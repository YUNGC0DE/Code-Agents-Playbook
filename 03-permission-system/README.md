# Chapter 03: The Permission System

> How an agent runtime decides whether a proposed action may run—and how to overlap human time with cheap or expensive checks.

## Overview

Every proposed tool call is a **request to leave the model's text world and touch the real one** (files, shell, network, remote APIs). A **permission system** is the gate: for each request it yields **allow**, **deny** (with a reason the UI or logs can show), or **ask** (pause for a human or an automation policy).

This chapter is **conceptual**. It matches the shape of a full product implementation: ordered layers, async resolution, optional classifiers. The sections below decompose each building block—modes, rule evaluation, speculative work, and frozen context—so you can adopt them individually or combine them into a full gate.

**Concrete example — what happens when the agent wants to run `rm -rf node_modules`:**

1. **Rule check** — Deny rules run first. No deny rule matches this command, so evaluation continues.
2. **Mode check** — The current mode is *Default*. Shell commands are side-effecting, so the mode does not auto-approve.
3. **Ask** — The gate pauses and presents the command to the user. Meanwhile, speculative classification starts in the background.
4. **User approves** — The user clicks "Allow". The speculative classifier result (if ready) is consumed to enrich logging.
5. **Execute** — The tool runs `rm -rf node_modules` and returns the result to the agent.

The flow in diagram form:

```mermaid
flowchart TD
  tool[Tool use proposed] --> rules[Evaluate rules and tool checks]
  rules -->|allow| run[Execute]
  rules -->|deny| reject[Tool result error]
  rules -->|ask| dialog[User or automation]
  dialog --> spec[Speculative / async checks optional]
  spec --> run
  spec --> reject
```

---

## 3.1 Permission modes

Modes are **not** different models—they are **policy presets** on the same tool surface. The same capability graph is available in every mode; what changes is how **ask** is resolved by default, not which tools exist (unless a mode definition explicitly removes tools from the graph).

| Mode | Behavior | When to use |
|------|----------|-------------|
| **Default** | Conservative: side effects usually need explicit approval unless rules say otherwise. | Day-to-day interactive development where safety is paramount. |
| **Plan** | Exploration-first: read-oriented tools may proceed without interrupting the user; mutating tools still reach the gate. | Research or planning phases where the agent reads code but should not change it unsupervised. |
| **Accept edits** | In-scope file edits can auto-approve when product rules align; deny lists and tool-specific checks still apply. | Focused coding sessions where you trust the agent's file edits within a known scope. |
| **Bypass** | Minimize prompts where policy allows; **bypass-immune** paths remain (explicit ask rules, safety checks, tools that require human interaction, enterprise deny lists). | Batch tasks where you have vetted the plan and want minimal interruption. |
| **Dont-ask / auto** | Map unresolved **ask** to **deny**, or route **ask** through an **automation classifier** instead of a person. | CI pipelines, headless workers, or scripted flows with no human in the loop. |

**Modes code sample (excerpt from [`permission_modes.py`](code-samples/permission_modes.py)):**

```python
class PermissionMode(str, Enum):
    DEFAULT = "default"
    PLAN = "plan"
    ACCEPT_EDITS = "acceptEdits"
    BYPASS = "bypassPermissions"
```

> **Tie-in — Chapter 04 (Execution Scope):** Scope complements permissions. While the permission system decides *whether* an action may run, [execution scope](../04-execution-scope/README.md) decides *where* it may run—limiting the directories, files, or network targets available to tools. A tight scope can make a permissive mode safer.

---

## 3.2 Rule evaluation

Permission resolution follows a layered, ordered pipeline. Rules are merged from multiple sources with explicit precedence.

**Layered rules** — User, project, session, CLI, and managed policy merge with explicit precedence; matchers can target whole tools or content patterns (e.g. command prefixes).

**Execution order (conceptual):**

