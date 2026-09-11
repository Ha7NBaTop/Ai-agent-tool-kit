# Controlled AI Agent Toolkit

A standalone, offline-first Python 3.11+ tool. No runtime dependencies or installation required.
It offers bounded file editing through Responses API custom functions, a deterministic local master,
sequential writer, checks, immutable review packet, read-only reviewer and a separate owner decision.

Build status: see [BUILD_REPORT.md](docs/BUILD_REPORT.md). Live model access remains ACCESS_UNKNOWN.
This is not a production security boundary. License is not yet granted: see LICENSE-CHOICE.md.

From this directory:

```sh
python -B -m controlled_agent.cli demo
python -B -m controlled_agent.cli doctor
python -B -m unittest discover -s tests -v
python -B scripts/verify_export.py
```

Windows: `./agent.ps1 demo`. POSIX: `sh agent.sh demo` (or `./agent.sh demo` after making the launcher executable).
Launchers need Python on PATH, do not install anything or change execution policy.
Windows with disabled PowerShell scripts can use `agent.cmd demo` or the direct Python command.
The demo copies synthetic inputs to a temporary directory and removes that temporary copy.
Fake run output explicitly says FAKE_REVIEW_ONLY; it is never evidence of real-model use.

Exact requested live routes: OpenAI gpt-5.6-sol/high (writer) and gpt-6-astra/high (reviewer).
No model aliases, Claude or fallback. API access must be tested separately with explicit permission.
Read [Russian quickstart](docs/QUICKSTART_RU.md), [API setup](docs/API_SETUP_RU.md),
[architecture](docs/ARCHITECTURE.md) and [security](SECURITY.md) before live use.

A copied task folder contains its target files and task.json. Paths are relative to target_root;
target_root itself is relative to task.json. Use a new task_id for changed contracts or fake-to-live migration.
The shipped fake provider is a scripted greeting demonstration, not a general-purpose AI.

Check profiles intentionally support only equality, literal containment and SHA-256 assertions.
They never execute code supplied by the target project. General test-runner integration requires
an independently sandboxed executor and is deferred.

Optional packaging: a stdlib PEP 517 wheel backend is included; no runtime third-party dependencies.
A pre-existing pip can optionally install with `python -m pip install --no-build-isolation --no-deps .`.
No installation or package/release publication was performed. Source launch is the primary path.
