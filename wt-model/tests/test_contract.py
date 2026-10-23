"""Forecast and occupancy invariants against the shared YAML assumptions."""

from pathlib import Path

import numpy as np
import pytest
import yaml

from model.forecast import forecast
from model.occupancy import compute_occupancy


@pytest.fixture(scope="module")
def cfg():
    root = Path(__file__).resolve().parents[1]
    source = root / "config" / "assumptions.yaml"
    if not source.is_file():
        source = root.parent / "wt-data" / "config" / "assumptions.yaml"
    with source.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.mark.parametrize("scenario", ["baseline", "low", "medium", "high"])
def test_hourly_draws_and_conservation(cfg, scenario):
    predicted = forecast(scenario, cfg, n_sims=200, seed=42)
    occupancy = compute_occupancy(predicted, cfg)
    arrivals = predicted.attrs["sims"]
    departures = occupancy.attrs["departure_sims"]
    parking = np.array([cfg["aircraft_classes"][name]["parking_up"]
                        for name in ("light", "mid", "large")])
    demand = occupancy.attrs["demand_up_sims"]

    assert len(predicted) == len(cfg["arrival_hourly_profile"]) * 7
    assert arrivals.shape == departures.shape == (200, len(predicted), 3)
    assert np.any(arrivals[0] != arrivals[1])
    assert np.array_equal(demand, np.cumsum(arrivals - departures, axis=1) @ parking)
    assert np.all(demand >= 0)
    assert np.all(departures >= 0)
    for prefix in ("arrivals", "occupancy_up"):
        frame = predicted if prefix == "arrivals" else occupancy
        assert (frame[f"{prefix}_p10"] <= frame[f"{prefix}_p50"]).all()
        assert (frame[f"{prefix}_p50"] <= frame[f"{prefix}_p90"]).all()
    assert np.allclose(occupancy["occupancy_unserved_up_p50"],
                       np.maximum(occupancy["occupancy_up_p50"] - occupancy["capacity_up"], 0))
    assert np.allclose(occupancy["occupancy_unserved_up_p90"],
                       np.maximum(occupancy["occupancy_up_p90"] - occupancy["capacity_up"], 0))
    assert (occupancy["staff_needed"] <= cfg["resources"]["max_ramp_agents_per_shift"]).all()
    assert (occupancy[["fuel_gal_p50", "fuel_gal_p90"]] >= 0).all().all()
    assert np.array_equal(
        predicted["departures_p50"].to_numpy(),
        np.percentile(departures.sum(axis=2), cfg["uncertainty"]["percentile_median"], axis=0),
    )


def test_scenario_peak_order(cfg):
    peaks = {
        scenario: compute_occupancy(forecast(scenario, cfg, n_sims=200, seed=42), cfg)
        ["occupancy_up_p50"].max()
        for scenario in ("low", "medium", "high")
    }
    assert peaks["high"] >= peaks["medium"] >= peaks["low"]


def test_deterministic_seed_and_validation(cfg):
    first = forecast("low", cfg, n_sims=20, seed=42)
    again = forecast("low", cfg, n_sims=20, seed=42)
    assert np.array_equal(first.attrs["sims"], again.attrs["sims"])
    with pytest.raises(ValueError, match="Unknown scenario"):
        forecast("unknown", cfg)
    with pytest.raises(ValueError, match="positive"):
        forecast("low", cfg, n_sims=0)