1. **Pre-invocation hooks** run first. They may attach a **permission result**, adjust input, or block continuation.
2. **Hook resolution** interprets that result: a hook **allow** still flows through a **rule-only** overlay—configured **deny** and **ask** rules are not overridden by the hook. A hook **deny** ends the story. A hook **ask** enters the interactive gate, optionally with a **forced decision** for tests or scripted flows while the UI still shows hook messaging.
3. The shared **can-use-tool** path walks **deny rules**, **ask rules**, the tool's own **checkPermissions** (and optional static checks for shell-like tools), then **mode** and allow rules, optional **classifiers**, and the dialog or non-interactive fallback.

```mermaid
sequenceDiagram
  participant Hooks as Pre-invocation hooks
  participant Resolve as Hook resolution
  participant Gate as Permission gate
  participant Tool as Tool run
  Hooks->>Resolve: permission result / updated input
  Resolve->>Gate: allow after rule overlay, or full gate with forceDecision
  Gate->>Tool: allow with updated input
```

**Key rule-evaluation design points:**

- **Hook allow is not blanket allow** — After hook **allow**, **rule-only** checks still apply so hooks cannot override enterprise deny lists or configured **ask** rules.
- **Explicit partial re-checks** — Some paths re-run only the rule subset (not full classifiers, bypass, or post-hooks) so behavior stays testable and auditable.
- **Managed policy** — Enterprise may enforce **managed-only** rules so user or project shortcuts cannot widen access; UI "always allow" may be hidden so approvals stay policy-bound.

> **Tie-in — Chapter 02 (Tool System):** Permission checks live inside tool execution. Each tool's `checkPermissions` method is invoked as part of the gate pipeline described above. See [the tool system chapter](../02-tool-system/README.md) for how tools declare their permission requirements and static checks.

---

## 3.3 Speculative work

When the outcome is **ask**, wall-clock time is often dominated by human reaction. The key insight: treat **ask** as a **scheduling surface**—speculative work is cheap relative to human wait time if you bound concurrency and key results correctly.

You can start an async job (risk scoring, command classification, validation) **in parallel with the dialog**. When the user confirms, **consume** the result under a **stable key** (tool-use id, hash, or normalized command string) so parallel dialogs never share state. If the user cancels, tear down tasks so you do not leak **unhandled rejection** noise.

**Timeline example:**

```mermaid
sequenceDiagram
  participant Agent
  participant Gate as Permission gate
  participant User
  participant Classifier as Async classifier

  Agent->>Gate: proposes tool call
  Gate->>User: "Allow rm -rf node_modules?"
  Gate->>Classifier: start classification (async)
  Note over User,Classifier: Both run in parallel
  Classifier-->>Gate: result ready (e.g. "medium risk")
  User->>Gate: clicks Allow
  Gate->>Gate: consume speculative result by stable key
  Gate->>Agent: tool call proceeds
```

Some interactive sessions use a **short bounded wait**: race the classifier against a timer; if the classifier returns a high-confidence **allow** before the timeout, skip the dialog and **consume** the speculative result so it is not reused. Coordinator-style workers may **await** automated checks **before** showing a dialog—different scheduling, same building blocks.

**Two classifier roles:**

1. **Shell / risk allow** classifiers — tied to command text, safe to run speculatively while a dialog is open.
2. **Auto-mode** classifiers — read broader transcript context when automation replaces the human. Different inputs, different contracts.

**Speculative task lifecycle (excerpt from [`speculative_classifier.py`](code-samples/speculative_classifier.py)):**

```python
def start(self, tool_use_id: str, command: str) -> None:
    ...
    task = asyncio.create_task(classify())
    task.add_done_callback(lambda t: t.exception())
    self._tasks[tool_use_id] = task

async def consume(self, tool_use_id: str) -> str | None:
    ...
```

**Peek / consume** (often by normalized command string for shell allow classifiers) keeps speculative results aligned with the final permission key; clear abandoned tasks on cancel.

