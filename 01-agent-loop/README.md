# Chapter 01: The Agent Loop

> A single async, streaming orchestration loop that turns model calls, partial responses, and tool execution into one coherent session the client can observe and cancel.

## Overview

An **agent loop** is the control program that repeatedly asks the language model what to do next, applies its decisions (including calling tools), updates what the model will see on the following round, and stops only when the model is done or a safety limit trips. It is not the model itself; it is the **scheduler** around the model. Each pass through the loop that ends in a new API request is one **model round** (often called a **turn** in logs—just keep your own definition consistent for billing and UX).

**User turn vs inner rounds.** In full products, one **user submission** may spin up work once (e.g. warming memory or context that stays valid for every model round in that submission), while the **inner loop** runs many times: stream → assemble assistant message → run tools → prepend results → repeat. Document which hooks fire **once per user input** versus **once per model round** so prefetch and telemetry stay correct.

**Why async streaming matters.** The model emits text and structured fragments over time. If you buffer the full reply before showing anything, latency feels high and you cannot cancel mid-flight. An **asynchronous** loop with **streaming** lets the UI or SDK pull events as they arrive, apply backpressure naturally, and abort a round without blocking a thread. The same loop shape can power a terminal UI, a headless API, and tests: every consumer subscribes to the same sequence of events at its own pace.

The **transcript** is the ordered list of **messages you actually send to the model** on the next call: system and developer instructions (where your stack puts them), prior user turns, assistant replies, tool invocations, and tool results. Everything the model is allowed to “read” when it generates the next token should be reflected there. If something affects behavior but never appears in that message list, it lives **outside the transcript**.

**Outside the transcript** is engine state that **controls** the loop without being copied into the chat history. Typical fields (names vary by product) include:

- **Turn counter** — how many model rounds you have used in this session or sub-task, so you can enforce a maximum and avoid infinite tool chatter.
- **Recovery attempts for output limits** — how many times you have already retried after the model hit its per-response output cap; paired with a hard ceiling so recovery cannot loop forever.
- **Whether a “reactive” compaction was already tried** — a flag so that, after a failure (for example context too large), you try an on-the-fly summarization path at most once per incident instead of burning cost in a tight loop.
- **Autocompact failure streak / circuit breaker** — counters that track repeated failures of full-context summarization; after enough consecutive failures you stop retrying that path and surface the error or fall back, instead of hammering a broken or unsuitable path.
- **Pending tool summary** — optional scratch state when tool outputs are large or deferred; the loop may track what still needs to be merged or shown without dumping raw blobs into the transcript until policy allows.
- **Stop-hook flag** — a signal from hooks or policy that says “end this trajectory now” even if the model might otherwise continue; the loop checks this when deciding whether to schedule another model call.
- **Temporary output limit bump for recovery** — a short-lived raise of the model’s maximum output length used only as a last-resort recovery step, then cleared, so normal runs keep tighter defaults.
- **Labeled continuation (transition) reason** — an optional record of *why* the previous round chose to continue (for example: drained staged context, reactive compact retry, token-budget nudge, stop-hook retry). The next iteration can use that label to avoid repeating the same expensive step blindly and to make tests and logs intelligible.

Immutable inputs to the loop (for example permission callbacks and fixed configuration) should stay separate from this mutable state. Updates should happen at well-defined **continuation** points—single assignments or spreads of a state object—so long sessions stay debuggable.

When things go wrong—context overflow, truncated answers, transient API faults—production systems use a **recovery cascade**: try the cheapest fix first (trim or collapse context), then heavier steps (summarization, raising output limits), each with caps so the system never spins without bound.

## How it fits together

Architecturally, a thin **stream consumer** assembles one complete assistant message per model call (text plus any tool-call blocks). A **tool executor** runs those calls (with permission checks where your design requires them) and returns normalized **tool result** messages. The loop appends those results to the transcript and either calls the model again or exits. **Recovery** wraps the same skeleton: on classified failures, rewrite messages or parameters, then re-enter without discarding user intent.

Many implementations expose **one** async iterator to callers but implement it as a **delegating wrapper** around an inner generator: the inner body holds the `while` loop and yields stream and message events; the outer function delegates with async iteration and runs **completion-only** bookkeeping after the inner loop returns normally (for example notifying a command queue that work was consumed). **Cancellation, thrown errors, and early client `return()`** on the iterator then bypass that bookkeeping by design—avoid double notifications or orphaned side effects.

```mermaid
flowchart TD
  subgraph consumer["Client / SDK"]
    pull[Pull events from async iterator]
  end

  subgraph loop["Agent loop"]
    prep[Pre-call pipeline: budgets, trim, summarize if needed]
    streamModel[Stream model response]
    assemble[Assemble assistant message]
    decide{Tool calls present in assembled message?}
    tools[Execute tools → append results]
    recover{Recoverable failure?}
    prep --> streamModel
    streamModel --> assemble
    assemble --> decide
    decide -->|yes| tools
    tools --> prep
    decide -->|no| recover
    recover -->|yes, with rewrite| prep
    recover -->|no| done([End turn / yield completion])
  end

  pull --> loop
```

