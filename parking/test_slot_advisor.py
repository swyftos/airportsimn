import json

import numpy as np

import parking_optimizer as po
import slot_advisor as sa

A = dict(po.load_assumptions(), mc_runs=500)


def test_drop_and_go_conserves_and_frees_parking():
    rng = np.random.default_rng(3)
    arr, dep = rng.uniform(2, 6, (50, 7, 3)), rng.uniform(2, 6, (50, 7, 3))
    extra = np.full((7, 3), 0.3)
    a2, d2, accepted, movements = sa.drop_and_go(arr, dep, 0.2, extra, extra)
    assert np.allclose(a2, arr)
    assert np.allclose(d2.sum((1, 2)), dep.sum((1, 2)))  # each accepting aircraft leaves once, earlier
    assert np.allclose(movements, 2 * accepted)
    before, _ = po.ramp_sim(arr, dep, np.full(7, np.inf), A)
    after, _ = po.ramp_sim(a2, d2, np.full(7, np.inf), A)
    assert after[:, 3].mean() < before[:, 3].mean()


def test_early_arrival_does_not_free_game_day_parking():
    rows = sa.run(po.load_demand(), A)
    for scen in ("Medium", "High"):
        early = [r for r in rows if r["scenario"] == scen and r["lever"] == "early_arrival"]
        assert early[-1]["unaccommodated_mean"] >= early[0]["unaccommodated_mean"]
        assert early[-1]["game_day_su_p50"] >= early[0]["game_day_su_p50"] - 0.5
        drop = [r for r in rows if r["scenario"] == scen and r["lever"] == "drop_and_go"]
        assert [r["game_day_su_p50"] for r in drop] == sorted((r["game_day_su_p50"] for r in drop), reverse=True)


def test_recommendations_are_offers_a_manager_approves():
    recs = sa.recommend(sa.run(po.load_demand(), A), A)
    actions = [x for r in recs.values() for x in r["actions"]]
    assert actions and all(x["requires_human_approval"] and x["approver"] for x in actions)
    assert "never" in json.dumps(recs)
