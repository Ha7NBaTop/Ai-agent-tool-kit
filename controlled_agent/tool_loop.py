"""Stateless Responses loop with durable replies and idempotent local calls."""
import json
from .config import load, resource
from .contracts import validate
from .manifests import encoded, object_hash
from .redaction import reject_secrets
from .router import route
from .tools import TOOL_DEFINITIONS
from .openai_provider import ProviderRejected


def result_from(response):
    text = []
    for item in response["output"]:
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "refusal":
                    raise ValueError("model refused request")
                if content.get("type") == "output_text":
                    text.append(content["text"])
    if not text:
        raise ValueError("no structured final response")
    return json.loads("".join(text))


def run_loop(role, packet, provider, tools, store, budget, ledger, cycle):
    config = route(role)
    definitions = TOOL_DEFINITIONS if role == "writer" else []
    schema = load("schemas/worker_result.schema.json" if role == "writer" else "schemas/reviewer_result.schema.json")
    instructions = resource("prompts/implementer.md" if role == "writer" else "prompts/critical_reviewer.md")
    history = [{"role": "user", "content": json.dumps({"task_packet": packet}, ensure_ascii=False, sort_keys=True)}]
    turn = 0
    while True:
        budget.check()
        slot = f"{role}:{cycle}:{turn}"
        request = {"model": config["model"], "instructions": instructions, "history": history, "tools": definitions, "schema": schema}
        signature = object_hash(request)
        saved = store.data["calls"].get(slot)
        if saved:
            if saved["request_hash"] != signature:
                raise ValueError("resume request changed; refuse replay")
            if saved["status"] != "DONE":
                raise ValueError("AMBIGUOUS_PROVIDER_ATTEMPT: pending call; no automatic retry")
            response = saved["response"]
        else:
            reserved, output_cap = budget.reserve_call(len(encoded(request)))
            key = object_hash({"run": store.data["task_hash"], "mode": store.data["mode"], "slot": slot, "request": signature})
            record = {"status": "PENDING", "sequence": len(store.data["calls"]), "request_hash": signature, "idempotency_key": key,
                      "provider": provider.name, "requested_model": config["model"], "reasoning_effort": "high",
                      "reserved_input": reserved, "output_cap": output_cap}
            store.data["calls"][slot] = record
            store.save()
            try:
                response = provider.complete(**request, key=key, max_output_tokens=output_cap, timeout=budget.remaining_seconds())
            except ProviderRejected as error:
                record.update(status="REJECTED", **error.evidence)
                store.save()
                raise
            if provider.name == "openai" and response.get("model") != config["model"]:
                raise ValueError("resolved-model mismatch")
            reject_secrets(response)
            # Persist reply + settled counters in one checkpoint; avoid replay double charging.
            usage = response.get("usage", {})
            if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("input_tokens", "output_tokens")):
                raise ValueError("invalid usage; reservation retained")
            budget.usage["input_tokens"] += usage["input_tokens"] - reserved
            budget.usage["output_tokens"] += usage["output_tokens"] - output_cap
            record.update(status="DONE", response=response, resolved_model=response["model"], response_id=response["id"], usage=usage,
                          service_tier=response.get("service_tier"))
            store.save(); budget.check()
            ledger.append({"call": slot, "provider": provider.name, "requested_model": config["model"], "resolved_model": response["model"], "response_id": response["id"], "usage": usage})
        calls = [item for item in response["output"] if item.get("type") == "function_call"]
        if calls:
            if role != "writer":
                raise ValueError("reviewer attempted mutation/tool call")
            if len(calls) != 1:
                raise ValueError("parallel/batched tool calls forbidden")
            # Preserve reasoning items including encrypted_content for store:false continuity.
            history.extend(response["output"])
            call = calls[0]
            arguments = json.loads(call["arguments"])
            output = tools.invoke(role, call["name"], arguments, slot + ":" + call["call_id"])
            history.append({"type": "function_call_output", "call_id": call["call_id"], "output": json.dumps(output, ensure_ascii=False, sort_keys=True)})
            turn += 1
            continue
        try:
            result = result_from(response)
            validate(result, schema)
            if role == "reviewer":
                if (result["verdict"] == "NO_FINDINGS" and (result["findings"] or result["unresolved"])) or (result["verdict"] == "FINDINGS" and not result["findings"]):
                    raise ValueError("inconsistent reviewer verdict/findings")
                for finding in result["findings"]:
                    if finding["file"] not in packet["files"]:
                        raise ValueError("finding refers to file outside frozen packet")
            return result
        except (ValueError, KeyError, TypeError) as error:
            marker = slot + ":schema-repair"
            if marker not in store.data:
                budget.repair()
                store.data[marker] = str(error)
                store.save()
            history.extend(response["output"])
            history.append({"role": "user", "content": "Correct the structured final output. Validation error: " + store.data[marker]})
            turn += 1
