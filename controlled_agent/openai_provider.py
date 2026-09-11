"""Responses API transport. No redirects, proxies, retries, or hidden model aliases."""
from dataclasses import dataclass
import json
import os
import urllib.request
from .contracts import validate
from .manifests import encoded
from .redaction import reject_secrets, clean

ENDPOINT = "https://api.openai.com/v1/responses"


class ProviderRejected(ValueError):
    def __init__(self, reason, data):
        super().__init__(reason)
        self.evidence = clean({"resolved_model": data.get("model"), "response_id": data.get("id"),
                               "usage": data.get("usage"), "service_tier": data.get("service_tier"),
                               "provider_status": data.get("status")})


@dataclass(frozen=True)
class LivePermit:
    task_id: str
    model_calls: int


def authorize(task, *, live, approve, confirmation):
    if not live or not approve or os.environ.get("CONTROLLED_AGENT_LIVE_ENABLED") != "1":
        raise ValueError("live execution disabled: flags and environment switch required")
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("API key missing")
    if task["network_policy"] != "api.openai.com":
        raise ValueError("task network policy denies OpenAI")
    if any(task["budget"].get(k, 0) <= 0 for k in ("input_tokens", "output_tokens", "model_calls")):
        raise ValueError("positive live budgets required")
    if confirmation != "RUN LIVE " + task["task_id"]:
        raise ValueError("live confirmation phrase mismatch")
    return LivePermit(task["task_id"], task["budget"]["model_calls"])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("API redirect forbidden")


class OpenAIProvider:
    name = "openai"

    def __init__(self, permit, *, transport=None):
        if not isinstance(permit, LivePermit):
            raise ValueError("live permit required")
        self.permit = permit
        self.transport = transport or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()).open

    def complete(self, *, model, instructions, history, tools, schema, key, max_output_tokens, timeout):
        if model not in {"gpt-5.6-sol", "gpt-6-astra"}:
            raise ValueError("unsupported exact model; no fallback")
        if model == "gpt-6-astra" and tools:
            raise ValueError("reviewer tools forbidden")
        if os.environ.get("CONTROLLED_AGENT_LIVE_ENABLED") != "1" or not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("live environment authorization missing")
        payload = {"model": model, "instructions": instructions, "input": history,
                   "reasoning": {"effort": "high"}, "tools": tools, "tool_choice": "auto" if tools else "none",
                   "parallel_tool_calls": False, "store": False, "include": ["reasoning.encrypted_content"],
                   "text": {"format": {"type": "json_schema", "name": "agent_result", "strict": True, "schema": schema}},
                   "max_output_tokens": max_output_tokens}
        reject_secrets(payload)
        request = urllib.request.Request(ENDPOINT, data=encoded(payload), method="POST",
                    headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "Content-Type": "application/json", "Idempotency-Key": key})
        try:
            with self.transport(request, timeout=min(60, timeout)) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise ValueError("response too large")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("provider JSON must be an object")
        except Exception:
            raise ValueError("AMBIGUOUS_PROVIDER_ATTEMPT: transport/response failure; no automatic retry") from None
        if data.get("model") != model:
            raise ProviderRejected("resolved-model mismatch; no fallback", data)
        if data.get("status") != "completed" or not isinstance(data.get("id"), str) or not isinstance(data.get("output"), list):
            raise ProviderRejected("provider response incomplete/refused/invalid; inspect new run separately", data)
        reject_secrets(data)
        return data
