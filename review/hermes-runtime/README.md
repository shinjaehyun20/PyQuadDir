# Hermes runtime admission review carrier

Scoped production-source snapshots for external review, not a PyQuadDir feature or deployable runtime. No configuration, operational goal/session registry, logs, credentials, customer documents or executable is included. The .py.txt suffix marks the non-installable review-only boundary. source-map.json binds snapshots to production bytes and exact line spans. The only adaptation is the explicitly recorded personal-path redaction in the test snapshot.

## Applied changes

- First-goal tests use the canonical CLI interpreter, not the hook-host interpreter.
- Absolute metadata caller identity uses the existing canonical APPROVED_EXECUTABLE instead of hook-host sys.executable. Existing bare-launcher behavior remains unchanged; this is not new executable authorization.
- Added persistent different-hook-host / canonical-caller and wrong-caller regressions for first-goal and metadata bootstrap.
- Preserved the user-authored STALE-to-MISS advisory projection and canonical first-goal CLI identity verbatim. The shared cache consumer retains its original semantics; the adapter is the Hermes-specific projection.

## Actual local verification

Final fixed offline runner: 22 tests, zero skips, PASS; source_unchanged=true; golden_promoted=false. Synthetic hardlink and Windows junction checks executed. Symlink creation was unavailable (Windows error 1314); unsupported creation remained denied. Successful symlink creation is not claimed.

Actual command shape: <canonical Hermes venv python> -B D:/workspace/tools/stack/hermes_verification_admission.py --session-id <actual native session> --task-id <same-session task>, after supported registration of fresh source-hash binding. Direct unittest runs before the final added metadata regression: 21 tests, six sandbox-only skips, PASS under Python3 hook host and canonical CLI. These are distinct verification scopes.

## Product build status: NOT complete

Before this carrier was added the product worktree was clean at committed 85e9aabe2effdc71e03ca7ccfef372f8d3e07550. Original EXE SHA-256 F76491BAFEA57F4003F44DCD76FD1AC6D2CB6B9298C9C51302EDF97C502D5ECA; 39846206 bytes. Build precheck stopped because the canonical EXE was running. No user process was killed, and no EXE was renamed, overwritten or rebuilt. No new binary hash/version or new-EXE GUI acceptance is claimed. Next product step requires operator closure of the existing app, then the ordered clean-source precheck, backup, canonical build and smoke sequence. An absolute build-interpreter path was also rejected by the write guard; packaging never began.

## Review scope

Review the exact commit and cite file/line and severity. Do not publish, modify main or install this carrier. Offline tests are not product GUI acceptance. This public app repository is only the explicitly approved source-only review carrier for these scoped runtime changes, not their production installation root.
