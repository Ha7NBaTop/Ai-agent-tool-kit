# Architecture

```text
local master lease
  -> writer tool loop (one tool at a time)
  -> deterministic declarative checks
  -> SHA-256 frozen packet
  -> read-only reviewer (no tools)
  -> READY_FOR_HUMAN
  -> separate named-owner decision
```

PENDING -> PLANNED -> IMPLEMENTING -> VALIDATING -> PACKET_FROZEN -> REVIEWING ->
READY_FOR_HUMAN -> ACCEPTED/REJECTED. BLOCKED/FAILED/PARTIAL preserve checkpoints.
Review/check feedback can return to IMPLEMENTING at most once. Structured-output repairs share that
same cumulative repair allowance, never add an unbounded second budget.

The controller, not a model, chooses transitions/routes/permissions. Worker COMPLETE never accepts a task.
Exact routes and resource hashes are part of lineage. Changed contract/config/code requires a new task_id.
Writer gets six strict functions; reviewer gets immutable initial/final contents and validation results.
Inputs and model output have no authority to change the contract.

Persisted checkpoint saves an API response before executing its function call. Calls have deterministic
request/idempotency hashes. A PENDING call after crash is ambiguous and is never automatically repeated.
Write intents save before/after SHA-256; after a crash, matching after-hash means recover without rewriting.
Conflicting content stops. State JSON is atomically replaced; audit ledger is hash-chained append-only.
Content-addressed packets/manifests never overwrite an existing different file. Hashes are integrity checks,
not signatures. Multiple cycles retain prior packets and calls.

Budget reserves conservative UTF-8 request size plus protocol margin and the output cap before calling,
then settles reported input/output tokens. No tokenizer dependency; reported overages stop further calls.
Wall time includes downtime. Model calls, tool calls, tokens and repairs are cumulative across resume.
Provider usage is authoritative for accounting; this mechanism is not a billing guarantee.

Filesystem writes are create-absent or unique exact replace with expected hash, temp file + atomic publication,
post-write verification. Scope snapshot is compared against recorded mutations before and after review.
Named check profiles run only a trusted isolated Python assertion runner with shell=False and scrubbed env.
Arbitrary target test execution is deliberately unsupported until an OS-sandboxed executor exists.

Fake provider is deterministic synthetic greeting machinery, labels every response fake and records fake model IDs.
A route's requested live name in a fake manifest is not evidence of a model invocation.
