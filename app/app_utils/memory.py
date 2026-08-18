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

"""Context Bloat Management (History Compaction) and Long-Term Memory Consolidation."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from app.app_utils.telemetry import record_action_telemetry, redact_pii

logger = logging.getLogger(__name__)

# In-memory store for user memory profiles (fallback/local development)
_USER_MEMORY_STORE: dict[str, dict[str, Any]] = {}


class HistoryCompactor:
    """Manages context bloat by compacting long conversation histories while preserving critical trip context."""

    DEFAULT_MAX_ACTIVE_TURNS = 8

    @classmethod
    def compact_messages(
        cls,
        messages: list[dict[str, Any]],
        max_active_turns: int = DEFAULT_MAX_ACTIVE_TURNS,
    ) -> list[dict[str, Any]]:
        """Compact conversation history if message count exceeds max_active_turns.

        Keeps the first user message (original intent) and the most recent N turns,
        summarizing intermediate turns into a concise entity-preserving context block.

        Args:
            messages: List of message dictionaries with 'role' and 'text'/'parts'.
            max_active_turns: Number of recent turns to preserve in full detail.

        Returns:
            Compacted list of messages.
        """
        if len(messages) <= max_active_turns:
            return messages

        # Keep initial intent
        first_message = messages[0]
        # Keep recent turns
        recent_messages = messages[-max_active_turns:]

        # Intermediate turns to summarize
        intermediate_messages = messages[1:-max_active_turns]
        extracted_entities: dict[str, Any] = {}

        for msg in intermediate_messages:
            text = msg.get("text", "")
            if not text and isinstance(msg.get("parts"), list):
                text = " ".join(
                    p.get("text", "") for p in msg["parts"] if isinstance(p, dict)
                )

            # Extract travel parameters if mentioned
            origin_match = re.search(
                r"\bfrom\s+([A-Z]{3}|[A-Za-z\s]+?)(?=\s+to\b|\s+on\b|\s*,|\s*\.|\s*$)",
                text,
                re.IGNORECASE,
            )
            if origin_match and "origin" not in extracted_entities:
                extracted_entities["origin"] = origin_match.group(1).strip()

            dest_match = re.search(
                r"\bto\s+([A-Z]{3}|[A-Za-z\s]+?)(?=\s+from\b|\s+on\b|\s*,|\s*\.|\s*$)",
                text,
                re.IGNORECASE,
            )
            if dest_match and "destination" not in extracted_entities:
                extracted_entities["destination"] = dest_match.group(1).strip()

            travelers_match = re.search(
                r"(\d+)\s+(?:travelers?|passengers?|adults?|people)",
                text,
                re.IGNORECASE,
            )
            if travelers_match and "travelers" not in extracted_entities:
                extracted_entities["travelers"] = int(travelers_match.group(1))

        summary_parts = ["[Compacted Conversation Context]"]
        if extracted_entities:
            summary_parts.append(
                f"Previously established parameters: {json.dumps(extracted_entities)}."
            )
        summary_parts.append(
            f"({len(intermediate_messages)} intermediate turns compacted for context efficiency.)"
        )
        compacted_summary = " ".join(summary_parts)

        compacted_node = {
            "role": "system",
            "text": compacted_summary,
            "metadata": {
                "is_compacted_summary": True,
                "turn_count": len(intermediate_messages),
            },
        }

        return [first_message, compacted_node, *recent_messages]


class MemoryConsolidator:
    """Asynchronously extracts, resolves, and consolidates long-term traveler preferences."""

    @classmethod
    def get_user_memory(cls, user_id: str) -> dict[str, Any]:
        """Retrieve the consolidated memory profile for a user."""
        return _USER_MEMORY_STORE.get(
            user_id,
            {
                "user_id": user_id,
                "preferred_hotel_stars": 4,
                "max_budget": 1000,
                "layover_limits": 1,
                "preferred_airlines": ["Delta Airlines"],
                "notes": "Default traveler preferences",
            },
        )

    @classmethod
    def update_user_memory(
        cls, user_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Update and consolidate user memory, resolving conflicts."""
        current = cls.get_user_memory(user_id)
        current.update(updates)
        _USER_MEMORY_STORE[user_id] = current
        return current

    @classmethod
    async def consolidate_memory_async(
        cls,
        user_id: str,
        session_text: str,
    ) -> dict[str, Any]:
        """Asynchronously extract and consolidate traveler preferences in a background task."""
        # Yield execution to allow non-blocking background processing
        await asyncio.sleep(0.01)

        extracted_updates: dict[str, Any] = {}
        redacted_text = redact_pii(session_text)

        # 1. Budget extraction
        budget_match = re.search(
            r"\b(?:budget|max|limit)\s*(?:of|is|:)?\s*\$?(\d+)",
            redacted_text,
            re.IGNORECASE,
        )
        if budget_match:
            try:
                extracted_updates["max_budget"] = int(budget_match.group(1))
            except ValueError:
                pass

        # 2. Hotel stars extraction
        stars_match = re.search(
            r"(\d+)\s*(?:star|stars)\s*hotel", redacted_text, re.IGNORECASE
        )
        if stars_match:
            try:
                extracted_updates["preferred_hotel_stars"] = int(stars_match.group(1))
            except ValueError:
                pass

        # 3. Direct / Nonstop preference
        if re.search(
            r"\b(?:direct|nonstop|no layovers)\b", redacted_text, re.IGNORECASE
        ):
            extracted_updates["layover_limits"] = 0
        elif re.search(r"(\d+)\s*layover", redacted_text, re.IGNORECASE):
            layover_m = re.search(r"(\d+)\s*layover", redacted_text, re.IGNORECASE)
            if layover_m:
                extracted_updates["layover_limits"] = int(layover_m.group(1))

        # 4. Airline preference
        for airline in [
            "Delta",
            "United",
            "American",
            "JetBlue",
            "Emirates",
            "ANA",
            "Air France",
        ]:
            if re.search(rf"\b{airline}\b", redacted_text, re.IGNORECASE):
                extracted_updates["preferred_airlines"] = [f"{airline} Airlines"]

        if extracted_updates:
            consolidated = cls.update_user_memory(user_id, extracted_updates)
            record_action_telemetry(
                action_name="memory_consolidation_etl",
                intent="Asynchronously extract and consolidate traveler preferences into Memory Bank",
                inputs={"user_id": user_id, "snippet_length": len(session_text)},
                outcome="SUCCESS",
                outcome_details={
                    "consolidated_updates": extracted_updates,
                    "profile": consolidated,
                },
                is_aligned=True,
            )
            logger.info(
                "Memory consolidated for user %s: %s", user_id, extracted_updates
            )
            return consolidated

        return cls.get_user_memory(user_id)


def get_user_memory(user_id: str) -> dict[str, Any]:
    """Public helper to get user memory."""
    return MemoryConsolidator.get_user_memory(user_id)


async def consolidate_user_memory_async(
    user_id: str, session_text: str
) -> dict[str, Any]:
    """Public async helper to run memory consolidation in background."""
    return await MemoryConsolidator.consolidate_memory_async(user_id, session_text)
