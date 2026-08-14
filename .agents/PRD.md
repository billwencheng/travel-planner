# Travel Planner - Product Requirement Document (PRD)

## 1. EXECUTIVE SUMMARY & TARGET USER PERSONA
**Product Vision:** An autonomous, highly capable travel assistant that synthesizes personalized flight and hotel itineraries for personal vacations and trips.

**Primary Persona:** The "Personal Travel User" who desires a simplified, end-to-end booking experience that finds great vacation deals and unique travel suggestions.

**User Pain Points:** 
- Navigating fragmented booking platforms and comparing dozens of tabs.
- Tracking multi-segment itinerary changes.
- Spending hours researching flights, hotels, and local attractions manually.

## 2. CORE USER EPIC & USER JOURNEYS (MVP SCOPE)
**Epic 1: Flight & Hotel Search via Public Web**
- **User Journey:** The user requests a trip (e.g., "SFO to JFK on Sept 15, returning Sept 20"). The system uses public Google Search engine capabilities to fetch real-time public travel information, filter options based on the traveler's stated preferences, and present a curated list of flights and hotels.

**Epic 2: Interactive Itinerary Curation (A2UI)**
- **User Journey:** The user receives a beautifully formatted, interactive flight and hotel proposal. They can click "Approve" to freeze the options or prompt the system to find alternatives (e.g., "Show me a flight leaving 2 hours later").

**Epic 3: Just-In-Time Booking Handoff**
- **User Journey:** Since search relies on public information, the system presents a final "Vibe Diff" (a plain-English summary of the selected options and estimated costs) and provides direct deep links for the user to complete the booking on public consumer platforms (e.g., Google Flights or direct airline/hotel sites).

## 3. STRICT SCOPE BOUNDARIES (IN-SCOPE VS. OUT-OF-SCOPE)
To prevent feature creep, the following boundaries are defined:

**IN-SCOPE for MVP:**
- Multi-agent collaboration for querying public travel info via Google Search engine, synthesizing options, and generating summaries.
- Exact parity between Local and Production execution (both rely on real public search, no mock APIs).
- Persistence of user travel session state (active itineraries, pending approvals).
- Expressive Agent-to-User Interface (A2UI) component generation.

**OUT-OF-SCOPE for MVP (Post-MVP):**
- Direct credit card payment processing (users will be handed off to public booking URLs).
- Real-time flight delay tracking and push notifications.
- Specialized corporate policy enforcement (the system is for individual/personal travel).

## 4. PRODUCT QUALITY, SAFETY & COMPLIANCE METRICS
The engineering team's evaluations (Golden Dataset) must assert the following KPIs:
- **Search Fidelity:** The system must accurately retrieve real flight and hotel data from public search without hallucinating schedules or prices.
- **User Latency Target:** Itinerary synthesis must return initial interactive cards (A2UI) within 8 seconds.
- **Safety & Guardrails:** The system must safely link the user out without unintentionally locking them into unapproved fake bookings.
