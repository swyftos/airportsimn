# Agent protocol (read before every task)

1. Read `AGENTS.md` (project plan) once per session, then `coordination/BOARD.md`.
2. Work only in the folders your role owns (AGENTS.md section 8). Never edit another role's files.
3. Never change the data contract (AGENTS.md section 7) on your own. If you need a change, write it under "Requests" in your status file and stop.
4. No numeric constant in code: everything comes from `config/assumptions.yaml`.
5. Commit on your own branch if git lets you (Codex sandboxes cannot: then leave changes uncommitted, the supervisor commits). Never merge, never push to `main`.
6. When you finish (or are blocked), overwrite `coordination/status/<role>.md` with EXACTLY this format, max 8 lines, no prose:

```
state: DONE | BLOCKED | PARTIAL
task: <one line>
files: <comma-separated paths changed>
tests: <pytest summary line, or n/a>
commit: <short sha>
requests: <none | one line per need from another role>
```

The supervisor only reads this file. Anything not in it is invisible.
