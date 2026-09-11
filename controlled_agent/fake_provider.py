"""Scripted offline fixture. Never claims a real model was invoked."""
import json


def message(value):
    return {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": json.dumps(value)}]}


class FakeProvider:
    name = "fake"

    def complete(self, *, model, instructions, history, tools, schema, key, max_output_tokens, timeout):
        role = "writer" if tools else "reviewer"
        outputs = [item for item in history if item.get("type") == "function_call_output"]
        if role == "writer" and not outputs:
            output = [{"type": "function_call", "call_id": "fake_create", "name": "create_file",
                       "arguments": json.dumps({"path": "output/hello.txt", "content": "Hello, controlled agent!\n"})}]
        elif role == "writer" and len(outputs) == 1:
            output = [{"type": "function_call", "call_id": "fake_check", "name": "run_check", "arguments": json.dumps({"profile": "hello"})}]
        elif role == "writer":
            output = [message({"status": "COMPLETE", "summary": "Scripted synthetic edit completed", "unresolved": []})]
        else:
            output = [message({"verdict": "NO_FINDINGS", "findings": [], "unresolved": []})]
        return {"id": "fake_" + key, "status": "completed", "model": "fake-" + role + "-v1", "provider": "fake",
                "output": output, "usage": {"input_tokens": 10, "output_tokens": 10}, "service_tier": "fake"}
