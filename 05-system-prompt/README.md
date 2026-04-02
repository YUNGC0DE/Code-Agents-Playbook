# Chapter 04: System Prompt Engineering

> Layered system instructions, separate context maps, and cache-stable request prefixes.

## Overview

The system prompt is not one string — it is an **ordered stack of blocks**. A product default, an agent override, project instructions, and an append tail all merge into what the model reads. Understanding this stack is essential for cache stability and correct behavior.

**Why split context from system prose?** Default product prompts assume specific metadata (tool lists, environment hints, git summaries). If a caller passes a **fully custom** system prompt, building the same default-derived **system** context map would attach data the model never agreed to interpret—wasteful and confusing. Mature implementations therefore **skip default system-context collection** when the default prompt stack is not used, while still loading **user**-side context such as project instruction files when policy allows.

---

## 5.1 The prompt stack

The effective system prompt is assembled from **discrete, labeled blocks**. Each block has a role (product default, agent override, append tail, etc.) and a position in the final array. Blocks never free-merge into one string — they remain separate entries so you can log, hash, and cache each one independently.

### How blocks layer

Think of the stack as a short ordered list. The resolution logic (covered in 5.2) decides **which** blocks appear; once chosen, they are concatenated in a fixed order:

```
[ base block ]  +  [ optional agent / custom block ]  +  [ append tail ]
```

### Concrete example: three blocks assembling into a final prompt

Suppose no override or coordinator is active, the product default is in play, the user has enabled a proactive-style agent, and an append tail is configured.

**Block 1 — Product default:**
```
You are Claude, an AI assistant made by Anthropic.
You have access to a set of tools you can use to answer the user's question.
Always prefer using tools over guessing.
```

**Block 2 — Agent section (proactive-style, appended after default):**
```
## Agent: code-review
You are reviewing a pull request. Focus on correctness, test coverage,
and adherence to the project style guide. Suggest improvements inline.
```

**Block 3 — Append tail:**
```
IMPORTANT: Never commit directly to main. Always create a feature branch.
```

**What the model reads (combined):**
```
You are Claude, an AI assistant made by Anthropic.
You have access to a set of tools you can use to answer the user's question.
Always prefer using tools over guessing.

## Agent: code-review
You are reviewing a pull request. Focus on correctness, test coverage,
and adherence to the project style guide. Suggest improvements inline.

IMPORTANT: Never commit directly to main. Always create a feature branch.
```

Each block retains its own cache-control boundary, so changing the append tail does not invalidate the cached prefix formed by blocks 1 and 2.

---

## 5.2 Priority resolution

The resolution logic is a strict priority ladder — only one base path wins, and the append tail rides along with every path except full override.

| Step | Outcome |
|------|---------|
| **Full override** | Single authoritative system block; no default stack, no append tail, no "default" system-context map in typical designs. |
| **Coordinator base** (when enabled and **no** main-thread agent) | Replaces the product default for that loop; append tail still applies. Does not compose with agent/custom/default in the same turn—this path returns early. |
| **Main-thread agent** | Normally **replaces** the default prompt. In **proactive-style** modes, the agent block is **appended** after the default (same idea as teammate stacking). |
| **Custom CLI/SDK string** | Used when **no** agent block is selected—never competes with an active main-thread agent prompt. |
| **Product default** | Fallback when nothing above supplies the base. |
| **Append tail** | Extra system material **after** all of the above, except under full override. |

```mermaid
flowchart TD
  subgraph resolve["System prompt resolution"]
    O{Full override?}
    O -->|yes| ONE[Single block only]
    O -->|no| C{Coordinator base<br/>and no main agent?}
    C -->|yes| COORD[Coordinator + optional append]
    C -->|no| A{Agent prompt?}
    A -->|yes, proactive-style| STK[Default blocks + agent section + append]
    A -->|yes, standard| AG[Agent blocks + append]
    A -->|no| U{Custom base?}
    U -->|yes| CU[Custom + append]
    U -->|no| DEF[Default + append]
  end
  subgraph ctx["Context maps (parallel concern)"]
    UC[user context: e.g. cwd, date, project instructions]
    SC[system context: e.g. git status, diagnostics]
    UC --> MERGE[Serialize into API: early user message vs system append]
    SC --> MERGE
  end
  MERGE --> API[Provider request]
  ONE --> API
  COORD --> API
  STK --> API
  AG --> API
  CU --> API
  DEF --> API
```

