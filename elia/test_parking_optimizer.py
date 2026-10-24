import numpy as np

import parking_optimizer as po

A = po.load_assumptions()
A["mc_runs"] = 500


def test_unlimited_capacity_accommodates_everyone():
    rng = np.random.default_rng(0)
    arr = rng.uniform(0, 20, (50, 7, 3))
    dep = rng.uniform(0, 20, (50, 7, 3))
    _, unacc = po.ramp_sim(arr, dep, np.full(7, np.inf), A)
    assert np.allclose(unacc, 0)


def test_tight_capacity_is_respected_and_counts_overflow():
    arr = np.full((1, 7, 3), 30.0)
    dep = np.zeros((1, 7, 3))
    peak_su, unacc = po.ramp_sim(arr, dep, np.full(7, 90.0), A)
    assert (peak_su <= 90 + 1e-9).all()
    assert unacc.sum() > 0


def test_every_action_needs_a_human():
    table, recs = po.run(po.load_demand(), A)
    actions = [x for r in recs.values() for x in r["actions"]]
    assert actions and all(x["requires_human_approval"] and x["approver"] for x in actions)
    assert set(table["risk_level"]) <= {"Low", "Medium", "High"}


def test_prepared_plan_never_worse_on_aircraft_accommodated():
    _, recs = po.run(po.load_demand(), A)
    for r in recs.values():
        i = r["impact"]
        assert i["ai_preparation"]["unaccommodated_aircraft"]["mean"] <= i["no_preparation"]["unaccommodated_aircraft"]["mean"]
