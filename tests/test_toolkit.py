"""Offline regressions. All mutations and subprocess workspaces use temporary directories."""
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from controlled_agent.budget import Budget, Exhausted
from controlled_agent.config import load
from controlled_agent.contracts import load_task, validate
from controlled_agent.fake_provider import FakeProvider
from controlled_agent.ledger import Ledger
from controlled_agent.manifests import atomic_bytes, digest, freeze, thaw
from controlled_agent.openai_provider import authorize, OpenAIProvider, LivePermit, NoRedirect
from controlled_agent.orchestrator import run, decide, lineage
from controlled_agent.path_guard import PathGuard, relative
from controlled_agent.redaction import clean, reject_secrets
from controlled_agent.router import route
from controlled_agent.state_store import StateStore, lease
from controlled_agent.tools import Tools, TOOL_DEFINITIONS
from verify_export import inventory, verify, MANIFEST
from build_export import build
from wheel_backend import build_wheel


class Crash(BaseException):
    pass


def final(value):
    return [{"type": "reasoning", "encrypted_content": "synthetic-encrypted"},
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": json.dumps(value)}]}]


def function(name, arguments, call_id="call-synthetic"):
    return [{"type": "function_call", "name": name, "arguments": json.dumps(arguments), "call_id": call_id}]


COMPLETE = {"status": "COMPLETE", "summary": "Synthetic test", "unresolved": []}
NO_FINDINGS = {"verdict": "NO_FINDINGS", "findings": [], "unresolved": []}
FINDINGS = {"verdict": "FINDINGS", "findings": [{"severity": "P2", "file": "output/hello.txt", "locator": "line 1",
            "invariant": "synthetic test", "explanation": "Please inspect greeting", "reproducer": "read line 1"}], "unresolved": []}


class Scripted(FakeProvider):
    def __init__(self, writer=None, reviewer=None):
        self.script = {"writer": iter(writer) if writer is not None else None, "reviewer": iter(reviewer) if reviewer is not None else None}
        self.requests = []

    def complete(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        role = "writer" if kwargs["tools"] else "reviewer"
        response = super().complete(**kwargs)
        if self.script[role] is not None:
            response["output"] = next(self.script[role])
        return response


class ToolkitTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="controlled agent tests ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "task with spaces"
        shutil.copytree(ROOT / "examples" / "hello-safe-edit", self.root,
                        ignore=shutil.ignore_patterns("output", ".controlled-agent", "__pycache__"))
        self.task, self.guard = load_task(self.root)
        self.network = patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("network forbidden in offline suite"))
        self.network.start(); self.addCleanup(self.network.stop)
        self.env = patch.dict(os.environ, {"PYTHONDONTWRITEBYTECODE": "1", "CONTROLLED_AGENT_LIVE_ENABLED": "0", "OPENAI_API_KEY": ""})
        self.env.start(); self.addCleanup(self.env.stop)

    def task_change(self, **updates):
        self.task.update(updates)
        (self.root / "task.json").write_text(json.dumps(self.task), encoding="utf-8")
        self.task, self.guard = load_task(self.root)

    def toolkit(self, fault=None):
        store = StateStore(self.root, self.task["task_id"], lineage(self.task), "fake")
        ledger = Ledger(store.directory)
        budget = Budget(self.task["budget"], store)
        return Tools(self.guard, self.task, store, ledger, budget, fault=fault)

    def create(self, content="one\n", name="output/file.txt"):
        return self.toolkit().invoke("writer", "create_file", {"path": name, "content": content}, "create")

    def subprocess_cli(self, *args, cwd=None):
        return subprocess.run([sys.executable, "-B", "-m", "controlled_agent.cli", *args],
                              cwd=cwd or ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)

    def test_01_launch_without_dependencies(self):
        result = self.subprocess_cli("doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["model_access"], "ACCESS_UNKNOWN")
        self.assertEqual(json.loads(result.stdout)["api_key_status"], "MISSING")

    def test_02_paths_with_spaces(self):
        self.assertIn(" ", str(self.root))
        self.assertEqual(run(self.root)["state"], "READY_FOR_HUMAN")

    def test_03_traversal_and_absolute_denied(self):
        for path in ("../x", "output/../x", "/etc/x", "C" + ":/x", "output\\x", "//server/x", "output/file:stream", "output/CON", "output/x. "):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.guard.path(path, write=True)

    def test_04_symlink_escape(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        link = self.root / "output"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest("OS does not permit test symlink: " + type(error).__name__)
        with self.assertRaises(ValueError):
            self.guard.path("output/escape.txt", write=True)

    @unittest.skipUnless(os.name == "nt", "Windows junction only")
    def test_04b_junction_escape(self):
        outside = Path(self.temp.name) / "junction target"
        outside.mkdir()
        link = self.root / "output"
        # Trusted fixed test command, never model-supplied; no deletion/moving command.
        escaped_link = str(link).replace("'", "''")
        escaped_outside = str(outside).replace("'", "''")
        result = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "New-Item -ItemType Junction -Path '" + escaped_link + "' -Target '" + escaped_outside + "'"], capture_output=True, timeout=20)
        if result.returncode:
            self.skipTest("junction creation unavailable")
        with self.assertRaises(ValueError):
            self.guard.path("output/escape.txt", write=True)

    def test_05_write_outside_allowlist(self):
        with self.assertRaises(ValueError):
            self.create(name="input/change.txt")

    def test_06_forbidden_path(self):
        for path in ("input/private/secret.txt", ".env", ".controlled-agent/checkpoint.json", "output/.env", "output/token.key"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.guard.path(path)

    def test_07_hash_conflict(self):
        self.create()
        with self.assertRaisesRegex(ValueError, "expected_sha256"):
            self.toolkit().invoke("writer", "replace_text", {"path": "output/file.txt", "expected_sha256": "0" * 64, "old": "one", "new": "two"}, "replace")
        self.assertEqual((self.root / "output/file.txt").read_text(), "one\n")

    def test_08_nonunique_or_missing_replace(self):
        self.create("one one\n")
        for i, old in enumerate(("one", "absent", "")):
            with self.assertRaisesRegex(ValueError, "exactly once"):
                self.toolkit().invoke("writer", "replace_text", {"path": "output/file.txt", "expected_sha256": digest(b"one one\n"), "old": old, "new": "two"}, "replace" + str(i))

    def test_09_atomic_replace_and_hash(self):
        self.create()
        with patch("controlled_agent.manifests.os.replace", wraps=os.replace) as replace:
            result = self.toolkit().invoke("writer", "replace_text", {"path": "output/file.txt", "expected_sha256": digest(b"one\n"), "old": "one", "new": "two"}, "replace")
        self.assertGreater(replace.call_count, 0)
        self.assertEqual(result["after_sha256"], digest(b"two\n"))
        self.assertEqual([p.name for p in (self.root / "output").iterdir()], ["file.txt"])

    def test_09b_create_never_overwrites(self):
        self.create()
        with self.assertRaises(ValueError):
            self.toolkit().invoke("writer", "create_file", {"path": "output/file.txt", "content": "other"}, "new-call")

    def test_10_secret_redaction(self):
        key = "sk-" + "syntheticsecret" * 3
        with patch.dict(os.environ, {"OPENAI_API_KEY": "custom-private-value"}):
            self.assertNotIn(key, str(clean({"note": key, "authorization": "value"})))
            self.assertNotIn("custom-private-value", clean("failed custom-private-value"))
            with self.assertRaises(ValueError):
                reject_secrets({"note": key})
        with self.assertRaises(ValueError):
            self.create(key)

    def test_11_reviewer_mutation_rejected(self):
        with self.assertRaises(ValueError):
            self.toolkit().invoke("reviewer", "create_file", {"path": "output/no.txt", "content": "no"}, "review")
        provider = Scripted(reviewer=[function("create_file", {"path": "output/no.txt", "content": "no"})])
        self.assertEqual(run(self.root, provider=provider)["state"], "BLOCKED")
        self.assertFalse((self.root / "output/no.txt").exists())

    def test_12_root_master_lock(self):
        with lease(self.root):
            with self.assertRaisesRegex(ValueError, "lease"):
                with lease(self.root):
                    self.fail("second writer acquired lock")
        with lease(self.root):
            pass

    def test_13_exact_routes(self):
        self.assertEqual(route("writer")["model"], "gpt-5.6-sol")
        self.assertEqual(route("reviewer")["model"], "gpt-6-astra")
        for role in ("writer", "reviewer"):
            self.assertEqual(route(role)["reasoning_effort"], "high")
            self.assertIsNone(route(role)["fallback"])
        self.assertFalse(route("reviewer")["write_access"])

    def response(self, model="gpt-5.6-sol"):
        return {"id": "mock-response", "model": model, "status": "completed", "output": final(COMPLETE),
                "usage": {"input_tokens": 11, "output_tokens": 12}, "service_tier": "default"}

    def call_mock(self, response=None, model="gpt-5.6-sol", tools=None, transport=None):
        seen = []
        def fake_http(request, timeout):
            seen.append((request, timeout))
            return io.BytesIO(json.dumps(response or self.response(model)).encode())
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-" + "testonly" * 4, "CONTROLLED_AGENT_LIVE_ENABLED": "1"}):
            value = OpenAIProvider(LivePermit("test", 1), transport=transport or fake_http).complete(
                model=model, instructions="Synthetic", history=[{"role": "user", "content": "synthetic"}],
                tools=TOOL_DEFINITIONS if tools is None else tools, schema=load("schemas/worker_result.schema.json"),
                key="synthetic-idempotency", max_output_tokens=256, timeout=10)
        return value, seen

    def test_14_resolved_model_mismatch(self):
        with self.assertRaisesRegex(ValueError, "resolved-model mismatch"):
            self.call_mock(self.response("other-model"))

    def test_15_no_fallback_or_retry(self):
        count = []
        def fail(*args, **kwargs):
            count.append(1)
            raise OSError("sensitive transport detail")
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS") as caught:
            self.call_mock(transport=fail)
        self.assertEqual(len(count), 1)
        self.assertNotIn("sensitive", str(caught.exception))
        with self.assertRaisesRegex(ValueError, "no fallback"):
            self.call_mock(model="alias")

    def test_16_all_live_gates(self):
        task = copy.deepcopy(self.task)
        task["network_policy"] = "api.openai.com"
        good = dict(live=True, approve=True, confirmation="RUN LIVE " + task["task_id"])
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-only", "CONTROLLED_AGENT_LIVE_ENABLED": "1"}):
            self.assertIsInstance(authorize(task, **good), LivePermit)
            for key, value in (("live", False), ("approve", False), ("confirmation", "wrong")):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    authorize(task, **{**good, key: value})
            for envkey in ("OPENAI_API_KEY", "CONTROLLED_AGENT_LIVE_ENABLED"):
                with patch.dict(os.environ, {envkey: ""}), self.assertRaises(ValueError):
                    authorize(task, **good)
            with self.assertRaises(ValueError):
                authorize({**task, "network_policy": "disabled"}, **good)
            with self.assertRaises(ValueError):
                authorize({**task, "budget": {**task["budget"], "model_calls": 0}}, **good)

    def test_17_mock_request_contract(self):
        result, seen = self.call_mock()
        request, timeout = seen[0]
        data = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
        self.assertEqual(data["model"], "gpt-5.6-sol")
        self.assertEqual(data["reasoning"], {"effort": "high"})
        self.assertFalse(data["store"])
        self.assertFalse(data["parallel_tool_calls"])
        self.assertEqual(data["max_output_tokens"], 256)
        self.assertEqual(timeout, 10)
        self.assertIn("Idempotency-key", request.headers)
        self.assertNotIn("OPENAI_API_KEY", str(data))
        self.assertEqual(result["usage"]["input_tokens"], 11)

    def test_18_writer_has_only_six_scoped_tools(self):
        _, seen = self.call_mock()
        definitions = json.loads(seen[0][0].data)["tools"]
        self.assertEqual({t["name"] for t in definitions}, {"list_files", "read_file", "search_text", "create_file", "replace_text", "run_check"})
        self.assertTrue(all(t["strict"] for t in definitions))

    def test_19_reviewer_has_no_tools(self):
        _, seen = self.call_mock(model="gpt-6-astra", tools=[])
        self.assertEqual(json.loads(seen[0][0].data)["tools"], [])
        with self.assertRaises(ValueError):
            self.call_mock(model="gpt-6-astra")

    def test_20_function_outputs_and_review_order(self):
        provider = Scripted()
        result = run(self.root, provider=provider)
        self.assertEqual(result["state"], "READY_FOR_HUMAN")
        self.assertEqual(len(provider.requests), 4)
        self.assertTrue(all(r["tools"] for r in provider.requests[:-1]))
        self.assertEqual(provider.requests[-1]["tools"], [])
        self.assertTrue(any(i.get("type") == "function_call_output" for i in provider.requests[1]["history"]))
        packet = json.loads(provider.requests[-1]["history"][0]["content"])["task_packet"]
        self.assertTrue(all(c["ok"] for c in packet["checks"]))
        self.assertIn("output/hello.txt", packet["files"])

    def test_21_idempotent_replay(self):
        provider = Scripted()
        first = run(self.root, provider=provider)
        stamp = (self.root / "output/hello.txt").stat().st_mtime_ns
        second = run(self.root, provider=provider)
        self.assertEqual(first, second)
        self.assertEqual(len(provider.requests), 4)
        self.assertEqual(stamp, (self.root / "output/hello.txt").stat().st_mtime_ns)

    def crash_resume(self, stage):
        provider = Scripted()
        def crash(actual):
            if stage == actual:
                raise Crash()
        with self.assertRaises(Crash):
            run(self.root, provider=provider, fault=crash)
        path = self.root / "output/hello.txt"
        stamp = path.stat().st_mtime_ns if path.exists() else None
        result = run(self.root, provider=provider)
        self.assertEqual(result["state"], "READY_FOR_HUMAN")
        self.assertEqual(result["usage"]["tool_calls"], 2)
        self.assertEqual(len(provider.requests), 4)
        if stamp is not None:
            self.assertEqual(stamp, path.stat().st_mtime_ns)

    def test_22a_crash_before_write(self):
        self.crash_resume("before_write")

    def test_22b_crash_after_write(self):
        self.crash_resume("after_write")

    def test_23_budget_exhaustion(self):
        self.task_change(budget={**self.task["budget"], "model_calls": 1})
        result = run(self.root)
        self.assertEqual(result["state"], "PARTIAL")
        self.assertEqual(result["usage"]["model_calls"], 1)
        self.assertEqual(run(self.root), result)

    def test_24_structured_repair_limit(self):
        provider = Scripted(writer=[final({"bad": True}), final({"bad": True})])
        result = run(self.root, provider=provider)
        self.assertEqual(result["state"], "PARTIAL")
        self.assertEqual(result["usage"]["repairs"], 1)
        self.assertEqual(len(provider.requests), 2)
        self.assertIn("Validation error:", provider.requests[1]["history"][-1]["content"])

    def test_24b_single_structured_repair_succeeds(self):
        writer = [final({"bad": True}), function("create_file", {"path": "output/hello.txt", "content": "Hello, controlled agent!\n"}), final(COMPLETE)]
        result = run(self.root, provider=Scripted(writer=writer))
        self.assertEqual(result["state"], "READY_FOR_HUMAN")
        self.assertEqual(result["usage"]["repairs"], 1)

    def test_25_deterministic_frozen_manifest(self):
        directory = Path(self.temp.name) / "frozen"
        one = freeze(directory, {"b": 2, "a": 1})
        two = freeze(directory, {"a": 1, "b": 2})
        self.assertEqual(one, two)
        self.assertEqual(len(list(directory.iterdir())), 1)
        self.assertEqual(thaw(directory, one), {"a": 1, "b": 2})

    def test_26_immutable_packet_and_refreeze(self):
        writer = [function("create_file", {"path": "output/hello.txt", "content": "Hello, controlled agent!\n"}), final(COMPLETE), final(COMPLETE)]
        result = run(self.root, provider=Scripted(writer=writer, reviewer=[final(FINDINGS), final(NO_FINDINGS)]))
        self.assertEqual(result["state"], "READY_FOR_HUMAN")
        directory = self.root / ".controlled-agent" / self.task["task_id"]
        packets = sorted((directory / "packets").glob("*.json"))
        self.assertEqual(len(packets), 2)
        prior = packets[0].read_bytes()
        self.assertNotEqual(packets[0].name, packets[1].name)
        self.assertEqual(packets[0].read_bytes(), prior)
        packets[0].write_text("{}")
        with self.assertRaises(ValueError):
            thaw(directory / "packets", packets[0].stem)

    def test_27_fake_demo(self):
        result = self.subprocess_cli("demo")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        document = json.loads(result.stdout)
        self.assertEqual(document["demo"], "PASS")
        self.assertEqual(document["result"]["review_status"], "FAKE_REVIEW_ONLY")
        self.assertEqual(document["live_calls"], 0)

    def test_28_human_only_acceptance(self):
        result = run(self.root)
        self.assertEqual(result["human_decision"], {})
        for owner, phrase in (("other", "ACCEPTED hello-safe-edit AS other"), ("Kamil", "wrong")):
            with self.assertRaises(ValueError):
                decide(self.root, owner, "ACCEPTED", phrase)
        store = self.toolkit().store
        with self.assertRaises(ValueError):
            store.transition("ACCEPTED")
        # Synthetic fixture only; no real project/task is accepted.
        accepted = decide(self.root, "Kamil", "ACCEPTED", "ACCEPTED hello-safe-edit AS Kamil")
        self.assertEqual(accepted["state"], "ACCEPTED")
        self.assertEqual(accepted["human_decision"]["provider"], "fake")

    def export_copy(self):
        destination = Path(self.temp.name) / "portable copy"
        shutil.copytree(ROOT, destination, ignore=shutil.ignore_patterns(".git", "__pycache__", ".controlled-agent", "output"))
        return destination

    def test_29_export_hygiene_and_hashes(self):
        destination = self.export_copy()
        build(destination)
        self.assertEqual(verify(destination)["verification"], "PASS")
        (destination / "README.md").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "mismatch"):
            verify(destination)
        for name, content in ((".env", "secret"), ("runtime.log", "log"), ("state.sqlite", "state"),
                              ("bad.pyc", "cache"), ("unexpected.txt", "sk-" + "synthetic" * 4),
                              ("host.txt", "C" + ":/" + "Users/test/private")):
            path = destination / name
            path.write_text(content, encoding="utf-8")
            with self.subTest(name=name), self.assertRaises(ValueError):
                inventory(destination)
            path.unlink()
        (destination / "README.md").unlink()
        with self.assertRaisesRegex(ValueError, "missing required"):
            inventory(destination)

    def test_30_portable_copy_without_parent(self):
        destination = self.export_copy()
        result = self.subprocess_cli("demo", cwd=destination)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["demo"], "PASS")

    def test_31_hardlink_denial(self):
        path = self.root / "input/request.txt"
        link = self.root / "input/hardlink.txt"
        try:
            os.link(path, link)
        except OSError:
            self.skipTest("hardlinks unavailable")
        with self.assertRaises(ValueError):
            self.guard.path("input/hardlink.txt")

    def test_32_check_cannot_execute_python_or_shell(self):
        for argv in (["git", "push"], ["python", "-c", "print(1)"], ["powershell"], ["curl"], ["pip", "install", "x"]):
            task = copy.deepcopy(self.task)
            task["checks"]["hello"]["argv"] = argv
            (self.root / "task.json").write_text(json.dumps(task))
            with self.assertRaises(ValueError):
                load_task(self.root)

    def test_33_check_fixed_process_and_no_environment_secret(self):
        run(self.root)
        original = subprocess.run
        with patch("controlled_agent.tools.subprocess.run", wraps=original) as process:
            self.assertTrue(self.toolkit().check("hello")["ok"])
        args, kwargs = process.call_args
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["cwd"], self.root.resolve())
        self.assertNotIn("OPENAI_API_KEY", kwargs["env"])
        self.assertEqual(args[0][1:3], ["-I", "-B"])

    def test_34_ledger_corruption_blocks(self):
        self.create()
        ledger = self.toolkit().ledger
        events = ledger.events()
        self.assertGreater(len(events), 0)
        ledger.path.write_text("{}\n", encoding="utf-8")
        with self.assertRaises((ValueError, KeyError)):
            ledger.events()

    def test_35_task_and_mode_changes_reject_resume(self):
        run(self.root)
        self.task_change(objective="Changed objective")
        with self.assertRaisesRegex(ValueError, "changed"):
            run(self.root)

    def test_36_post_review_drift_blocks_acceptance(self):
        run(self.root)
        (self.root / "output/hello.txt").write_text("tampered")
        with self.assertRaises(ValueError):
            decide(self.root, "Kamil", "ACCEPTED", "ACCEPTED hello-safe-edit AS Kamil")
        with self.assertRaises(ValueError):
            run(self.root)

    def test_37_ambiguous_crash_no_second_request(self):
        class Ambiguous(FakeProvider):
            count = 0
            def complete(self, **kwargs):
                self.count += 1
                raise Crash()
        provider = Ambiguous()
        with self.assertRaises(Crash):
            run(self.root, provider=provider)
        result = run(self.root, provider=provider)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(provider.count, 1)
        self.assertIn("AMBIGUOUS", str(result["unresolved"]))

    def test_38_read_chunk_and_literal_search(self):
        tools = self.toolkit()
        chunk = tools.invoke("writer", "read_file", {"path": "input/request.txt", "offset": 0, "limit": 5}, "read")
        self.assertEqual(chunk["content"], "Write")
        search = tools.invoke("writer", "search_text", {"path": "input/request.txt", "text": "synthetic"}, "search")
        self.assertEqual(search["lines"][0]["line"], 1)
        with self.assertRaises(ValueError):
            tools.invoke("writer", "read_file", {"path": "input/request.txt", "offset": 0, "limit": 99999}, "large")

    def test_39_secret_input_blocks_before_provider(self):
        (self.root / "input/request.txt").write_text("sk-" + "synthetic" * 4)
        provider = Scripted()
        self.assertEqual(run(self.root, provider=provider)["state"], "BLOCKED")
        self.assertEqual(provider.requests, [])

    def test_40_stateless_reasoning_preserved(self):
        writer = [[{"type": "reasoning", "encrypted_content": "synthetic"}, *function("create_file", {"path": "output/hello.txt", "content": "Hello, controlled agent!\n"})], final(COMPLETE)]
        provider = Scripted(writer=writer)
        self.assertEqual(run(self.root, provider=provider)["state"], "READY_FOR_HUMAN")
        self.assertTrue(any(i.get("encrypted_content") == "synthetic" for i in provider.requests[1]["history"]))

    def test_41_wheel_is_self_contained_without_install(self):
        wheel_dir = Path(self.temp.name) / "wheels"
        first = build_wheel(wheel_dir)
        data = (wheel_dir / first).read_bytes()
        self.assertEqual(data, (wheel_dir / build_wheel(wheel_dir)).read_bytes())
        extracted = Path(self.temp.name) / "extracted wheel"
        with zipfile.ZipFile(wheel_dir / first) as archive:
            archive.extractall(extracted)
        result = self.subprocess_cli("demo", cwd=extracted)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_42_transport_rejects_redirect(self):
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(None, None, None, None, None, None)

    def test_43_tool_budget_and_wall_budget(self):
        tools = self.toolkit()
        tools.store.data["usage"]["tool_calls"] = self.task["budget"]["tool_calls"]
        with self.assertRaises(Exhausted):
            tools.invoke("writer", "list_files", {}, "too-many")
        tools.store.data["started"] = 0
        with self.assertRaises(Exhausted):
            tools.budget.check()

    def test_44_owner_contract_not_writable(self):
        task = copy.deepcopy(self.task)
        task.update(allowed_read_paths=["."], allowed_write_paths=["."])
        (self.root / "task.json").write_text(json.dumps(task))
        with self.assertRaisesRegex(ValueError, "contract"):
            load_task(self.root)

    def test_45_batch_tool_calls_rejected(self):
        calls = function("list_files", {}, "one") + function("list_files", {}, "two")
        result = run(self.root, provider=Scripted(writer=[calls]))
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["usage"]["tool_calls"], 0)

    def test_46_inconsistent_reviewer_schema_blocks_after_one_repair(self):
        bad = {**NO_FINDINGS, "findings": FINDINGS["findings"]}
        result = run(self.root, provider=Scripted(reviewer=[final(bad), final(bad)]))
        self.assertEqual(result["state"], "PARTIAL")
        self.assertEqual(result["usage"]["repairs"], 1)

    def test_47_repeated_writes_keep_chronological_order_after_resume(self):
        provider = Scripted(writer=[function("create_file", {"path": "output/hello.txt", "content": "old"}, "z-first"),
                                   function("replace_text", {"path": "output/hello.txt", "expected_sha256": digest(b"old"), "old": "old", "new": "Hello, controlled agent!\n"}, "a-last"), final(COMPLETE)])
        first = run(self.root, provider=provider)
        self.assertEqual(first["state"], "READY_FOR_HUMAN")
        self.assertEqual(run(self.root, provider=provider), first)
        tools = self.toolkit()
        # Canonical JSON sorts dictionary keys; audit must use sequence, not key ordering.
        tools.store.data["operations"] = dict(reversed(list(tools.store.data["operations"].items())))
        from controlled_agent.orchestrator import audit_changes
        self.assertIn("output/hello.txt", audit_changes(tools, tools.store))

    def test_48_ready_checkpoint_missing_manifest_recovers(self):
        first = run(self.root)
        store = self.toolkit().store
        del store.data["manifest_ref"]
        store.save()
        self.assertEqual(run(self.root), first)

    def test_49_mocked_openai_complete_lifecycle(self):
        self.task_change(network_policy="api.openai.com")
        requests = []
        fake = FakeProvider()
        def transport(request, timeout):
            payload = json.loads(request.data)
            requests.append(payload)
            response = fake.complete(model=payload["model"], instructions=payload["instructions"], history=payload["input"],
                                     tools=payload["tools"], schema=payload["text"]["format"]["schema"], key="mock", max_output_tokens=256, timeout=timeout)
            response.update(model=payload["model"], id="mocked-http-" + str(len(requests)))
            response.pop("provider", None)
            return io.BytesIO(json.dumps(response).encode())
        permit = LivePermit(self.task["task_id"], 16)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-test-key", "CONTROLLED_AGENT_LIVE_ENABLED": "1"}):
            result = run(self.root, mode="openai", permit=permit, provider=OpenAIProvider(permit, transport=transport))
        self.assertEqual(result["state"], "READY_FOR_HUMAN")
        self.assertEqual([r["model"] for r in requests], ["gpt-5.6-sol"] * 3 + ["gpt-6-astra"])
        directory = self.root / ".controlled-agent" / self.task["task_id"] / "manifests"
        manifest = thaw(directory, result["manifest_ref"])
        self.assertEqual(len(manifest["calls"]), 4)
        self.assertTrue(all(c["response_id"].startswith("mocked-http-") for c in manifest["calls"]))

    def test_50_provider_rejection_preserves_evidence(self):
        self.task_change(network_policy="api.openai.com")
        permit = LivePermit(self.task["task_id"], 16)
        def transport(request, timeout):
            return io.BytesIO(json.dumps(self.response("wrong-model")).encode())
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-test-key", "CONTROLLED_AGENT_LIVE_ENABLED": "1"}):
            result = run(self.root, mode="openai", permit=permit, provider=OpenAIProvider(permit, transport=transport))
        self.assertEqual(result["state"], "BLOCKED")
        manifest = thaw(self.root / ".controlled-agent" / self.task["task_id"] / "manifests", result["manifest_ref"])
        self.assertEqual(manifest["calls"][0]["resolved_model"], "wrong-model")
        self.assertEqual(manifest["calls"][0]["response_id"], "mock-response")

    def test_51_failing_checks_never_reach_reviewer(self):
        provider = Scripted(writer=[final(COMPLETE), final(COMPLETE)])
        result = run(self.root, provider=provider)
        self.assertEqual(result["state"], "PARTIAL")
        self.assertEqual(result["usage"]["repairs"], 1)
        self.assertTrue(all(r["tools"] for r in provider.requests))

    def test_52_exact_route_configuration_cannot_fallback(self):
        from controlled_agent import router
        original = router.load
        def changed(path):
            data = original(path)
            data["worker_hard_case"]["fallback"] = "other"
            return data
        with patch.object(router, "load", side_effect=changed), self.assertRaises(ValueError):
            route("writer")

    def test_53_export_forbids_runtime_directories(self):
        destination = self.export_copy()
        for name in ("sources", "context", "raw", ".ai", "__pycache__", ".controlled-agent"):
            path = destination / name
            path.mkdir()
            with self.subTest(name=name), self.assertRaises(ValueError):
                inventory(destination)
            path.rmdir()


if __name__ == "__main__":
    unittest.main()
