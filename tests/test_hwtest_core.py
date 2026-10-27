"""Pure bench-test math: capacitor calibration and pass/fail checks."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

HWTEST = Path(__file__).resolve().parents[1] / "firmware" / "mp-firm" / "hwtest"


def _load_core():
    spec = importlib.util.spec_from_file_location(
        "hwtest_core_under_test", HWTEST / "hwtest_core.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def core():
    return _load_core()


def test_expected_impedance_of_point_one_microfarad_at_50khz(core):
    z = core.expected_impedance(50_000.0, 0.1e-6)
    assert z.real == pytest.approx(0.0, abs=1e-9)
    assert z.imag == pytest.approx(-31.8309886, rel=1e-6)
    assert core.magnitude(z) == pytest.approx(31.8309886, rel=1e-6)
    assert core.phase_deg(z) == pytest.approx(-90.0)


def test_expected_impedance_scales_with_frequency(core):
    assert core.magnitude(core.expected_impedance(5_000.0, 0.1e-6)) == pytest.approx(
        318.309886, rel=1e-6
    )
    assert core.magnitude(core.expected_impedance(1_000.0, 0.1e-6)) == pytest.approx(
        1591.549431, rel=1e-6
    )


def test_expected_impedance_rejects_bad_inputs(core):
    with pytest.raises(ValueError):
        core.expected_impedance(0, 0.1e-6)
    with pytest.raises(ValueError):
        core.expected_impedance(50_000, 0)


def test_calibration_factor_and_restore(core):
    expected = core.expected_impedance(50_000.0, 0.1e-6)
    raw = complex(1000.0, -250.0)
    factor = core.calibration_factor(expected, raw)
    assert core.apply_calibration(raw, factor) == pytest.approx(expected)


def test_evaluate_passes_with_stable_ideal_samples(core):
    expected = core.expected_impedance(50_000.0, 0.1e-6)
    raw = complex(1000.0, 0.0)
    samples = [(raw.real, raw.imag) for _ in range(16)]

    result = core.evaluate(50_000.0, 0.1e-6, samples)

    assert result["measured"]["mag"] == pytest.approx(core.magnitude(expected))
    assert result["measured"]["phase_deg"] == pytest.approx(-90.0)
    assert result["drift"]["mag_pct"] == pytest.approx(0.0)
    assert [check["status"] for check in result["checks"]] == ["pass", "pass"]
    assert result["raw"]["n"] == 16


def test_evaluate_fails_when_second_half_drifts(core):
    expected = core.expected_impedance(50_000.0, 0.1e-6)
    raw = complex(1000.0, 0.0)
    samples = [(raw.real, raw.imag) for _ in range(8)]
    samples += [(raw.real * 1.2, raw.imag) for _ in range(8)]

    result = core.evaluate(50_000.0, 0.1e-6, samples)

    by_name = {check["name"]: check for check in result["checks"]}
    assert by_name["stability"]["status"] == "fail"
    assert by_name["impedance"]["status"] == "fail"
    assert result["measured"]["mag"] < core.magnitude(expected)


def test_evaluate_rejects_zero_raw_data(core):
    result = core.evaluate(50_000.0, 0.1e-6, [(0.0, 0.0), (0.0, 0.0)])
    assert result["calibration"] is None
    assert result["checks"][0]["status"] == "fail"


def test_evaluate_requires_two_samples(core):
    with pytest.raises(ValueError):
        core.evaluate(50_000.0, 0.1e-6, [(1.0, 0.0)])


def test_is_saturated(core):
    assert not core.is_saturated(1000, -1000)
    assert core.is_saturated(core.ADC_SATURATION_LIMIT, 0)
    assert core.is_saturated(0, -core.ADC_SATURATION_LIMIT)


def test_summarize_samples(core):
    summary = core.summarize_samples([(3.0, 4.0), (3.0, 4.0)])
    assert summary["n"] == 2
    assert summary["re_mean"] == pytest.approx(3.0)
    assert summary["im_mean"] == pytest.approx(4.0)
    assert summary["mag_mean"] == pytest.approx(5.0)
    assert summary["mag_std"] == pytest.approx(0.0)
    assert summary["mag_std_pct"] == pytest.approx(0.0)


def test_phase_wrap(core):
    assert math.isclose(core.wrap_deg(370.0), 10.0)
    assert math.isclose(core.wrap_deg(-370.0), -10.0)