### Key resolution rules

- **Ordering beats length** — A short default plus a labeled agent section behaves differently than a single merged paragraph.
- **Coordinator is not composable** with a main-thread agent in the same resolution step—it short-circuits before agent selection.
- **Append versus replace** — Agent and mode dictate whether domain rules **replace** the default or **stack** after it; teammates often follow the append pattern.
- **System prompt as an array** — Enables per-block cache scope and clean separation of attribution headers, product prefixes, and body text.

---

## 5.3 Context maps

Context collection runs **in parallel** with system-prompt assembly. Two maps — **user context** and **system context** — carry structured metadata that the model needs but that does not belong inside the prose blocks.

### What the maps look like in practice

**User context** (lands early in the message list inside a dedicated meta turn):
```
User context:
  cwd: /project/my-app
  date: 2025-01-15
  instructions: "Use TypeScript strict mode. Prefer functional components..."
  extra_dirs: ["/shared/design-tokens"]
```

**System context** (appended to the system side as labeled lines):
```
System context:
  git_status: "branch: main, clean"
  shell: zsh
  os: darwin
  editor: vscode
```

### Serialization and cache implications

**User context** usually lands **early in the message list** inside a dedicated meta turn: structured sections per key so the model can ignore irrelevant material. **System context** is often **appended to the system side** as labeled lines derived from the same map. Both maps are part of the **same cache family** as system prose—changing `claudeMd` or `gitStatus` without intent can invalidate the prefix.

Context maps are built by **pure, testable functions** with a single session cache where I/O is expensive. This keeps them deterministic and avoids re-reading the filesystem on every turn.

### Tie-in: [Chapter 07 – Context management](../07-context-management/README.md) / [Chapter 08 – Caching](../08-caching/README.md)

Compaction and token budgets assume you can tell **what changed** in the transcript and in the API prefix. If system text, tool JSON, or cache-control metadata drifts unnoticed, you pay for **cache misses** exactly when compaction is already tight. Treat **hash-stable prefixes** as part of context hygiene. When diagnosing prefix cache misses, diff **structured** fields (model, tool schema hash, system hash, context keys) instead of eyeballing one giant string.

---

## 5.4 Project instruction files

**Project instruction files (CLAUDE.md-style)** are the primary way users inject persistent rules into context. They follow a discovery-and-merge pipeline:

1. **Discovery** — Walk from the working directory toward filesystem root (and optionally merge additional roots the user asked to include). Files **closer to cwd** are typically merged **later** so nearby rules win.
2. **Layers** — Think in terms of **managed**, **user-global**, **project**, and **local-private** instruction files; products differ on exact paths, but the **ordering story** is always "later / closer overrides earlier / farther."
3. **Includes** — Markdown-style `@path` inclusion pulls fragments in with **cycle detection**; missing files are skipped so one broken reference does not fail the whole session.
4. **Gating** — Environment flags or "bare" modes can disable automatic discovery while still honoring **explicit** extra directories—useful for CI or minimal repros.
5. **Dual surfaces** — The same aggregated text may feed a **user-context field** for the main agent and, separately, a **classifier-only** message with its own delimiter and cache hint—without duplicating filesystem reads once a session cache exists.

### Concrete example: discovery order

Given a working directory of `/home/user/projects/my-app/src`:

```
~/.claude/instructions.md          # user-global  (loaded first)
/home/user/projects/CLAUDE.md      # project root  (loaded second)
/home/user/projects/my-app/CLAUDE.md  # app root   (loaded third, wins ties)
/home/user/projects/my-app/.claude/local.md  # local-private (loaded last, highest priority)
```

None of this replaces the **system prompt priority ladder** from 5.2; it **enriches** what the model sees in a controlled slot inside the user-context map.

---

## 5.5 Cache stability