**Continuation sites.** Each time the loop “starts over” toward another API call, mutable state should be replaced in one place: messages (and sometimes tool context) update together with counters and flags. Optional **transition labels** make it obvious whether you arrived at this iteration after a normal tool round, after draining collapsible context, after a reactive compact, after a token-budget nudge, and so on—so branching logic and recovery ordering stay consistent.

```mermaid
flowchart LR
  subgraph iter["One model round"]
    A[Destructure loop state] --> B[Pre-call pipeline on message copy]
    B --> C[Stream + assemble assistant]
    C --> D{Tool blocks?}
    D -->|yes| E[Execute tools, merge results]
    E --> F[Set state + transition label]
    F --> A
    D -->|no| G[No-follow-up path: recovery / hooks / budget / return]
  end
```

The pre-call pipeline (ordering matters in real systems) usually runs **before** each API request: clamp or spill oversized tool payloads, optionally trim history, run lighter “micro” compaction, optionally collapse archived context, then heavier full summarization if still over budget—with circuit breaking on repeated summarization failure. Runtime details such as prefetch overlap and withheld errors are summarized under **Production concepts** and **Insights**.

## Production concepts

- **Immutable loop inputs vs mutable loop state** — arguments that should not change mid-session stay fixed; counters, flags, pending work, and optional transition labels live in one state object updated only at explicit continue points, not scattered globals.
- **Stable chain identity and depth** — a logical **chain id** plus monotonic **depth** for nested or delegated work helps tracing, analytics, and debugging without overloading the transcript.
- **Injected dependencies** — model calling, compaction, identifiers, and clocks are passed in so tests can substitute fakes without patching modules.
- **Tool-result budgeting before compaction** — enforce size limits on tool outputs (and optional spill-to-storage with placeholders) *before* cache-aware compaction so compaction keys stay consistent whether bodies are inlined or replaced.
- **Withheld recoverable errors** — truncation-class failures may stay internal while recovery runs, so thin clients do not treat every warning as fatal; when recovery is exhausted, surface a single clear error.
- **Completion vs cancellation** — “work finished” notifications often fire only on **normal** generator completion; cancellation or early exit may intentionally skip side effects such as final hooks or dequeue notifications.
- **Delegating async generator** — a small outer iterator can forward yields from an inner loop and centralize asymmetric cleanup (success-only paths), matching how streaming clients actually stop.
- **Prefetch overlap** — memory or retrieval warm-up can start once per user submission; per-iteration discovery work can run under streaming and tool execution to hide latency.
- **Honest task token allowance after summarization** — after aggressive compaction, the API may under-count tokens already “spent” in the pre-summary window; sync the **remaining task budget** the model should respect with what the client already accounted for (see [Chapter 07 – Context Management](../07-context-management/README.md)).
- **What triggers another tool round** — rely on **assembled tool-call blocks** in the assistant message, not on the API’s reported stop reason alone, because streaming transports can report that field inconsistently; treat collected tool blocks as the authoritative signal that another iteration is needed (with hook-driven retries as a special case when the stream ends without tool blocks but policy says retry).
- **Lifecycle hooks vs API-error shapes** — when the last assistant-shaped payload is a **transport or quota error** (not a normal completion), be careful which hooks run before retry; uninformed hook rounds can inject more context and amplify failure loops.

**How this chapter connects to the rest of the spine**

- **[Chapter 02 – Tool system](../02-tool-system/README.md)** — Tool-result budgets and replacement records compose with compaction; executed tools yield normalized results back into the same transcript the loop recurses on.
- **[Chapter 03 – Permission system](../03-permission-system/README.md)** — Permission checks belong inside tool execution; the loop branches on completed tool-call and tool-result pairs.
- **[Chapter 04 – System prompt](../04-system-prompt/README.md)** — Per-iteration “request start” hooks align with assembling prompts and fork context while mutable loop state stays out of immutable prompt inputs.
- **[Chapter 05 – Tool implementations](../05-tool-implementations/README.md)** — Registry-backed runners produce the tool-result streams the loop merges; streaming vs batch execution stays behind the same contract.
- **[Chapter 06 – Streaming & messages](../06-streaming-and-messages/README.md)** — Streaming deltas assemble into assistant messages; error-shaped assistants and withhold rules belong with the message model.
- **[Chapter 07 – Context management](../07-context-management/README.md)** — Ordering of trim, micro-compaction, collapse, autocompact, reactive compaction, and task-budget sync lives here; the loop applies outputs and continues with a rewritten message list.

