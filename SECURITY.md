# Security

This is a local single-user tool, not an OS sandbox or a multi-user authentication service.
The trusted computing base is Python, this controller, owner-authored task/config, and the local OS.
Do not run on a directory concurrently writable by an adversarial OS process or remote/network filesystem.
Path revalidation cannot eliminate all TOCTOU races against a hostile local administrator.
Use an isolated local directory and restricted OS account. Never include real secrets in read scope.

Models cannot invoke shell, arbitrary Python, network, environment access, deletion, package installation,
Git, or acceptance. The only check executable is the toolkit's fixed stdlib assertion runner.
Reviewer gets file contents from a frozen packet and no functions.
Links/reparse points, hardlinks, traversal and writes beyond allowlists are rejected.

The API key is environment-only, never a CLI argument or file. Known keys and key-like strings
are rejected in model inputs and outputs; sanitization is defense in depth, not a complete DLP system.
Task contents, snapshots and encrypted reasoning are retained in private .controlled-agent checkpoints.
Do not publish or share these runtime directories. store:false does not mean zero provider retention.
API transport disables environment proxies and redirects, uses verified HTTPS, bounded responses and no retries.
Ambiguous transport failures keep a pending reservation and block: do not blindly retry or reset state.

Hash-addressed packets/manifests detect tampering but are not signed or physically write-protected.
Owner decisions use a name and confirmation phrase, not strong identity verification.
Fake acceptance, if explicitly performed by an owner, is labelled fake and proves no live review.
The toolkit author has not accepted any real task during this build.

Report vulnerabilities privately to the repository owner after a contact is configured.
Do not attach keys, private task packets, runtime logs or exploit data from real projects.
