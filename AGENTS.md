# AGENTS.md — Instructions for AI Agents

> This file is designed to be consumed by AI agents that need to build code agent systems. It tells you how to navigate and use this repository efficiently.

**Humans** building a personal or team agent should use this file the same way: principles, anti-patterns, and the concept index are checklist-quality. For narrative context, read [README.md](README.md) and the chapter *Overview* sections first.

## Purpose

This repository — **Code Agents Playbook** documents how a production-grade AI code agent works: the agent loop, tool system, permissions, context management, multi-agent coordination, and more.

**Use this as your blueprint** when building a custom code agent system. Chapters are **reference**, not a dependency graph: implement the minimal loop (Ch 01–02), add permissions (03), then add features from the concept index as required.

**Full potential architecture (one diagram):** [17-arch-overview](17-arch-overview/) shows how subsystems connect end-to-end—user/IDE, query engine, compaction and recovery, tools, services (MCP, memory, API, analytics), and the permission layer. It is a **reference layout** drawn from production patterns; use the staged steps below and the concept index to choose what you need.

## Quick Navigation

### If you are building a code agent from scratch

Read these 4 chapters in order — they give you the minimal viable architecture:

1. **[Chapter 01: Agent Loop](01-agent-loop/)** — The core `async generator` loop that drives everything
2. **[Chapter 02: Tool System](02-tool-system/)** — How to define, register, and execute tools
3. **[Chapter 03: Permission System](03-permission-system/)** — Safety gates for tool execution
4. **[Chapter 04: System Prompt](04-system-prompt/)** — How to assemble and cache system prompts

Each chapter has a "Build Your Own" section with step-by-step guidance and runnable Python code in `code-samples/`.

### If you are adding a specific capability


| I need...                    | Read                                                            |
| ---------------------------- | --------------------------------------------------------------- |
| Shell command execution      | [Ch 05: Tool Implementations](05-tool-implementations/)         |
| File editing with validation | [Ch 05: Tool Implementations](05-tool-implementations/)         |
| Streaming API responses      | [Ch 06: Streaming & Messages](06-streaming-and-messages/)       |
| Context window management    | [Ch 07: Context Management](07-context-management/)             |
| Persistent memory            | [Ch 08: Memory System](08-memory-system/)                       |
| MCP server integration       | [Ch 09: MCP Integration](09-mcp-integration/)                   |
| Nested agent spawning        | [Ch 10: Subagents](10-subagents/)                               |
| Multi-agent coordination     | [Ch 11: Multi-Agent Coordination](11-multi-agent-coordination/) |
| Extensible skills/plugins    | [Ch 12: Skills & Plugins](12-skills-and-plugins/)               |
| Lifecycle hooks              | [Ch 13: Hooks & Lifecycle](13-hooks-and-lifecycle/)             |
| Fast startup                 | [Ch 14: Startup Optimization](14-startup-optimization/)         |
| Cost tracking                | [Ch 15: Cost & Observability](15-cost-and-observability/)       |
| IDE integration              | [Ch 16: IDE Bridge](16-ide-bridge/)                             |


### If you are optimizing for production

Read Chapters 14–16 before shipping. They cover startup performance, cost management, and IDE integration patterns.

---

### 1. Generator-Based Agent Loop

Use `async generators` (`async def` + `yield`) for the core loop. This gives you streaming, backpressure, and cancellation for free. The model calls tools in a loop; each iteration yields partial results to the UI.

→ See [Chapter 01](01-agent-loop/), `code-samples/minimal_agent_loop.py`

### 2. Tool as a Contract

Every tool implements the same interface: input schema, permission check, execution, result rendering. This uniformity enables concurrent execution, permission auditing, and deferred loading.

→ See [Chapter 02](02-tool-system/), `code-samples/tool_contract.py`

### 3. Immutable Permission Contexts

Freeze the permission context before passing it to tools. This prevents tools from escalating their own privileges. Use `DeepImmutable<>` (TypeScript) or `@dataclass(frozen=True)` (Python).

→ See [Chapter 03](03-permission-system/), `code-samples/permission_checker.py`

### 4. Cache-Safe Forking

When spawning subagents, share the *rendered* system prompt bytes — not the prompt builder function. Re-rendering can produce different bytes (due to feature flags, timestamps, etc.) and bust the prompt cache.

→ See [Chapter 10](10-subagents/), `code-samples/cache_sharing.py`

### 5. Recovery Cascades

Distinguish **per-turn trimming** (before each API call) from **error-path recovery** (after a bad response).

**Before each API call** (cheapest first): tool-result budget / spill → optional history snip → micro-compaction → optional context-collapse projection → autocompact if still over threshold. Chapter 07 details ordering and circuit breakers.

