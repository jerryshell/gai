# 0005 Name the call instead of containing the fault

Date: 2026-11-03
Status: accepted

## Context

`docs/gai/decisions/0004-synchronous-requests.md` decided that a bridge call
cannot be interrupted. It left the other half open: a call that hard-crashes the
process.

Today a fatal signal in the game kills the engine, and the client sees a closed
socket. The agent learns nothing: not the method, not the target, not the
signal. On the next start the scene is fresh and the evidence is gone.

Jenova Runtime contains the fault per call with a Windows structured exception
handler (`__try`/`__except`), aborts the script instance, and keeps the host
alive. That pattern is the reference we measured before choosing.

## Decision

Write a crash record, and do not try to contain the fault.

- Before each request the bridge formats one JSON prefix into a fixed buffer:
  schema, pid, method, target, start time. The request clears it after it
  returns.
- A handler for `SIGSEGV`, `SIGFPE`, `SIGILL`, and `SIGABRT` appends the signal
  name and number, writes the record with one `write`, and re-raises the signal
  with the default action.
- The handler allocates nothing, takes no lock, and formats no `String`.
- `bin/gai agent start` sets `GAI_CRASH_RECORD`. A clean stop deletes the record.
- `bin/gai agent call` and `bin/gai agent status` read the record and print the
  method, the target, and the signal.

## Why not contain the fault

- Linux has no structured exception handling. The equivalent is `siglongjmp`
  out of a signal handler, which leaves every mutex and allocator state in the
  process as the fault found it. The engine's own crash handler and the core
  dump are the honest behavior.
- Jenova's version is Windows-only for that reason, and it aborts the script
  instance, not the engine. gai has no script-instance layer to abort.
- A guard that catches the signal and continues would turn a loud crash into a
  quiet corrupted state, which is worse for an agent than a named death.

## Consequences

- A crashing call still costs the process and the scene state. The agent knows
  which call to avoid, which is the part that was missing.
- The record is written for Linux and macOS. Windows has no record until an
  unhandled-exception filter exists.
- The in-flight buffer is one request deep. A batch reports the item that was
  running when the signal arrived.
- The handler is installed only when the bridge starts, so a normal game run is
  unchanged.

## Revisit

Revisit if an engine build offers per-call fault isolation with a defined
recovery point, or if Windows parity is needed.
