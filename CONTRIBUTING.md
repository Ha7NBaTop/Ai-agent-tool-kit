# Contributing

The project is MIT licensed. Contributions must be compatible with that license.
Use synthetic fixtures and temporary directories, standard library, and Python 3.11+.
Keep fake/live evidence separate, preserve no-fallback routing, and do not weaken guards to make tests pass.
Changes to tool semantics require negative tests, crash/replay tests and threat-model updates.

Run `python -B -m unittest discover -s tests -v` and `python -B -m controlled_agent.cli demo`.
Then run `python -B scripts/build_export.py` and `python -B scripts/verify_export.py` on a clean export copy.
A Git checkout must exclude .git before export verification; scripts/ci_verify.py does this in a temporary copy.
Review generated hashes and docs before publication. Never include local runtime data.
