# Threat model and limits

In scope: malicious model paths/function arguments, prompt injection in declared files, writer/reviewer role
confusion, schema failures, stale hashes, links/reparse points, accidental secrets, duplicate replay,
concurrent cooperating masters, corrupted packet/ledger, runaway calls and ambiguous network responses.

Controls: exact routes/no fallback, strict bounded functions, no executable model text, declarative checks,
allow/deny paths before access, reparse/hardlink denial, one OS lease, write-ahead checkpoint,
hash-addressed packets, no automatic network retry, approvals and cumulative budgets.

Trusted: owner-authored contract/config/controller/Python/OS. A malicious local user can alter them or call
internal Python APIs, forge an owner name, race path checks or tamper with unsigned state. These attacks
require OS account isolation, signed policies, identity and a sandbox, none of which is claimed here.
Atomic file publication is not a transactional filesystem and directory fsync portability varies.

Known limits: UTF-8 text only; 64 KiB/file, 200 files and 512 KiB snapshot; literal search only;
no deletes, directory moves, binary editing, general shell/test runner, regex engine or network tools.
Root must be a real local directory, not a junction/symlink. Hardlinked files are refused.
Secrets scanning is heuristic, not complete DLP. Read scopes may be transmitted verbatim in live mode.
Runtime packets contain target content and encrypted reasoning and must remain private.

No real-model access, live provider behavior, production security or production readiness is established.
Fake lifecycle and mocked HTTPS prove local mechanics only. CI matrix is configuration until hosted runs occur.
General-purpose autonomous coding, strong owner authentication and adversarial OS isolation are deferred.
