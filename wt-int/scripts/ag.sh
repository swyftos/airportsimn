#!/usr/bin/env bash
# Supervisor harness: dispatch tasks to agents in their own worktrees, read compact status.
#   ag.sh setup                 create one worktree + branch per role
#   ag.sh send <role> "<task>"  run the role's agent in background (log in .logs/)
#   ag.sh status                compact view: status files + diff stat per branch
#   ag.sh test <role>           pytest summary in that worktree
#   ag.sh log <role> [n]        last n lines of the agent log (default 20)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WT="$(dirname "$ROOT")"
LOGS="$ROOT/.logs"; mkdir -p "$LOGS"
ROLES="data model docs"

model_for() {  # role -> agent command prefix
  case "$1" in
    data)  echo "opencode run --auto -m ${DATA_MODEL:-google/gemini-3.8-flash}" ;;
    docs)  echo "opencode run --auto -m ${DOCS_MODEL:-google/gemini-flash-latest}" ;;
    *) echo "unknown role: $1" >&2; exit 1 ;;
  esac
}

default_engine() {  # data: Gemini (Antigravity), docs: GitHub Copilot, model: Codex
  case "$1" in data) echo agy ;; docs) echo copilot ;; *) echo codex ;; esac
}

preamble() {
  echo "You are the '$1' agent of the RampReady team. Follow coordination/PROTOCOL.md strictly. Task:"
}

case "${1:-}" in
  setup)
    for r in $ROLES; do
      [ -d "$WT/wt-$r" ] || git -C "$ROOT" worktree add -q -b "$r" "$WT/wt-$r" main
    done
    git -C "$ROOT" worktree list ;;
  send)
    r="$2"; task="$3"; dir="$WT/wt-$r"
    git -C "$dir" merge -q --no-edit main >/dev/null 2>&1 || true   # pick up latest decisions
    msg="$(preamble "$r") $task"
    # engine per role, override with ENGINE_<role>=codex|agy|copilot|opencode
    eng_var="ENGINE_$r"; eng="${!eng_var:-$(default_engine "$r")}"
    case "$eng" in
      codex)   ( cd "$dir" && codex exec -s workspace-write -o "$LOGS/$r.last" "$msg" ) ;;
      agy)     ( cd "$dir" && agy -p "$msg" --dangerously-skip-permissions ) ;;
      copilot) ( cd "$dir" && copilot -p "$msg" --allow-all-tools -s ) ;;
      opencode) ( cd "$dir" && $(model_for "$r") --title "$r" "$msg" ) ;;
    esac >"$LOGS/$r.log" 2>&1 &
    echo $! > "$LOGS/$r.pid"; echo "$r started (pid $!)" ;;
  status)
    for r in $ROLES; do
      dir="$WT/wt-$r"; f="$dir/coordination/status/$r.md"
      running=$(kill -0 "$(cat "$LOGS/$r.pid" 2>/dev/null)" 2>/dev/null && echo running || echo idle)
      echo "== $r [$running] $(git -C "$dir" log -1 --format='%h %s' 2>/dev/null)"
      [ -f "$f" ] && cat "$f" || echo "(no status yet)"
      git -C "$ROOT" diff --stat main..."$r" 2>/dev/null | tail -1
    done ;;
  test)
    ( cd "$WT/wt-$2" && "$WT/.venv/bin/python" -m pytest -q 2>&1 | tail -3 ) ;;
  log)
    tail -n "${3:-20}" "$LOGS/$2.log" ;;
  *) sed -n '2,7p' "$0" ;;
esac
