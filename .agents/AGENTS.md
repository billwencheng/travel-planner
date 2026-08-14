# Travel Planner System - Context Harness & Architectural Rules

This document serves as the project's shared configuration and rule book for the Travel Planner agent system built on Google Cloud Platform (GCP). It outlines the fundamental principles, architectural specs, and grading criteria that govern all implementations in this repository.

## System Environment
- **Target Platform:** Google Cloud Platform (GCP) services (Vertex AI Agent Platform, Agent Engine Runtime, Cloud Run, Secret Manager, Cloud Trace/Logging/Monitoring, BigQuery).
- **Tooling:** \`agents-cli\` and the suite of \`google-agents-cli-*\` skills.

---

## 1. TOOL & INTERFACE DESIGN
- **Single Responsibility:** Tools must be granular, highly focused, and represent discrete "tasks" rather than thin wrappers around complex enterprise APIs.
- **Contracts & Schemas:** Every tool must expose a rigid schema (\`inputSchema\` and \`outputSchema\` are required) and leverage behavior annotations (\`destructiveHint\`, \`readOnlyHint\`, and \`idempotentHint\` where applicable).
- **Defensive Design:** Tools must return concise output payloads to avoid context bloat, and provide highly descriptive, actionable error messages that instruct the LLM on how to self-correct.
- **UI Standard (A2UI):** For interactive outputs (e.g., flight comparisons or visual calendars), utilize the Agent-to-User Interface (A2UI v0.9) open standard via \`a2ui-agent-sdk\` to generate dynamic, declarative UI components (Cards, Lists, Buttons, ChoicePickers) rather than streaming raw JSON.

## 2. CONTEXT & MEMORY
- **Progressive Disclosure:** Do not bloat the system prompt. Maintain a tight \`AGENTS.md\` index of skill metadata. Load full procedural workflows (\`SKILL.md\`) and supporting references dynamically only when specific activation triggers are matched.
- **Short-Term Sessions:** Manage conversation history in a robust Session Store (backed by Firestore, Spanner, or Vertex AI Agent Engine) capable of tracking chronological event chains and supporting long-running, multi-day operations (up to 7 days) with pause/resume hooks.
- **Long-Term Memories:** Connect the system to a background Memory Manager (Vertex AI Agent Engine Memory Bank). Implement an asynchronous LLM-driven ETL pipeline to automatically Extract and Consolidate user preferences, resolving conflicts and deleting stale data.
- **Memory-as-a-Tool:** Expose memory retrieval as an explicit tool (\`load_memory_tool\`) to allow the model to dynamically fetch context on-demand rather than statically pre-loading all memories on every turn.

## 3. ORCHESTRATION & LOGIC
- **Specialization over Monoliths:** Avoid a single "Swiss Army knife" prompt. Decompose the Travel Planner into a structured Directed Acyclic Graph (DAG) or a team of specialized sub-agents:
  - **Querying Agent:** Retrieves raw travel data and inventory.
  - **Reporting Agent:** Synthesizes itinerary options.
  - **Critiquing & Learning Agent:** Inspects constraints (e.g., budget, compliance) and refines the output.
- **Handoff & State:** Use a decoupled state routing model (File Message Bus) to pass structured schema references or file URIs between nodes instead of accumulating execution logs in the active prompt context.
- **Authority & Guardrails:** Enforce the Read-Only, Draft-Only, and Action-Allowed authority ladder. High-risk operations (e.g., booking flights or charging cards) must utilize Just-In-Time (JIT) hyper-restricted ephemeral credentials and halt execution to request explicit Human-in-the-Loop (HITL) authorization.

## 4. OBSERVABILITY & TRACING
- **OpenTelemetry Distributed Tracing:** Instrument every component using OTel-compliant telemetry natively supported on GCP (Cloud Trace). All traces must record explicit span blocks for \`agent_run\`, \`agent_think\` (including chain-of-thought and tokens), and \`execute_tool\` linked by a unique \`trace_id\`.
- **Dual Dashboards:** Configure separate dashboards in Cloud Monitoring:
  - **Operational Dashboard:** Track system health (P99 latency, HTTP error rates, token-burn budgets, API costs).
  - **Quality Dashboard:** Track agent reasoning health (factual correctness, helpfulness, trajectory adherence, and hallucination rates).
- **Dynamic Tail-Based Sampling:** Set up real-time online monitors to catch reasoning drift and alerts. Trace 10% of successful flows but capture 100% of traces containing exceptions, tool failures, or high-iteration loops.

## 5. INFRASTRUCTURE & CI/CD
- **Infrastructure as Code (IaC):** All infrastructure (Agent Platform, Cloud Run containers, AlloyDB state databases, Pub/Sub channels, Secret Manager) must be defined programmatically using version-controlled Terraform scripts.
- **Evaluation-Gated Pipeline:** Build a multi-phase CI/CD pipeline using Google Cloud Build:
  - **Pre-Merge (CI):** Automatically run code linters, security scanners (SCA/SAST to block slopsquatting or unvetted public packages), and execute the agent evaluation suite. Evaluate the agent's behavior against a version-controlled "Golden Dataset" of prompts, asserting strict threshold scores for F1-score, trajectory adherence, and pass^k accuracy.
  - **Post-Merge (CD):** Build and deploy containerized services to Staging. Run load testing and automate gradual rollout strategies (Canary with 1% initial traffic, Blue-Green, or A/B testing) for production releases.
- **Sandbox Security:** Execute all dynamically generated scripts or code evaluation tools in secure, network-isolated, ephemeral Agent Sandboxes (e.g., gVisor) that reset state between runs and restrict file-system access via strict allowlists.
