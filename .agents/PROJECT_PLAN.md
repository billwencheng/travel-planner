# Travel Planner - Project Execution Plan

This document outlines the phased delivery milestones, task breakdown, and acceptance criteria for the Personal Travel Planner MVP. It strictly adheres to the scope defined in `PRD.md` and the architecture in `TECH_DESIGN.md`.

---

## Phase 1: Infrastructure & Foundation Scaffolding
**Goal:** Establish the operational bedrock, CI/CD pipelines, and local vs. remote development environments.

*   **Task 1.1:** Setup Terraform configurations for GCP (Cloud Run, Firestore, Vertex AI Agent Engine, Secret Manager).
*   **Task 1.2:** Initialize GitHub/Cloud Build CI/CD pipelines with OpenTelemetry instrumentation capabilities.
*   **Task 1.3:** Configure local development environment (`agents-cli serve`, `.env.local`) to connect directly to GCP resources.

**Acceptance Criteria:**
- [x] Infrastructure configuration scaffolds correctly (verified via static review).
- [x] Local environment files configured properly for the Agent Engine and GCP Firestore.
- [x] OpenTelemetry CI integration and traces configured correctly.

---

## Phase 2: Core Agent DAG & State Management
**Goal:** Implement the multi-agent backbone and the File Message Bus state routing mechanism.

*   **Task 2.1:** Scaffold the Backend API (Cloud Run deployable format).
*   **Task 2.2:** Scaffold the four core agents (Orchestrator, Querying, Auditor, Reporting) using `gemini-2.5-pro` and `gemini-2.5-flash`.
*   **Task 2.3:** Implement the **File Message Bus** for stateless handoffs and Firestore Session integration.

**Acceptance Criteria:**
- [x] Orchestrator Agent can successfully receive a dummy user prompt and hand it off to the Querying Agent.
- [x] State handoffs pass file URI pointers (File Message Bus) rather than inflating token context.
- [x] Session history successfully persists and loads from Firestore.

---

## Phase 3: Public Search Integration (Data Retrieval)
**Goal:** Equip the Querying Agent with the capability to execute and parse real public internet searches.

*   **Task 3.1:** Implement `search_public_travel_tool` utilizing Google Custom Search / Vertex Grounding.
*   **Task 3.2:** Train the Querying Agent to translate user intents into highly structured search schema parameters.
*   **Task 3.3:** Parse unstructured HTML/search results into internal standardized Flight/Hotel JSON objects.

**Acceptance Criteria:**
- [x] `search_public_travel_tool` successfully queries live flight and hotel data from the public internet.
- [x] Zero reliance on mock APIs or third-party enterprise tools.
- [x] Results are accurately mapped into structured JSON without hallucinated pricing or times.

---

## Phase 4: Auditing, Guardrails & A2UI Synthesis
**Goal:** Implement the validation loop and synthesize complex data into declarative UI schemas.

*   **Task 4.1:** Implement the Auditor Agent and `validate_preferences_tool` to cross-reference search data against the user's personal travel preferences.
*   **Task 4.2:** Implement safety guardrails (halting off-topic or policy-violating prompts).
*   **Task 4.3:** Implement the Reporting Agent and `generate_vibe_diff_tool` to convert audited JSON into A2UI declarative payload standards.

**Acceptance Criteria:**
- [x] Auditor Agent correctly rejects itineraries that violate budget or layover preferences, initiating a retry.
- [x] Reporting Agent produces valid A2UI JSON schemas consisting of Cards, Lists, and deep-link Buttons.
- [x] "Vibe Diff" plain-text summaries are generated accurately based on finalized options.

---

## Phase 5: Frontend Development & Handoff
**Goal:** Create the presentation layer that the user physically interacts with.

*   **Task 5.1:** Scaffold Next.js/React SPA and deploy to Firebase Hosting.
*   **Task 5.2:** Build the dynamic UI rendering engine capable of parsing A2UI JSON components.
*   **Task 5.3:** Connect the frontend WebSocket or REST polling to the Backend Cloud Run endpoint.

**Acceptance Criteria:**
- [x] Web app successfully renders A2UI Cards (Flight & Hotel options) based on backend payloads.
- [x] Deep links inside the A2UI components successfully direct the user to public consumer booking platforms.
- [x] End-to-end latency from user prompt to initial A2UI rendering is under 8 seconds.

---

## Phase 6: System Evaluation, CI/CD Gating & MVP Launch
**Goal:** Ensure the system meets rigorous quality thresholds before marking MVP complete.

*   **Task 6.1:** Author the "Golden Dataset" of personal travel prompts targeting edge cases and safety bypass attempts.
*   **Task 6.2:** Integrate automated LLM-as-a-judge evaluations into the Cloud Build Pre-Merge CI pipeline.
*   **Task 6.3:** End-to-End manual quality assurance and MVP sign-off.

**Acceptance Criteria:**
- [x] Infrastructure deploys clean to a sandbox GCP project via `terraform apply` before MVP sign-off.
- [x] CI pipeline automatically rejects any PR that drops the "Trajectory Accuracy" or "Search Fidelity" heuristic below specific thresholds.
- [x] Quality Dashboard successfully captures agent reasoning loops.
- [x] MVP deployed to live production GCP environment.
