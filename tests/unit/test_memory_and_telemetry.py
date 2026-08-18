# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest

from app.app_utils.memory import (
    HistoryCompactor,
    consolidate_user_memory_async,
    get_user_memory,
)
from app.app_utils.telemetry import (
    redact_pii,
    trace_action,
)
from app.tools import (
    generate_vibe_diff_tool,
    load_memory_tool,
    search_public_travel_tool,
    validate_preferences_tool,
)


class MockToolContext:
    """Mock ToolContext for unit testing tools in isolation."""

    def __init__(self):
        self.artifacts = {}
        self.state = {}

    async def save_artifact(self, filename: str, part):
        self.artifacts[filename] = part

    async def load_artifact(self, filename: str):
        return self.artifacts.get(filename)


def test_pii_redaction_strings():
    raw_text = (
        "My email is traveler.jane@example.com and phone is +1-555-867-5309. "
        "Card: 4111-2222-3333-4444, SSN: 123-45-6789, Token: AIzaSyD3x918237abcde123456789012345."
    )
    redacted = redact_pii(raw_text)
    assert "[REDACTED_EMAIL]" in redacted
    assert "traveler.jane@example.com" not in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert "555-867-5309" not in redacted
    assert "[REDACTED_CARD]" in redacted
    assert "4111-2222-3333-4444" not in redacted
    assert "[REDACTED_SSN]" in redacted
    assert "[REDACTED_SECRET]" in redacted


def test_pii_redaction_nested_structures():
    data = {
        "user": "Alice",
        "contacts": ["alice@work.org", "+1 (212) 555-0199"],
        "payment": {"card_number": "5500 0000 0000 0004", "billing_name": "Alice"},
    }
    redacted = redact_pii(data)
    assert redacted["contacts"][0] == "[REDACTED_EMAIL]"
    assert redacted["contacts"][1] == "[REDACTED_PHONE]"
    assert redacted["payment"]["card_number"] == "[REDACTED_CARD]"
    assert redacted["user"] == "Alice"


def test_intent_vs_outcome_telemetry():
    with trace_action(
        "plan_vacation", "Formulate travel plan", {"destination": "Tokyo"}
    ) as tracker:
        tracker.set_outcome("SUCCESS", "Plan formulated with 2 travelers")
        assert tracker.outcome == "SUCCESS"
        assert tracker.is_aligned is True


def test_history_compactor():
    messages = [
        {
            "role": "user",
            "text": "I want to travel from NYC to MIA on 2026-10-10 for 2 travelers.",
        },
        {"role": "assistant", "text": "Got it. Let me check flight options for you."},
        {"role": "user", "text": "Also I prefer Delta Airlines and 4 star hotels."},
        {"role": "assistant", "text": "I will include Delta and 4 star hotels."},
        {"role": "user", "text": "Is there a pool at the hotel?"},
        {"role": "assistant", "text": "Yes, Grand Hyatt has an outdoor pool."},
        {"role": "user", "text": "What about breakfast?"},
        {"role": "assistant", "text": "Breakfast is included."},
        {"role": "user", "text": "Great, please finalize the plan."},
        {"role": "assistant", "text": "Finalizing now."},
    ]
    compacted = HistoryCompactor.compact_messages(messages, max_active_turns=4)
    # Length should be 1 (first) + 1 (compacted summary) + 4 (recent) = 6
    assert len(compacted) == 6
    assert compacted[0]["text"] == messages[0]["text"]
    assert "[Compacted Conversation Context]" in compacted[1]["text"]


@pytest.mark.asyncio
async def test_memory_consolidation_async():
    user_id = "test_user_memory_001"
    session_text = (
        "I have a budget of $1200, prefer 5 star hotel and direct flights with United."
    )
    updated = await consolidate_user_memory_async(user_id, session_text)
    assert updated["max_budget"] == 1200
    assert updated["preferred_hotel_stars"] == 5
    assert updated["layover_limits"] == 0
    assert "United Airlines" in updated["preferred_airlines"]

    retrieved = get_user_memory(user_id)
    assert retrieved["max_budget"] == 1200


@pytest.mark.asyncio
async def test_search_tool_defensive_validation():
    ctx = MockToolContext()

    # Missing origin
    err = await search_public_travel_tool("", "MIA", "2026-10-10", "2026-10-15", ctx)
    assert err["status"] == "error"
    assert "recovery_instructions" in err
    assert err["error_code"] == "MISSING_ORIGIN"

    # Identical origin and destination
    err2 = await search_public_travel_tool(
        "NYC", "NYC", "2026-10-10", "2026-10-15", ctx
    )
    assert err2["status"] == "error"
    assert err2["error_code"] == "IDENTICAL_ORIGIN_DESTINATION"

    # Valid search
    success = await search_public_travel_tool(
        "NYC", "MIA", "2026-10-10", "2026-10-15", ctx
    )
    assert success["status"] == "success"
    assert "searchDataURI" in success


@pytest.mark.asyncio
async def test_validate_preferences_tool_defensive_recovery():
    ctx = MockToolContext()
    # Execute search to populate artifact
    search_res = await search_public_travel_tool(
        "NYC", "MIA", "2026-10-10", "2026-10-15", ctx
    )
    uri = search_res["searchDataURI"]

    # Budget violation test: budget = $200 (flight is $295 + hotel)
    report = await validate_preferences_tool(
        uri, budget=200, preferred_hotel_stars=3, layover_limits=1, tool_context=ctx
    )
    assert report.isAligned is False
    assert "exceeds" in report.violationReason
    assert report.recoveryInstructions is not None

    # Star rating violation test: requested 5 stars, mock hotel has 4 stars
    report_stars = await validate_preferences_tool(
        uri, budget=2000, preferred_hotel_stars=5, layover_limits=1, tool_context=ctx
    )
    assert report_stars.isAligned is False
    assert "below requested" in report_stars.violationReason

    # Aligned test: budget = $2000, 4 stars, 1 layover
    report_ok = await validate_preferences_tool(
        uri, budget=2000, preferred_hotel_stars=4, layover_limits=1, tool_context=ctx
    )
    assert report_ok.isAligned is True
    assert report_ok.approvedDataURI == uri


@pytest.mark.asyncio
async def test_generate_vibe_diff_and_memory_tools():
    ctx = MockToolContext()
    search_res = await search_public_travel_tool(
        "NYC", "MIA", "2026-10-10", "2026-10-15", ctx
    )
    uri = search_res["searchDataURI"]

    vibe = await generate_vibe_diff_tool(uri, ctx)
    assert vibe.estimatedCost > 0
    assert len(vibe.flights) > 0
    assert len(vibe.hotels) > 0
    assert len(vibe.deepLinks) > 0

    mem = await load_memory_tool("alice_123", ctx)
    assert "preferred_hotel_stars" in mem