**After truncation / limit errors** (bounded retries): reactive compact at most once per episode, then raise `max_output_tokens` with a **hard cap** on attempts—never infinite loops.

→ [Chapter 01](01-agent-loop/) (pipeline + withheld errors), [Chapter 07](07-context-management/) (`circuit_breaker.py`, `auto_compaction.py`)

### 6. Feature Gates for Dead Code Elimination

Use compile-time feature flags to strip entire modules from builds. This keeps the binary small and prevents internal features from leaking to external builds.

→ See [Chapter 14](14-startup-optimization/), `code-samples/feature_gates.py`

### 7. File-Based Coordination

For multi-agent systems, use file-based mailboxes instead of IPC. Files survive process restarts, work across terminal multiplexers, and provide a unified interface for in-process and cross-process agents.

→ See [Chapter 11](11-multi-agent-coordination/), `code-samples/file_mailbox.py`

### 8. Speculative Work During Blocking Operations

While the user sees a permission dialog, run the classifier speculatively. While the model streams, prefetch memory and skills. The result is ready when needed — zero extra latency.

→ See [Chapter 03](03-permission-system/), `code-samples/speculative_classifier.py`

### 9. PII Safety at the Type Level

Name your analytics metadata type something verbose like `AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS`. Engineers are forced to read and acknowledge the constraint at every call site.

→ See [Chapter 15](15-cost-and-observability/), `code-samples/pii_safe_analytics.py`

### 10. Deferred Tool Discovery

Don't load all tool schemas into the system prompt. When tool descriptions exceed ~10% of the context window, use a `ToolSearch` meta-tool that lets the model discover tools on demand.

→ See [Chapter 09](09-mcp-integration/), `code-samples/deferred_tool_discovery.py`

### 11. Task Budget Honesty and Tool Continuation

After **autocompact**, the API may only see a summary—sync `**task_budget.remaining`** with what the client measured as consumed (pre-compact window). For the **next round**, treat **presence of `tool_use` blocks** as the signal to run tools and continue; `stop_reason === 'tool_use'` is not always reliable in streaming stacks.

→ [Chapter 01](01-agent-loop/) (`prefetch_and_task_budget.py`), [Chapter 06](06-streaming-and-messages/) (`tool_use_exit_signal.py`), [Chapter 07](07-context-management/) (`api_task_budget_remaining.py`)

---

## Anti-Patterns to Avoid

These are common mistakes to avoid:

1. **Shared mutable state across agents** — Use `AsyncLocalStorage` / `contextvars` instead of global state. When agents run concurrently, shared state causes attribution errors.
2. **Re-rendering prompts at fork time** — Feature flags, timestamps, and caches can change between parent and fork creation. Freeze the rendered bytes.
3. **Unbounded compaction retries** — Use a circuit breaker (max 3 failures). Otherwise, a permanently-too-large context wastes API calls indefinitely.
4. **Synchronous boot** — Startup must be parallelized. Keychain reads, MDM settings, MCP preconnect, and credential fetches should all fire concurrently before heavy module evaluation.
5. **Tool permission escalation** — Never pass a mutable permission context to tools. A tool could modify its own permission level.
6. **Blocking on tool schemas** — If you have 40+ tools, loading all schemas delays the first API call. Defer non-essential tool schemas.
7. **Losing messages on crash** — Persist the user message to the transcript *before* the API call, not after. This ensures session resumability.
8. **Single recovery strategy** — Use the full **pre-API pipeline** (snip / micro-compact / collapse / autocompact) before assuming you need a single blunt “compact everything.” On errors, escalate reactive compact → max_output with a retry cap.

---

## Token Budget Guidance

If you have limited context and can only read a few chapters, read them in this priority:


| Priority | Chapter                                          | Why                                                    |
| -------- | ------------------------------------------------ | ------------------------------------------------------ |
| 1        | [01: Agent Loop](01-agent-loop/)                 | The skeleton — everything else plugs into this         |
| 2        | [02: Tool System](02-tool-system/)               | The hands — how the agent interacts with the world     |
| 3        | [03: Permissions](03-permission-system/)         | The immune system — safety is non-negotiable           |
| 4        | [07: Context Management](07-context-management/) | The memory manager — without this, long sessions crash |
| 5        | [10: Subagents](10-subagents/)                   | The cloning system — enables parallel work             |


---

## Concept → Chapter Index


