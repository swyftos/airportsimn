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


def test_departure_delay_conserves_aircraft():
    rng = np.random.default_rng(1)
    dep = rng.uniform(0, 20, (50, 7, 3))
    shifted, pushed = po.shift_departures(dep, A)
    first = int(A["delay_24h_first_day"])
    assert np.allclose(shifted.sum((1, 2)) + pushed.sum(1), dep.sum((1, 2)))
    assert np.allclose(shifted[:, :first], dep[:, :first])
    assert np.allclose(shifted[:, first], dep[:, first] * (1 - A["delay_24h_share"]))


def test_delay_variant_keeps_standard_schema_and_more_aircraft_remain():
    carry_std, carry_delay = {}, {}
    table, _ = po.run(po.load_demand(), A, carryover=carry_std)
    d_table, d_recs = po.run(po.load_demand(), A, "departure_delay_24h", carry_delay)
    assert list(table.columns) == list(d_table.columns) and len(table) == len(d_table)
    assert all(x["requires_human_approval"] for r in d_recs.values() for x in r["actions"])
    for s in carry_std:
        assert carry_delay[s]["aircraft_remaining_p50"] > carry_std[s]["aircraft_remaining_p50"]
        assert carry_delay[s]["departures_pushed_past_window_p50"] > 0


def test_ordinary_week_uses_p2_baseline():
    ordinary = po.load_ordinary_demand()
    table, carry = po.run_ordinary(ordinary, A)
    assert len(table) == 7 and (table["data_status"] == "provisional").all()
    assert (table["parking_demand_su_p10"] <= table["parking_demand_su_p90"]).all()
    assert carry["opening_aircraft"] == A["initial_transient_aircraft"]


def test_ramp_capacity_matches_area_derivation():
    derived = A["ramp_area_m2"] * A["usable_parking_share"] / A["m2_per_su"]
    assert round(derived) == A["ramp_capacity_su"]


def test_opening_inventory_follows_p2_baseline():
    implied = po.implied_opening_inventory(po.load_demand(), A)
    assert abs(implied - A["initial_transient_aircraft"]) < 0.1
