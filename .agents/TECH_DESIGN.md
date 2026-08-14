# Technical Design Document: Travel Planner Agent System

## 1. System Architecture & Google Cloud Services
*   **Execution Parity:** The system maintains 100% parity between local and production environments. Both environments execute real public web searches without relying on mock APIs or stubs.
*   **Orchestration, Compute & Deployment (Frontend & Backend):** 
    *   **Backend (Agent API):** Deployed as stateless, containerized microservices on **Google Cloud Run**. The backend exposes REST/gRPC endpoints that stream A2UI states, handle state routing via the File Message Bus, and interface directly with Vertex AI Agent Engine.
    *   **Frontend (A2UI Web App):** A Next.js/React Single Page Application (SPA), deployed via **Firebase Hosting** (or lightweight Cloud Run containers). The frontend acts purely as a presentation layer, dynamically rendering the schema-driven A2UI JSON payloads returned by the Agent Backend.
    *   **Local Development:** Both frontend and backend are emulated locally via `agents-cli serve` alongside Docker Desktop.
*   **LLM Foundation (2026 Models):** 
    *   `gemini-2.5-pro`: Orchestrator Agent & Auditor Agent (for complex reasoning and multi-step planning).
    *   `gemini-2.5-flash`: Querying Agent & Reporting Agent (for fast data retrieval and A2UI UI generation).
*   **State & Memory Management:** GCP Firestore as the immutable Session Store for interactions and A2UI states. Vertex AI Agent Engine Memory Bank for long-term user preferences.

## 2. Agent Definitions (DAG Orchestration)
The system operates as a Directed Acyclic Graph (DAG) of specialized sub-agents:
1.  **Orchestrator Agent (`gemini-3.1-pro`):** Analyzes main user intent, manages session contextualization, and routes file pointers using the **File Message Bus**.
2.  **Querying Agent (`gemini-3.6-flash`):** Strict data retriever. Translates requests into search queries and uses public Google Search tools to fetch real-world flights, hotels, and pricing directly from the consumer internet. Uses NO mock endpoints.
3.  **Auditor Agent (`gemini-3.1-pro`):** Inspects the raw public search results to ensure they align with the personal traveler's stated preferences (e.g., budget, layover limits, hotel stars).
4.  **Reporting Agent (`gemini-3.6-flash`):** UI synthesizer generating Agent-to-User Interface (A2UI) declarative output formatting.

## 3. Tool & Skill Definitions
All tools use strict `inputSchema`/`outputSchema` typing.
*   **`search_public_travel_tool` (readOnly)**
    *   *Input:* `query: string`
    *   *Action:* Executes public Google Search to scrape and return real-world flight/hotel data.
*   **`validate_preferences_tool` (idempotent)**
    *   *Input:* `searchDataURI: string, preferences: UserProfile`
    *   *Output:* `ValidationReport { isAligned: boolean, approvedDataURI: string }`
*   **`generate_vibe_diff_tool` (readOnly)**
    *   *Input:* `approvedDataURI: string`
    *   *Output:* `VibeDiff { plainTextSummary, estimatedCost, deepLinks }`

## 4. API Definitions (Public Search Integration)
There are NO mock APIs and NO third-party/internal GDS tools (e.g., Amadeus) for this system.
*   **Data Strategy:** The Querying Agent will utilize native public web search integration (via Vertex Web Search Grounding or Google Custom Search API).
*   **Behavioral Parity:** Because there are no mock systems, executing the agent locally on a laptop produces the exact same search fidelity as executing it in the production GCP environment. Users simply receive direct deep links to public booking engines to securely complete their transactions.

## 5. Observability, Monitoring & Evaluation
*   **OpenTelemetry & Cloud Trace:** Every agent execution, including reasoning cycles (`agent_think`) and HTTP search API calls (`execute_tool`), must be instrumented using OpenTelemetry. Traces will be forwarded to GCP Cloud Trace with a unified `trace_id`.
*   **Dual Dashboards (Cloud Monitoring):**
    *   **Operational Dashboard:** Tracks token usage, search API latency (P99), and HTTP failure rates.
    *   **Quality Dashboard:** Measures trajectory accuracy and safety guardrail adherence.
*   **Eval-Driven CI/CD:** Google Cloud Build pipelines will enforce evaluation gates against a version-controlled "Golden Dataset" of personal travel prompts, scoring the agent's ability to fetch accurate public travel data without hallucinations prior to production deployments.