| Concept                                                                         | Chapter                            |
| ------------------------------------------------------------------------------- | ---------------------------------- |
| Agent loop, pre-API pipeline, recovery, `task_budget`, tool_use exit signal     | [01](01-agent-loop/)               |
| Tool contract, registry, streaming executor, result budget, content replacement | [02](02-tool-system/)              |
| Permission modes, rules, speculative classification                             | [03](03-permission-system/)        |
| System prompt priority, context maps, cache-stable keys                         | [04](04-system-prompt/)            |
| Bash/file/search tool patterns                                                  | [05](05-tool-implementations/)     |
| Message types, streaming assembly, API normalization                            | [06](06-streaming-and-messages/)   |
| Auto-compact, micro-compact, token budget, circuit breaker                      | [07](07-context-management/)       |
| Scoped memory, extraction, entrypoints                                          | [08](08-memory-system/)            |
| MCP lifecycle, config merge, deferred tools                                     | [09](09-mcp-integration/)          |
| Subagent spawn, frozen prompt, sidechain transcript                             | [10](10-subagents/)                |
| File mailbox, permission bridge, contextvars                                    | [11](11-multi-agent-coordination/) |
| Skills frontmatter, plugins, template substitution                              | [12](12-skills-and-plugins/)       |
| Hook registry, lifecycle, execution backends                                    | [13](13-hooks-and-lifecycle/)      |
| Parallel boot, feature gates, lazy import, preconnect                           | [14](14-startup-optimization/)     |
| Cost tracking, PII-safe analytics, telemetry context                            | [15](15-cost-and-observability/)   |
| Bridge framing, session backoff, JWT                                            | [16](16-ide-bridge/)               |


---

## How to Build a Code Agent Using This Repository

You can walk the repo **in chapter order (01→16)** for a complete tour, or ship a **minimal agent first** by finishing **01–04**, then layering **05–09** (core systems), **10–13** (advanced patterns), and **14–16** (production) as needed. Below, **one step groups several chapters**; each chapter has its own **Build your own** and `code-samples/` entry points.

### Step 1: Agent loop and tool system (Chapters [01](01-agent-loop/)–[02](02-tool-system/))

Implement `minimal_agent_loop.py`, then `tool_contract.py`, `tool_registry.py`, and `streaming_executor.py`. Add `recovery_cascade.py` / `prefetch_and_task_budget.py` when you wire pre-API trimming and budgets; add `tool_result_budget.py` when you cap tool output.

### Step 2: Permissions and system prompt (Chapters [03](03-permission-system/)–[04](04-system-prompt/))

Implement `permission_checker.py` (and `permission_modes.py`, `speculative_classifier.py` as you harden rules). Build `prompt_assembly.py`, `context_builder.py`, and cache-safe prompt parameters.

### Step 3: Tool implementations and streaming (Chapters [05](05-tool-implementations/)–[06](06-streaming-and-messages/))

Add production-shaped tools (`bash_tool.py`, `file_edit_tool.py`, `search_tools.py`). Implement `message_types.py`, `stream_handler.py`, and `tool_use_exit_signal.py` so streaming assembly and tool continuation match real API behavior.

### Step 4: Context, memory, and MCP (Chapters [07](07-context-management/)–[09](09-mcp-integration/))

Add token budgeting and compaction (`token_budget.py`, `micro_compaction.py`, `auto_compaction.py`, `circuit_breaker.py`, `api_task_budget_remaining.py`). Add `scoped_memory.py` / extraction / index samples. Integrate MCP (`mcp_client.py`, `mcp_config_merger.py`, `deferred_tool_discovery.py`).

### Step 5: Subagents and multi-agent coordination (Chapters [10](10-subagents/)–[11](11-multi-agent-coordination/))

Implement `subagent_spawner.py`, `cache_sharing.py`, `sidechain_transcript.py`, then coordination patterns (`file_mailbox.py`, `async_context_isolation.py`, `leader_permission_bridge.py`).

### Step 6: Skills, plugins, and hooks (Chapters [12](12-skills-and-plugins/)–[13](13-hooks-and-lifecycle/))

Add `skill_loader.py`, `plugin_registry.py`, `argument_substitution.py`, and hook execution (`hook_registry.py`, `lifecycle_hooks.py`, `hook_execution_backends.py`).

### Step 7: Production hardening (Chapters [14](14-startup-optimization/)–[16](16-ide-bridge/))

Optimize startup (`parallel_boot.py`, `feature_gates.py`, `lazy_loading.py`, `api_preconnect.py`). Add cost and observability (`cost_tracker.py`, `pii_safe_analytics.py`, `session_telemetry.py`). When you integrate an IDE, add bridge pieces (`bridge_transport.py`, `session_manager.py`, `jwt_auth.py`).

Together, these seven steps cover **all 16 chapters** in the same part groupings as the book: foundations (01–04), core systems (05–09), advanced patterns (10–13), production (14–16).

---

*Start with the [main README](README.md) for scope and disclaimers; use this file as your implementation checklist alongside the chapters.*