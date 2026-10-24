# Shift Board status
Views: Today timeline and live board; Week plan; Evidence.
Features: scenario, day, demo clock, dark/light theme, per-day weather with next-day carryover.
Movements: add, edit, mark landed/departed, delete local entry, CSV import/export; saved in localStorage.
Planning: 90% ranges, ordinary-week comparison, peak windows, day-specific proposals with acknowledge/dismiss notes.
Run: `cd agent_codex && python3 -m http.server`, then open the displayed local URL.
Verified: JavaScriptCore rendered every view for all seven days and three scenarios; midnight lookahead and quoted CSV passed.
Known limits: hourly shape and 2027 game-day restriction are assumptions in the supplied data; no observed hourly feed.
Known test gap: this sandbox blocked opening an HTTP listener, so browser layout testing was unavailable here.
