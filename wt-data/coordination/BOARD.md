# Board

Roles: `data` (OpenCode + Gemini) · `model` (Codex) · `docs` (OpenCode + Copilot) · `app` (Claude Code, supervisor + integration).

Decisions D1–D6 from the plan review are merged into AGENTS.md (search "D1"…"D6").

## Tasks

| id | role | task | state |
|---|---|---|---|
| T1 | data | `config/assumptions.yaml` with all plan values + D1, D3 | TODO |
| T2 | data | `data/generate.py` stub CSVs in contract format (seeded) | TODO |
| T3 | model | skeletons of the 5 modules with frozen signatures + D2, D4 | TODO |
| T4 | docs | run.sh (venv, install, generate if missing, streamlit run); review README.md for accuracy vs AGENTS.md | TODO |
| T5 | app | Streamlit skeleton, 7 tabs, banner, decision log CSV | TODO |
| T6 | data | Calibrate on real data, see coordination/research_sources.md: export ATADS daily VNY Feb 2022 vs control weeks, derive baseline_day and observed multiplier, cross-check regional extra demand (300/550/850) and departure wave shape; open every source before citing; cite in docs/ASSUMPTIONS.md; update assumptions.yaml only if numbers disagree, and say so in status | TODO |
