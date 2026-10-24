# FBO agent workflow in RampReady

The desk is organized around the questions an FBO agent must answer during a shift:

1. **Is parking at risk?** Overview leads with the first median capacity gap, the largest modeled gap, and the highest simulated exceedance chance. A zero median gap is not presented as zero risk. Parking values are size-weighted model units, not verified stands.
2. **What workload is coming?** The seven-day operations board shows arrivals, departures, daily parking and uncertainty, staffing, and fuel. A day drill-down pairs that daily model output with the separately labeled hourly illustration.
3. **What needs a person to decide?** The action plan exposes proposal owners, deadlines, evidence, stress cases, and a versioned planning review. Approval records a planning decision only. It does not reserve space, dispatch staff, spend money, or authorize aircraft movement.
4. **Can the inputs be trusted for this use?** The release strip and Evidence page show source class, provisional status, assumption ledger, and historical holdout metrics where available. Estimated and synthetic inputs are not described as observed FBO accuracy.

The source for the board is the active validated P2/P3 bundle. The UI does not rerun a model or merge customer bookings into forecasts. Uploaded pseudonymous visits remain separate until the producers regenerate a coherent release. The resource board uses native shift counts when supplied; sample bundles with only a peak staff count say so explicitly. Forecast ranges and exceedance probabilities display as unavailable when absent.

Scenario selection and the delayed-departure variant update the full desk together. The proposal comparison remains conditional on modeled capacity; staff and fuel outputs are workload estimates to check against actual rosters, trucks, and supply. Consequential operations remain with qualified people under local airport and FBO procedures.
