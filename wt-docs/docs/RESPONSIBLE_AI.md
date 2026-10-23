# Responsible AI & Humans in Command

> **Core Principle:** *AI assists. People decide.*

RampReady is a strategic planning aid designed to forecast aircraft parking demand for an FBO during major events (Super Bowl LXI at SoFi Stadium, February 2027). The system is built around strict ethical, privacy, and operational boundaries to ensure human authority, safety, and accountability.

---

## 1. Five Absolute Rules (Coded & Displayed)

These rules are enforced both in application logic and prominently displayed in the user interface:

1. **Strategic Planning Only — No Aircraft Movement Authorization:**
   The tool plans and flags capacity saturation risks. It **never** refuses, accepts, moves, or authorizes any aircraft. It replaces no airport or FAA safety procedure and holds zero operational control.

2. **Spot-Agnostic Aggregate Modeling — No Individual Spot Assignment:**
   The tool **never** assigns physical parking spots or ramp coordinates to specific aircraft. Capacity and demand are tracked solely in aggregate **Parking Units (PU)** (Light = 1.0, Midsize = 1.5, Large = 2.5).

3. **Privacy by Design — Zero Personal or Aircraft-Specific Data:**
   The system processes **no** passenger names, VIP identities, crew information, tail numbers (N-numbers), aircraft owners, or individual flight plans. Aircraft are counted and modeled strictly by generic size class.

4. **Transparent Uncertainty — No Single-Number Predictions:**
   Demand is inherently stochastic. Forecasts are never presented as a single point estimate, but always as probabilistic **P10 / P50 / P90** percentile ranges generated via Monte Carlo simulation (1,000 draws). All modeling assumptions are public, auditable, and adjustable.

5. **Human Approval Gate — Mandatory Audit Trail:**
   Every automated recommendation is initially flagged as `PROPOSED`. No recommendation takes effect without explicit human action:
   - Status transitions strictly require human choice: `APPROVED`, `MODIFIED`, or `REJECTED`.
   - Every decision requires/records a human note and timestamp in an auditable decision log (`decision_log.csv`).

---

## 2. LLM Briefing Guardrails

RampReady includes an optional executive briefing generator powered by an LLM with strict safety constraints:

- **Grounded Only in Computed Metrics:** The LLM is provided solely with computed numerical outputs (JSON summary of P10/P50/P90 arrivals, peak occupancy, unserved PU, fuel volume, staffing requirements). It is prohibited from hallucinating or estimating external figures.
- **Strictly Descriptive, Never Prescriptive on Operations:** The LLM is prohibited from instructing staff to refuse, accept, or reposition specific flights, and from referencing individuals or operators.
- **Zero-Dependency Fallback:** If no API key (`ANTHROPIC_API_KEY`) is configured, the application falls back immediately to a deterministic rule-based template. The entire application remains 100% operational without an LLM.

---

## 3. Answer to the Jury Question

> **Jury Question:** *"What decision should your AI never be allowed to make?"*
>
> **Answer:**
> *"Our tool never decides which aircraft is accommodated, refused, moved or allowed to move. It tells Maria: **Saturday between 2 PM and 8 PM, you will likely be 8 to 15 spots short.** She decides who is accommodated, who is redirected and how, within the airport's safety procedures. Any decision touching an aircraft, a crew or passengers stays human."*

---

## 4. System Safeguards in the Interface

- **Permanent Banner:** Displayed across every view of the Streamlit application:
  > *"Planning aid only. Authorizes no aircraft movement. Final decision: the manager."*
- **Explainable Rules:** Every recommendation cites the exact deterministic rule and threshold that triggered it (e.g., *"because P90 occupancy exceeds capacity by 14 PU on Sat 18:00"*), alongside an explicit confidence level (`low` / `medium` / `high`).
- **Full Operational Override:** Assumptions can be updated or overridden in real time by the operations manager via sliders and scenario selectors.