> **Tie-in — Chapter 14 (Hooks and Lifecycle):** Hooks can carry permission results into downstream processing. A pre-invocation hook may attach classifier output or risk scores that the speculative pipeline produced. See [hooks and lifecycle](../14-hooks-and-lifecycle/README.md) for the full hook execution model and how permission results flow through the hook chain.

---

## 3.4 Frozen permission context

Treat policy as an **immutable snapshot** for the in-flight request: mode, merged rules, and any other inputs the gate must not mutate mid-flight. A buggy or adversarial tool must not widen privileges by mutating live policy while resolution runs—same spirit as passing **read-only config** into a training step.

In UI-driven apps, updating global policy after an approval may **re-queue** still-pending items; that is a separate concern from the snapshot semantics **during** one resolution.

**Frozen context code sample (excerpt from [`permission_checker.py`](code-samples/permission_checker.py)):**

```python
@dataclass(frozen=True)
class FrozenPermissionContext:
    mode: str
    rules: tuple[PermissionRule, ...]

def resolve_tool_permission(tool_name: str, ctx: FrozenPermissionContext) -> PermissionBehavior:
    ...
```

**Multi-session shapes:** a **leader** UI, in-process bridge, or serialized mailbox may determine **who** sees **ask**. Shell-heavy **workers** may **await** a classifier before escalating to the leader; the **main** interactive agent may **race** the classifier against a short timeout instead—different scheduling, same primitives. In multi-agent setups, preserve the **leader's permission mode** when applying permission updates from workers so teammate context does not widen policy unintentionally.

---

## Production concepts

- **Async gate** — Permission resolution is async per tool use; tests inject a **forced decision** to skip UI.
- **Forced decision** — Automation and tests need allow/deny without a person; the dialog can still show hook copy while the outcome is predetermined.
- **Structured logging** — Log tool identity and decision **source** (config vs dialog vs classifier), not raw secrets; numeric **reason codes** help telemetry without PII.
- **Permission-style hooks** in non-interactive contexts must **decide** (allow/deny/interrupt) or fall back to **deny**, not hang waiting for a UI that does not exist.
- **Post-invocation** hooks see permission **mode** for context but do not re-run the allow gate—they observe completed output.

## Code samples

All snippets below live under `docs/03-permission-system/code-samples/` only.

| Sample | Description |
|--------|-------------|
| [`permission_modes.py`](code-samples/permission_modes.py) | Mode enum and a tiny "would this mode skip a prompt?" sketch |
| [`permission_checker.py`](code-samples/permission_checker.py) | Frozen context + rule list with deny-first precedence -> allow / deny / ask |
| [`speculative_classifier.py`](code-samples/speculative_classifier.py) | Start async classification early; peek, consume, optional race vs timeout |

Run any sample: `python docs/03-permission-system/code-samples/<file>.py`.

## Build your own

1. Define a small **mode enum** and a matrix: mode x tool category -> default (prompt vs silent), then layer **deny-wins** rules on top.
2. Store rules in **priority order**; support **managed-only** if you have enterprise policy.
3. Expose `can_use_tool(tool_name, payload, frozen_context) -> Decision` where `frozen_context` is immutable (e.g. `dataclass(frozen=True)` or a deep snapshot).
4. On **ask** for risky tools, start `asyncio.create_task(classify(...))` before awaiting the user; **consume** by stable key (tool-use id or normalized command). Optionally **race** against a short timeout if skipping the dialog on high-confidence **allow** is acceptable.
5. If you add **hooks**, run them **before** the main gate; after hook **allow**, run a **rule-only** re-check; thread **force_decision** for tests and scripted flows.

---

**Navigation:** [<- Chapter 02 -- Tool System](../02-tool-system/README.md) | [Overview](../README.md) | [Next: Chapter 04 -- System Prompt ->](../04-system-prompt/README.md)
