"""One local master, one writer, local validation, then a frozen-packet reviewer."""
from .budget import Budget, Exhausted
from .config import hashes, load
from .contracts import load_task, validate
from .fake_provider import FakeProvider
from .ledger import Ledger
from .manifests import freeze, thaw, object_hash
from .openai_provider import OpenAIProvider, LivePermit
from .state_store import StateStore, lease
from .tools import Tools
from .tool_loop import run_loop

TERMINAL = {"READY_FOR_HUMAN", "ACCEPTED", "REJECTED", "BLOCKED", "FAILED", "PARTIAL"}


def lineage(task):
    return object_hash({"task": task, "resources": hashes()})


def summary(store):
    return {"state": store.data["state"], "provider": store.data["mode"], "manifest_ref": store.data.get("manifest_ref"),
            "review_status": "FAKE_REVIEW_ONLY" if store.data["mode"] == "fake" else store.data.get("review", {}).get("verdict", "NOT_REVIEWED"),
            "usage": store.data["usage"], "unresolved": store.data["unresolved"], "human_decision": store.data.get("human_decision", {})}


def persist_manifest(store, task):
    data = store.data
    calls = [{k: v for k, v in c.items() if k != "response"} for c in sorted(data["calls"].values(), key=lambda c: c["sequence"])]
    operations = {k: {field: value for field, value in op.items() if field != "result"} for k, op in data["operations"].items()}
    document = {"version": "1.0.0", "task_hash": data["task_hash"], "base_revision": task["base_revision"],
                "mode": data["mode"], "resources": data["resources"],
                "input_hashes": {k: v["sha256"] for k, v in data.get("initial_files", {}).items()},
                "output_hashes": {k: v["sha256"] for k, v in data.get("final_files", {}).items()},
                "calls": calls, "tool_operations": operations, "checks": data.get("checks", []), "usage": data["usage"], "budget_limits": task["budget"],
                "review_packet_refs": data["packets"], "review": data.get("review", {}), "status": data["state"],
                "unresolved": data["unresolved"], "human_decision": data.get("human_decision", {})}
    validate(document, load("schemas/run_manifest.schema.json"))
    data["manifest_ref"] = freeze(store.directory / "manifests", document)
    store.save()


def audit_changes(tools, store):
    final = tools.snapshot()
    initial = store.data["initial_files"]
    expected = {k: v["sha256"] for k, v in initial.items()}
    for operation in sorted(store.data["operations"].values(), key=lambda op: op["sequence"]):
        if operation["tool"] in {"create_file", "replace_text"}:
            if operation["status"] != "DONE":
                raise ValueError("unfinished write intent")
            expected[operation["path"]] = operation["after_sha256"]
    actual = {k: v["sha256"] for k, v in final.items()}
    if actual != expected:
        raise ValueError("filesystem drift not explained by recorded tool writes")
    return final


