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

import contextlib
import json
import logging
import os
import re
from typing import Any, ClassVar

import google.auth
from google.adk.cli.api_server import _setup_instrumentation_lib_if_installed
from google.adk.telemetry.google_cloud import get_gcp_exporters, get_gcp_resource
from google.adk.telemetry.setup import maybe_set_otel_providers
from opentelemetry import trace

logger = logging.getLogger(__name__)


class PIIRedactor:
    """Detects and redacts sensitive personally identifiable information (PII) from strings and structured objects."""

    PATTERNS: ClassVar[list[tuple[re.Pattern, str]]] = [
        # Email addresses
        (
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}\b"),
            "[REDACTED_EMAIL]",
        ),
        # Credit / debit card numbers (13 to 19 digits)
        (re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{15,16}\b"), "[REDACTED_CARD]"),
        # API Keys, secrets, or bearer tokens
        (
            re.compile(
                r"\b(?:AIza[0-9A-Za-z-_]{20,}|Bearer\s+[A-Za-z0-9-_.]{20,}|sk-[0-9A-Za-z]{20,})\b"
            ),
            "[REDACTED_SECRET]",
        ),
        # Social Security Numbers (SSN)
        (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
        # US / International phone numbers (with optional +country code)
        (
            re.compile(r"(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
            "[REDACTED_PHONE]",
        ),
    ]

    @classmethod
    def redact_text(cls, text: str) -> str:
        """Redact PII from raw string."""
        if not isinstance(text, str):
            return text
        redacted = text
        for pattern, replacement in cls.PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted

    @classmethod
    def redact(cls, data: Any) -> Any:
        """Recursively redact PII from strings, dictionaries, lists, and objects."""
        if isinstance(data, str):
            return cls.redact_text(data)
        if isinstance(data, dict):
            return {k: cls.redact(v) for k, v in data.items()}
        if isinstance(data, list):
            return [cls.redact(item) for item in data]
        if hasattr(data, "model_dump"):
            return cls.redact(data.model_dump())
        return data


def redact_pii(data: Any) -> Any:
    """Public helper for PII redaction."""
    return PIIRedactor.redact(data)


def record_action_telemetry(
    action_name: str,
    intent: str,
    inputs: Any,
    outcome: str,
    outcome_details: Any,
    is_aligned: bool = True,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record intent vs outcome for agent actions in OpenTelemetry spans and structured logs.

    Args:
        action_name: Name of the agent action or tool being executed.
        intent: The explicit stated goal or intent of the action.
        inputs: Input arguments passed to the action (will be PII redacted).
        outcome: High-level outcome ('SUCCESS', 'FAILED', 'RETRY_REQUIRED', 'GUARDRAIL_BLOCKED').
        outcome_details: Descriptive summary or structured result of what occurred.
        is_aligned: Boolean indicating whether the outcome satisfied the intent.
        metadata: Optional additional contextual attributes.
    """
    redacted_inputs = redact_pii(inputs)
    redacted_details = redact_pii(outcome_details)

    # Attach attributes to active OpenTelemetry span
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.set_attribute("travel_planner.action.name", str(action_name))
        current_span.set_attribute("travel_planner.action.intent", str(intent))
        current_span.set_attribute("travel_planner.action.outcome", str(outcome))
        current_span.set_attribute(
            "travel_planner.action.outcome_details",
            json.dumps(redacted_details)
            if isinstance(redacted_details, (dict, list))
            else str(redacted_details),
        )
        current_span.set_attribute("travel_planner.action.is_aligned", bool(is_aligned))

    # Emit structured log
    payload = {
        "event": "agent_action_evaluation",
        "action": action_name,
        "intent": intent,
        "inputs": redacted_inputs,
        "outcome": outcome,
        "outcome_details": redacted_details,
        "is_aligned": is_aligned,
        "metadata": redact_pii(metadata) if metadata else {},
    }
    logger.info("Agent action evaluated: %s", json.dumps(payload))


class ActionTracker:
    """Helper context object to track intent vs outcome during execution."""

    def __init__(self, action_name: str, intent: str, inputs: Any):
        self.action_name = action_name
        self.intent = intent
        self.inputs = inputs
        self.outcome = "SUCCESS"
        self.outcome_details = "Action completed successfully"
        self.is_aligned = True
        self.metadata: dict[str, Any] = {}

    def set_outcome(self, outcome: str, outcome_details: Any, is_aligned: bool = True):
        self.outcome = outcome
        self.outcome_details = outcome_details
        self.is_aligned = is_aligned


@contextlib.contextmanager
def trace_action(action_name: str, intent: str, inputs: Any = None):
    """Context manager to record intent vs outcome for an action."""
    tracker = ActionTracker(action_name, intent, inputs)
    try:
        yield tracker
    except Exception as exc:
        tracker.set_outcome("FAILED", f"Unhandled exception: {exc!s}", is_aligned=False)
        record_action_telemetry(
            action_name=tracker.action_name,
            intent=tracker.intent,
            inputs=tracker.inputs,
            outcome=tracker.outcome,
            outcome_details=tracker.outcome_details,
            is_aligned=tracker.is_aligned,
            metadata=tracker.metadata,
        )
        raise
    else:
        record_action_telemetry(
            action_name=tracker.action_name,
            intent=tracker.intent,
            inputs=tracker.inputs,
            outcome=tracker.outcome,
            outcome_details=tracker.outcome_details,
            is_aligned=tracker.is_aligned,
            metadata=tracker.metadata,
        )


def setup_telemetry() -> str | None:
    """Configure GenAI prompt/response logging via OpenTelemetry."""
    # Keep full prompts/responses out of trace span attributes (use GenAI logging instead).
    os.environ.setdefault("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "false")

    bucket = os.environ.get("LOGS_BUCKET_NAME")
    capture_content = os.environ.get(
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "false"
    )
    if bucket and capture_content != "false":
        logging.info(
            "Prompt-response logging enabled - mode: NO_CONTENT (metadata only, no prompts/responses)"
        )
        os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "NO_CONTENT"
        os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT", "jsonl")
        os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK", "upload")
        os.environ.setdefault(
            "OTEL_SEMCONV_STABILITY_OPT_IN", "gen_ai_latest_experimental"
        )
        commit_sha = os.environ.get("COMMIT_SHA", "dev")
        os.environ.setdefault(
            "OTEL_RESOURCE_ATTRIBUTES",
            f"service.namespace=travel-planner,service.version={commit_sha}",
        )
        path = os.environ.get("GENAI_TELEMETRY_PATH", "completions")
        os.environ.setdefault(
            "OTEL_INSTRUMENTATION_GENAI_UPLOAD_BASE_PATH",
            f"gs://{bucket}/{path}",
        )
    else:
        logging.info(
            "Prompt-response logging disabled (set LOGS_BUCKET_NAME=gs://your-bucket and OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=NO_CONTENT to enable)"
        )

    # Set up OpenTelemetry exporters for Cloud Trace and Cloud Logging
    try:
        credentials, project_id = google.auth.default()
        otel_hooks = get_gcp_exporters(
            enable_cloud_tracing=True,
            enable_cloud_metrics=False,
            enable_cloud_logging=True,
            google_auth=(credentials, project_id),
        )
        otel_resource = get_gcp_resource(project_id)
        maybe_set_otel_providers(
            otel_hooks_to_setup=[otel_hooks],
            otel_resource=otel_resource,
        )
    except Exception as e:
        logging.warning("Could not setup GCP OTEL exporters: %s", e)

    # Set up GenAI SDK instrumentation
    _setup_instrumentation_lib_if_installed()

    return bucket
