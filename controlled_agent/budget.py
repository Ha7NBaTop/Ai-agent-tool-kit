"""Persisted cumulative counters. Reserve worst-case input before network use."""
import time


class Exhausted(ValueError):
    pass


class Budget:
    def __init__(self, limits, store):
        self.limits, self.store = limits, store

    @property
    def usage(self):
        return self.store.data["usage"]

    def remaining_seconds(self):
        return self.limits["wall_seconds"] - (time.time() - self.store.data["started"])

    def check(self):
        if self.remaining_seconds() <= 0:
            raise Exhausted("wall-time budget exhausted")
        for k in ("input_tokens", "output_tokens", "model_calls", "tool_calls"):
            if self.usage[k] > self.limits[k]:
                raise Exhausted(k + " budget exhausted")

    def reserve_call(self, request_bytes):
        self.check()
        # UTF-8 byte count + explicit protocol margin, conservative for text JSON.
        reserve = request_bytes + 4096
        if self.usage["model_calls"] >= self.limits["model_calls"] or self.usage["input_tokens"] + reserve > self.limits["input_tokens"]:
            raise Exhausted("model-call/input budget insufficient for next request")
        output = min(self.limits["per_call_output_tokens"], self.limits["output_tokens"] - self.usage["output_tokens"])
        if output <= 0:
            raise Exhausted("output budget exhausted")
        self.usage["model_calls"] += 1
        self.usage["input_tokens"] += reserve
        self.usage["output_tokens"] += output
        self.store.save()
        return reserve, output

    def settle(self, reserved, output, usage):
        for key in ("input_tokens", "output_tokens"):
            if type(usage.get(key)) is not int or usage[key] < 0:
                raise ValueError("missing/invalid provider usage; reservation retained")
        self.usage["input_tokens"] += usage["input_tokens"] - reserved
        self.usage["output_tokens"] += usage["output_tokens"] - output
        self.store.save(); self.check()

    def tool(self):
        self.check()
        if self.usage["tool_calls"] >= self.limits["tool_calls"]:
            raise Exhausted("tool budget exhausted")
        self.usage["tool_calls"] += 1
        self.store.save()

    def repair(self):
        if self.usage["repairs"] >= self.limits["repair_cycles"]:
            raise Exhausted("one-repair limit reached")
        self.usage["repairs"] += 1
        self.store.save()