def run(folder, *, mode="fake", permit=None, provider=None, fault=None):
    task, guard = load_task(folder)
    if mode not in {"fake", "openai"}:
        raise ValueError("unknown provider mode")
    if mode == "openai":
        if not isinstance(permit, LivePermit) or permit.task_id != task["task_id"] or task["network_policy"] != "api.openai.com":
            raise ValueError("task-specific live authorization required")
    provider = provider or (FakeProvider() if mode == "fake" else OpenAIProvider(permit))
    if provider.name != mode:
        raise ValueError("provider mode mismatch")
    with lease(guard.root):
        store = StateStore(guard.root, task["task_id"], lineage(task), mode)
        store.data.setdefault("resources", hashes())
        ledger = Ledger(store.directory)
        ledger.events()  # detect truncated or corrupted ledger before side effects
        budget = Budget(task["budget"], store)
        tools = Tools(guard, task, store, ledger, budget, fault=fault)
        if store.data["state"] in TERMINAL:
            if store.data.get("manifest_ref"):
                thaw(store.directory / "manifests", store.data["manifest_ref"])
            if store.data["state"] == "READY_FOR_HUMAN":
                audit_changes(tools, store)
            if not store.data.get("manifest_ref"):
                persist_manifest(store, task)
            return summary(store)
        try:
            if store.data["state"] == "PENDING":
                store.data["initial_files"] = tools.snapshot()
                store.transition("PLANNED")
            if store.data["state"] == "PLANNED":
                store.transition("IMPLEMENTING")
            while store.data["state"] not in TERMINAL:
                budget.check()
                cycle = store.data["cycle"]
                if store.data["state"] == "IMPLEMENTING":
                    packet_key = f"writer_input_{cycle}"
                    if packet_key not in store.data:
                        store.data[packet_key] = {"task": task, "files": tools.snapshot(), "feedback": store.data.get("feedback", [])}
                        store.save()
                    worker = run_loop("writer", store.data[packet_key], provider, tools, store, budget, ledger, cycle)
                    store.data["worker"] = worker
                    if worker["status"] != "COMPLETE":
                        store.data["unresolved"] = worker["unresolved"]
                        store.transition("PARTIAL")
                        break
                    store.transition("VALIDATING")
                if store.data["state"] == "VALIDATING":
                    store.data["final_files"] = audit_changes(tools, store)
                    checks = [tools.check(name) for name in sorted(task["checks"])]
                    store.data["checks"] = checks
                    if not all(c["ok"] for c in checks):
                        budget.repair()
                        store.data["cycle"] += 1
                        store.data["feedback"] = checks
                        store.transition("IMPLEMENTING")
                        continue
                    packet = {"task": task, "task_hash": store.data["task_hash"], "resources": store.data["resources"],
                              "initial_files": store.data["initial_files"], "files": store.data["final_files"],
                              "checks": checks, "worker": store.data["worker"], "cycle": cycle, "provider": mode}
                    ref = freeze(store.directory / "packets", packet)
                    if ref not in store.data["packets"]:
                        store.data["packets"].append(ref)
                    store.transition("PACKET_FROZEN")
                if store.data["state"] == "PACKET_FROZEN":
                    store.transition("REVIEWING")
                if store.data["state"] == "REVIEWING":
                    packet = thaw(store.directory / "packets", store.data["packets"][-1])
                    if tools.snapshot() != packet["files"]:
                        raise ValueError("files changed since review packet freeze")
                    review = run_loop("reviewer", packet, provider, tools, store, budget, ledger, cycle)
                    if tools.snapshot() != packet["files"]:
                        raise ValueError("files mutated during read-only review")
                    store.data["review"] = review
                    if review["verdict"] == "BLOCKED":
                        store.data["unresolved"] = review["unresolved"] or ["review blocked"]
                        store.transition("BLOCKED")
                    elif review["verdict"] == "FINDINGS":
                        store.data["unresolved"] = [f["explanation"] for f in review["findings"]] + review["unresolved"]
                        budget.repair()
                        store.data["cycle"] += 1
                        store.data["feedback"] = review["findings"]
                        store.transition("IMPLEMENTING")
                    else:
                        store.data["unresolved"] = []
                        store.transition("READY_FOR_HUMAN")
        except (ValueError, OSError, KeyError, TypeError, StopIteration) as error:
            from .redaction import clean
            store.data["unresolved"].append(clean(str(error)))
            store.transition("PARTIAL" if isinstance(error, Exhausted) else "BLOCKED")
        persist_manifest(store, task)
        ledger.append({"state": store.data["state"], "manifest_ref": store.data["manifest_ref"]})
        return summary(store)


def decide(folder, owner, decision, confirmation, mode="fake"):
    task, guard = load_task(folder)
    if owner != task["owner"] or decision not in {"ACCEPTED", "REJECTED"} or confirmation != f"{decision} {task['task_id']} AS {owner}":
        raise ValueError("named owner and exact human confirmation required")
    with lease(guard.root):
        store = StateStore(guard.root, task["task_id"], lineage(task), mode)
        if store.data["state"] != "READY_FOR_HUMAN":
            raise ValueError("only READY_FOR_HUMAN may receive acceptance")
        tools = Tools(guard, task, store, Ledger(store.directory), Budget(task["budget"], store))
        if tools.snapshot() != store.data["final_files"]:
            raise ValueError("files changed after review; use new task")
        thaw(store.directory / "manifests", store.data["manifest_ref"])
        store.data["human_decision"] = {"owner": owner, "decision": decision, "provider": mode}
        store.transition(decision, human=True)
        persist_manifest(store, task)
        return summary(store)
