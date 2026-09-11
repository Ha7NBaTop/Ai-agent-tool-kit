"""Portable CLI. No key or network needed for doctor, plan, demo and fake runs."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
from .budget import Budget
from .config import ROOT, load, resource, hashes
from .contracts import load_task
from .manifests import freeze, object_hash
from .openai_provider import authorize, OpenAIProvider, ProviderRejected
from .orchestrator import run, decide
from .redaction import clean
from .router import route
from .state_store import StateStore, lease
from .tool_loop import result_from


def emit(value):
    print(json.dumps(clean(value), ensure_ascii=False, indent=2))


def plan(folder):
    task, _ = load_task(folder)
    return {"task_id": task["task_id"], "master": "deterministic-local", "writer": route("writer"),
            "reviewer": route("reviewer"), "order": ["writer", "deterministic-checks", "freeze", "reviewer", "human"],
            "network_policy": task["network_policy"], "budget": task["budget"], "fallback": None}


def doctor():
    route("writer"); route("reviewer")
    return {"configuration": "VALID", "api_key_status": "PRESENT" if os.environ.get("OPENAI_API_KEY") else "MISSING",
            "live": os.environ.get("CONTROLLED_AGENT_LIVE_ENABLED") == "1", "model_access": "ACCESS_UNKNOWN",
            "routes": {"writer": route("writer"), "reviewer": route("reviewer")}, "dependencies": "stdlib only"}


def demo():
    with tempfile.TemporaryDirectory(prefix="controlled-agent-demo-") as temp:
        copy = Path(temp) / "hello safe edit"
        shutil.copytree(ROOT / "examples" / "hello-safe-edit", copy,
                        ignore=shutil.ignore_patterns(".controlled-agent", "output", "__pycache__"))
        first = run(copy)
        second = run(copy)
        expected = (copy / "expected" / "hello.txt").read_bytes()
        passed = first == second and first["state"] == "READY_FOR_HUMAN" and (copy / "output" / "hello.txt").read_bytes() == expected
        emit({"demo": "PASS" if passed else "FAIL", "result": first, "idempotent_resume": first == second,
              "workspace": "temporary; removed after demo", "live_calls": 0})
        return 0 if passed else 2


def probe(args):
    if not 1 <= args.max_output_tokens <= 256:
        raise ValueError("probe output cap must be 1..256 including reasoning tokens")
    task_id = "probe-" + args.model
    task = {"task_id": task_id, "network_policy": "api.openai.com", "budget": load("config/budgets.json")}
    task["budget"].update(model_calls=1, output_tokens=args.max_output_tokens, per_call_output_tokens=args.max_output_tokens)
    print("One synthetic OpenAI call. No target/project files. Reasoning consumes the output cap; incomplete is a failed probe.")
    permit = authorize(task, live=True, approve=args.approve_live, confirmation=input("Type RUN LIVE " + task_id + ": "))
    import uuid
    # Probe outputs stay outside distribution; caller explicitly supplies a directory.
    args.output.mkdir(parents=True, exist_ok=True)
    with lease(args.output):
        store = StateStore(args.output, task_id + "-" + uuid.uuid4().hex[:8], object_hash(task), "openai")
        budget = Budget(task["budget"], store)
        history = [{"role": "user", "content": "Synthetic connection probe. Return COMPLETE, summary probe, unresolved empty."}]
        reserved, cap = budget.reserve_call(10000)
        store.data["probe_pending"] = True; store.save()
        try:
            response = OpenAIProvider(permit).complete(model=args.model, instructions="Return the requested JSON only.", history=history,
                        tools=[], schema=load("schemas/worker_result.schema.json"), key=uuid.uuid4().hex, max_output_tokens=cap, timeout=60)
        except ValueError as error:
            failure = {"kind": "exact-model-probe", "status": "BLOCKED", "requested_model": args.model,
                       "reasoning_effort": args.reasoning, "error": clean(str(error)),
                       "budget_reservations": store.data["usage"], **getattr(error, "evidence", {})}
            ref = freeze(store.directory / "manifests", failure)
            store.data.update(manifest_ref=ref, unresolved=[clean(str(error))]); store.save()
            emit({"probe": "BLOCKED", "manifest_ref": ref, **failure})
            return 2
        from .contracts import validate
        result = result_from(response)
        validate(result, load("schemas/worker_result.schema.json"))
        budget.settle(reserved, cap, response["usage"])
        document = {"kind": "exact-model-probe", "requested_model": args.model, "resolved_model": response["model"],
                    "reasoning_effort": args.reasoning, "response_id": response["id"], "usage": response["usage"],
                    "service_tier": response.get("service_tier"), "result": result}
        ref = freeze(store.directory / "manifests", document)
        store.data.update(probe_pending=False, manifest_ref=ref); store.save()
        emit({"probe": "COMPLETE", "manifest_ref": ref, **document})
    return 0


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("demo"); sub.add_parser("doctor")
    validate_task = sub.add_parser("task").add_subparsers(dest="task_command", required=True).add_parser("validate")
    validate_task.add_argument("folder", type=Path)
    planner = sub.add_parser("plan"); planner.add_argument("folder", type=Path)
    runner = sub.add_parser("run"); runner.add_argument("folder", type=Path)
    modes = runner.add_mutually_exclusive_group(required=True)
    modes.add_argument("--fake", action="store_true"); modes.add_argument("--live", action="store_true")
    runner.add_argument("--approve-live", action="store_true")
    decision = sub.add_parser("decide"); decision.add_argument("folder", type=Path)
    decision.add_argument("--owner", required=True)
    decision.add_argument("--decision", choices=["ACCEPTED", "REJECTED"], required=True)
    decision.add_argument("--mode", choices=["fake", "openai"], default="fake")
    model = sub.add_parser("models").add_subparsers(dest="models_command", required=True).add_parser("probe")
    model.add_argument("--model", choices=["gpt-5.6-sol", "gpt-6-astra"], required=True)
    model.add_argument("--reasoning", choices=["high"], default="high")
    model.add_argument("--max-output-tokens", type=int, default=256)
    model.add_argument("--approve-live", action="store_true")
    model.add_argument("--output", type=Path, default=Path(tempfile.gettempdir()) / "controlled-agent-probes")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "demo":
            return demo()
        if args.command == "doctor":
            emit(doctor())
        elif args.command in {"plan", "task"}:
            emit(plan(args.folder))
        elif args.command == "models":
            return probe(args)
        elif args.command == "run":
            permit = None
            if args.live:
                task, _ = load_task(args.folder)
                emit(plan(args.folder))
                print("Live run transmits declared task/file contents to OpenAI. Review the scope and token budget above.")
                permit = authorize(task, live=True, approve=args.approve_live, confirmation=input("Type RUN LIVE " + task["task_id"] + ": "))
            result = run(args.folder, mode="openai" if args.live else "fake", permit=permit)
            emit(result)
            return 0 if result["state"] in {"READY_FOR_HUMAN", "ACCEPTED"} else 2
        elif args.command == "decide":
            task, _ = load_task(args.folder)
            phrase = f"{args.decision} {task['task_id']} AS {args.owner}"
            emit(decide(args.folder, args.owner, args.decision, input("Type " + phrase + ": "), args.mode))
        return 0
    except (ValueError, OSError, KeyError, TypeError, EOFError) as error:
        emit({"error": clean(str(error)), "status": "BLOCKED"})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
