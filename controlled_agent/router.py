from .config import load


def route(role):
    if role not in {"writer", "reviewer"}:
        raise ValueError("unknown role; delegation depth is fixed at one")
    expected = "gpt-5.6-sol" if role == "writer" else "gpt-6-astra"
    config = load("config/models.json")["worker_hard_case" if role == "writer" else "critical_reviewer"]
    if config != {"provider": "openai", "model": expected, "reasoning_effort": "high", "write_access": role == "writer", "fallback": None}:
        raise ValueError("route configuration differs from exact contract; no fallback")
    return config
