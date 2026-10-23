"""Contract checks for the first model skeleton."""

import numpy as np
import pandas as pd
import pytest

import model
from model.disruption import apply_disruption
from model.forecast import forecast
from model.impact import backtest, compare_plans
from model.occupancy import compute_occupancy
from model.recommend import recommend


FORECAST_COLUMNS = {
    "timestamp", "scenario", "arrivals_p10", "arrivals_p50", "arrivals_p90",
    "departures_p50", "arrivals_light", "arrivals_mid", "arrivals_large",
}
OCCUPANCY_COLUMNS = {
    "timestamp", "scenario", "occupancy_up_p10", "occupancy_up_p50",
    "occupancy_up_p90", "occupancy_unserved_up_p50",
    "occupancy_unserved_up_p90", "capacity_up", "movements_p90",
    "staff_needed", "fuel_gal_p50", "fuel_gal_p90",
}


@pytest.fixture
def stub_sources(tmp_path, monkeypatch):
    assumptions = tmp_path / "assumptions.yaml"
    assumptions.write_text("resources: {}\n", encoding="utf-8")
    monkeypatch.setattr(model, "_ASSUMPTIONS_PATH", assumptions)

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("model.forecast._DATA_DIR", data_dir)
    sample = pd.DataFrame(
        [{
            "timestamp": "2027-02-09T00:00",
            "scenario": "low",
            "arrivals_p10": 1.0,
            "arrivals_p50": 2.0,
            "arrivals_p90": 3.0,
            "departures_p50": 0.0,
            "arrivals_light": 1.0,
            "arrivals_mid": 1.0,
            "arrivals_large": 0.0,
        }]
    )
    sample.to_csv(data_dir / "event_hourly.csv", index=False)
    return assumptions


def test_forecast_and_occupancy_contract(stub_sources):
    predicted = forecast("low", {}, n_sims=4)
    assert set(predicted.columns) == FORECAST_COLUMNS
    assert predicted.attrs["sims"].shape == (4, len(predicted), 3)
    assert isinstance(predicted.attrs["sims"], np.ndarray)
    assert (predicted["arrivals_p10"] <= predicted["arrivals_p50"]).all()
    assert (predicted["arrivals_p50"] <= predicted["arrivals_p90"]).all()

    occupancy = compute_occupancy(predicted, {})
    assert set(occupancy.columns) == OCCUPANCY_COLUMNS
    assert len(occupancy) == len(predicted)
    assert (occupancy["timestamp"] == predicted["timestamp"]).all()
    assert (occupancy["scenario"] == predicted["scenario"]).all()
    complete = occupancy.dropna(subset=[
        "occupancy_up_p10", "occupancy_up_p50", "occupancy_up_p90"
    ])
    assert (complete["occupancy_up_p10"] <= complete["occupancy_up_p50"]).all()
    assert (complete["occupancy_up_p50"] <= complete["occupancy_up_p90"]).all()


def test_other_public_signatures(stub_sources):
    predicted = forecast("low", {}, n_sims=2)
    occupancy = compute_occupancy(predicted, {})
    assert recommend(occupancy, {}) == []
    assert isinstance(compare_plans("low", {}), dict)
    assert set(backtest({})) == {"mape", "coverage_p10_p90", "peak_error_up"}
    disrupted = apply_disruption(predicted, "fog", {})
    assert set(disrupted.columns) == FORECAST_COLUMNS
    assert disrupted is not predicted


def test_missing_assumptions_has_clear_error(tmp_path, monkeypatch):
    missing = tmp_path / "assumptions.yaml"
    monkeypatch.setattr(model, "_ASSUMPTIONS_PATH", missing)
    with pytest.raises(FileNotFoundError, match="config/assumptions.yaml"):
        forecast("low", {})
