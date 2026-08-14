from google.adk.workflow import Workflow
from google.adk.agents import LlmAgent
from google.adk.models import Gemini

orch = LlmAgent(name="orch", model=Gemini(model="gemini"))
q = LlmAgent(name="q", model=Gemini(model="gemini"))

Workflow(name="w", edges=[
    ('START', orch),
    (orch, {"retry": q})
])
print("Success")