## Key design decisions

- **Async iterator (generator) instead of callbacks** — uniform yielded events (tokens, tool progress, final messages) let one core implementation serve terminal UI, SDK, and tests; trade-off: consumers must understand async iteration and cancellation.
- **Bounded recovery** — capped retries for expensive paths (for example repeated output-limit bumps) prevent infinite loops when the task is fundamentally too large; trade-off: some edge cases stop with an error instead of trying forever.
- **Tool execution decoupled from parsing** — the loop orchestrates; a dedicated executor owns concurrency and ordering so stream assembly stays simple; trade-off: more interfaces to maintain.
- **Continuation gates** — if a tool or attachment path requests “stop the run,” return without starting a new user round; distinct from normal completion, which may still run stop hooks and budget checks.
- **Command queue and lifecycle** — attachments derived from queued commands dequeue only after a successful attachment pass so retries do not double-notify; trade-off: slightly more state around partial failures.
- **Labeled transitions** — storing why the loop continued (recovery type, budget nudge, hook retry) costs a field or two but prevents ambiguous “retry everything” behavior and documents execution paths for operators.

## Insights

- **Cache-aware micro-compaction** — when compaction edits segments that participate in prompt caching, a boundary message may be **deferred** until after the response so real cache-invalidation metrics can be attached accurately.
- **Withheld errors must match recovery** — the same classification that decides “do not yield yet” must drive the recovery branch (for example media limits vs prompt-too-long); otherwise buffered assistant errors are dropped or mishandled.
- **Turn vs trajectory** — validators and UX often need assistant messages, tool results, and the following assistant reply treated as one logical unit; document that for anyone building message schemas.
- **Nested cancellation** — child abort scopes let you cancel sibling subprocesses (for example shell tools) without tearing down the entire session iterator.
- **Streaming transport fallback** — if the client falls back mid-stream, discard partial assistant content and pending tool results so the next attempt does not emit orphan tool-result rows without matching tool calls.
- **Stop hooks after withheld prompt-too-long** — if you skip or narrow stop hooks when recovering from context overflow, document that invariant: hooks meant for “normal” completions are not always safe when the model never produced a valid answer.

## Code samples

The examples are small, runnable Python sketches that mirror the ideas above without embedding any vendor implementation. Use them as patterns, not drop-in production modules.

| Sample | Description |
|--------|-------------|
| [`minimal_agent_loop.py`](code-samples/minimal_agent_loop.py) | Minimal async-generator loop with a mock model and tools; request-start event; chain id and per-round depth; continuation keyed off tool blocks, not stop reason. |
| [`state_machine.py`](code-samples/state_machine.py) | Mutable loop state carried across iterations; fields align with “outside the transcript” tracking, including an optional last-transition label. |
| [`recovery_cascade.py`](code-samples/recovery_cascade.py) | Layered recovery with caps: collapse, optional one-shot reactive compact, full compact, then bounded output-limit retries. |
| [`prefetch_and_task_budget.py`](code-samples/prefetch_and_task_budget.py) | Prefetch overlap with streaming/tools; adjusting remaining task budget after summarization; settle-then-consume prefetch gating. |
| [`withheld_stream_stub.py`](code-samples/withheld_stream_stub.py) | Recoverable errors buffered internally and only yielded to the consumer after recovery fails. |

## Build your own

1. **Define a small event vocabulary** — token deltas, tool started, tool finished, message finalized, done, error—whatever your UI needs—and yield them from one async iterator.
2. **Implement one model pass** — stream until one assistant message is complete (text plus structured tool-call blocks if any).
3. **Execute tools from structured blocks** — for each tool call, run your registry, enforce permissions inside execution, append tool results with stable correlation ids matching the calls.
4. **Introduce explicit loop state** — turn count, recovery counters, compaction flags, hook flags, optional transition label; reset only what each recovery level requires.
5. **Order pre-call steps** — tool-result size policy before cache-sensitive compaction; then trim, lighter compaction, optional collapse, heavier summarization with a failure circuit breaker.
6. **Classify failures** — map API and transport errors to recovery steps; for recoverable cases, keep assistant error payloads in an internal buffer for recovery logic but omit them from the outward stream until recovery succeeds, fails definitively, or is skipped—then yield once.
7. **Wire cancellation** — ensure subprocesses and prefetches cancel cleanly when the consumer aborts the iterator.
8. **Document trajectory rules** — how your stack defines a single “turn” for analytics, billing, and user-visible completion.
9. **Decide success-only side effects** — if something must run only when the loop finishes cleanly (not on cancel), place it in an outer delegating generator or an explicit `finally` that distinguishes completion kinds.

---

**Navigation:** [Overview](../README.md) | [Next: Chapter 02 – Tool System →](../02-tool-system/README.md)
