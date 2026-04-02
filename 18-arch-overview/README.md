# Architecture Overview (Reference)

> A single-page diagram of how a production-grade coding agent stack *can* fit together. Supplementary to chapters 01–17 (each with `code-samples/`); this reference page has none.

This README sketches one **reference layout** for user/IDE surfaces, query engine, tools, services, and permissions. It synthesizes patterns described across the playbook.

For **subsystem detail and implementation order**, use the [main README](../README.md) table of contents and [AGENTS.md](../AGENTS.md).

## Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER / IDE                               │
│                   (Terminal, VS Code, JetBrains)                │
└──────────────┬──────────────────────────────┬───────────────────┘
               │ Input                        │ Bridge Protocol
               ▼                              ▼
┌──────────────────────┐        ┌─────────────────────────┐
│    REPL / React+Ink  │◄──────►│     IDE Bridge          │
│    (screens, input,  │        │  (JWT, sessions,        │
│     permissions UI)  │        │   transport)            │
└──────────┬───────────┘        └─────────────────────────┘
           │ handlePromptSubmit()
           ▼
┌──────────────────────────────────────────────────────────────┐
│                    QUERY ENGINE                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              query() — async generator loop            │  │
│  │                                                        │  │
│  │  ┌──────────┐    ┌───────────┐    ┌────────────────┐   │  │
│  │  │ API Call │───►│ Stream    │───►│ Tool Execution │   │  │
│  │  │ (retry,  │    │ (SSE,     │    │ (concurrent,   │   │  │
│  │  │ fallback)│    │  thinking)│    │  permissions)  │   │  │
│  │  └──────────┘    └───────────┘    └───────┬────────┘   │  │
│  │       ▲                                   │            │  │
│  │       └───────────────────────────────────┘            │  │
│  │              LOOP until end_turn / max turns           │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │  Compaction  │  │  Token       │  │  Recovery        │    │
│  │  (full/micro/│  │  Budget      │  │  (collapse →     │    │
│  │   partial)   │  │  Tracking    │  │   compact →      │    │
│  │              │  │              │  │   max_tokens)    │    │
│  └──────────────┘  └──────────────┘  └──────────────────┘    │
└──────────────────────────────────────────────────────────────┘
           │                              │
           ▼                              ▼
┌─────────────────────┐     ┌──────────────────────────────┐
│       TOOLS         │     │        SERVICES              │
│  ┌───────────────┐  │     │  ┌────────┐  ┌───────────┐   │
│  │ BashTool      │  │     │  │ MCP    │  │ Memory    │   │
│  │ FileEditTool  │  │     │  │ Client │  │ (memdir,  │   │
│  │ FileReadTool  │  │     │  └────────┘  │  extract) │   │
│  │ GrepTool      │  │     │  ┌────────┐  └───────────┘   │
│  │ AgentTool ────┼──┼──►  │  │ OAuth  │  ┌───────────┐   │
│  │ SkillTool     │  │     │  └────────┘  │ Analytics │   │
│  │ MCPTool       │  │     │  ┌────────┐  │ (events,  │   │
│  │ SendMessage   │  │     │  │ API    │  │  flags)   │   │
│  │ ...40+ tools  │  │     │  │ Client │  └───────────┘   │
│  └───────────────┘  │     │  └────────┘                  │
└─────────────────────┘     └──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│           PERMISSION SYSTEM             │
│  Modes: default │ plan │ auto │ bypass  │
│  Rules: allow/deny lists, classifiers   │
│  Handlers: interactive, coordinator,    │
│            swarm worker                 │
└─────────────────────────────────────────┘
```
