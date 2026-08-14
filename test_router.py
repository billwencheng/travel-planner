def auditor_router(node_input: dict) -> str:
    if node_input.get("needsRetry"):
        return "retry"
    return "approved"