Cache-safe design applies to everything that participates in the provider's **prefix fingerprint**: model id, tool schemas, system blocks, context maps, the start of the transcript, and options like thinking or output caps. Volatile strings (timestamps, random ids, non-deterministic serialization) in those regions **break** prefix reuse.

### The stability rule

> Stable blocks first, volatile blocks after an intentional breakpoint, and **frozen snapshots** for forks or sub-sessions prevent silent drift mid-run.

### What to hash

Build and log the tuple your provider actually keys on:

```python
cache_key_inputs = (
    model_id,                   # "claude-sonnet-4-20250514"
    hash(tool_schemas_json),    # deterministic serialization
    hash(system_blocks),        # each block hashed in order
    hash(context_maps),         # user + system maps
    thinking_enabled,           # True / False
    max_output_tokens,          # 16384
)
```

Exclude volatile fields (wall-clock timestamps, random session ids) from the stable slice. If you must include a date, pin it per-session so it does not change between turns.

### Side paths and resume

Secondary entrypoints that must match the main loop's prefix should mirror the same assembly order; a controlled cache miss beats failing the call.

### Tie-in: [Chapter 10 – Subagents](../10-subagents/README.md) / [Chapter 11 – Multi-agent](../11-multi-agent/README.md)

Nested agents should inherit a **frozen bundle**: rendered system blocks, user and system context maps, tools, model-related options, and the shared message prefix. A live builder that re-reads flags or disk mid-run **desynchronizes** cache identity with the parent. Always pass **rendered** bytes and frozen maps at spawn time — never let a child agent re-resolve the prompt stack independently.

---

## Production concepts

- **Strict priority ladder** — Override wins absolutely. Coordinator base applies only in its gated mode **and** when no main-thread agent owns the loop. Agent beats custom string. Proactive-style modes flip agent from replace to stack.
- **Append-only tail** — Survives coordinator, agent, custom, and default branches; omitted only under full override.
- **Optional extra blocks** — Integrations may inject another system segment when a custom base is combined with an **opt-in** memory or tooling path (so the model knows filenames and write semantics without resurrecting the full default prompt).
- **Context maps** — Pure, testable builders for cwd, shell, date, aggregated instructions, git/VCS snippets, coordinator addenda, etc.
- **Cache fingerprint** — Hash or log the tuple your provider actually keys on; keep cached segments free of wall-clock noise.
- **Fork safety** — Pass **rendered** bytes and frozen maps at spawn time ([Chapter 10 – Subagents](../10-subagents/README.md)).
- **Custom prompt + empty system context** — Skipping default-derived system metadata when the default stack is bypassed avoids dangling context.

---

## Insights

- **Diagnostics** — When prefix cache misses, diff **structured** fields (model, tool schema hash, system hash, context keys) instead of eyeballing one giant string.
- **Classifiers** — Permission or auto-mode models may see project instructions in a **dedicated** user-shaped message with stable cache control; that is separate from the main chat meta turn but shares the same underlying aggregated text.

---

## Code samples

| Sample | Description |
|--------|-------------|
| [`prompt_assembly.py`](code-samples/prompt_assembly.py) | Priority ladder: override, coordinator short-circuit, proactive append vs replace, append tail |
| [`context_builder.py`](code-samples/context_builder.py) | User/system maps, instruction-file layering, merge order |
| [`cache_safe_params.py`](code-samples/cache_safe_params.py) | Stable JSON and a toy prefix fingerprint |

---

## Build your own

1. Model the system side as a **list of blocks** with explicit labels for logging.
2. Implement `build_effective_prompt(...)` with override, coordinator (early exit without agent), agent (replace vs append), custom, default, and append.
3. Build context with **pure functions** and a single session cache where I/O is expensive.
4. Hash the tuple your provider uses for prefix cache; exclude volatile fields from the stable slice.
5. For forks, **serialize** effective prompt + context at spawn and pass immutable copies forward ([Chapter 10 – Subagents](../10-subagents/README.md)).

---

**Navigation:** [← Chapter 03 – Permissions](../03-permission-system/README.md) | [Overview](../README.md) | [Next: Chapter 05 – Tool Implementations →](../05-tool-implementations/README.md)
