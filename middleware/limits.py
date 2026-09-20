def tool_middleware(state):
    """Simple tool call limit check."""
    return {"allowed": True}


def Model_middleware(state):
    """Simple model call limit check."""
    return {"allowed": True} 