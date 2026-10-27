"""Pure math and pass/fail logic for the standalone bench hardware test.

MicroPython-safe: only ``math`` and complex numbers are used, so this module can
run on the ESP32 and under CPython in the unit tests. No hardware imports.
"""

import math

DEFAULT_TOL_PCT = 5.0
DEFAULT_TOL_DEG = 5.0
DEFAULT_DRIFT_PCT = 2.0
DEFAULT_DRIFT_DEG = 2.0
ADC_SATURATION_LIMIT = 32_700


def check(name, status, detail=""):
    """Return one JSON-ready check record."""
    return {"name": str(name), "status": str(status), "detail": str(detail)}


def _fmt(value, digits=2):
    """MicroPython-safe fixed-ish formatting for human-readable details."""
    return str(round(float(value), digits))


def expected_impedance(freq_hz, capacitance_f):
    """Expected impedance of an ideal capacitor: ``1 / (j * 2*pi*f*C)``."""
    freq_hz = float(freq_hz)
    capacitance_f = float(capacitance_f)
    if freq_hz <= 0:
        raise ValueError("frequency must be positive")
    if capacitance_f <= 0:
        raise ValueError("capacitance must be positive")
    return complex(0.0, -1.0 / (2.0 * math.pi * freq_hz * capacitance_f))


def is_saturated(real, imag, limit=ADC_SATURATION_LIMIT):
    """True when either AD5933 output register is at/near full scale."""
    return abs(float(real)) >= limit or abs(float(imag)) >= limit


def phase_deg(value):
    """Phase of a complex value in degrees, in ``[-180, 180]``."""
    return math.degrees(math.atan2(value.imag, value.real))


def wrap_deg(angle):
    """Wrap an angle in degrees into ``[-180, 180]``."""
    while angle > 180.0:
        angle -= 360.0
    while angle < -180.0:
        angle += 360.0
    return angle


def magnitude(value):
    return math.sqrt(value.real * value.real + value.imag * value.imag)


def mean_complex(values):
    if not values:
        raise ValueError("cannot average an empty sample set")
    real = 0.0
    imag = 0.0
    for value in values:
        real += value.real
        imag += value.imag
    count = float(len(values))
    return complex(real / count, imag / count)


def _std(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / float(len(values))
    variance = sum((value - mean) ** 2 for value in values) / float(len(values) - 1)
    return math.sqrt(variance)


def calibration_factor(expected, raw):
    """Return ``K`` such that ``Z = K / S`` for raw DFT value ``S``."""
    return expected * raw


def apply_calibration(raw, factor):
    if raw == 0:
        raise ValueError("cannot calibrate a zero raw measurement")
    return factor / raw


def _complex_record(value):
    mag = magnitude(value)
    return {
        "re": value.real,
        "im": value.imag,
        "mag": mag,
        "phase_deg": phase_deg(value),
    }


def summarize_samples(samples):
    """Summarise raw ``(real, imag)`` samples for the result payload."""
    values = [complex(float(real), float(imag)) for real, imag in samples]
    magnitudes = [magnitude(value) for value in values]
    mean = mean_complex(values)
    mean_mag = sum(magnitudes) / float(len(magnitudes))
    std_mag = _std(magnitudes)
    return {
        "n": len(values),
        "re_mean": mean.real,
        "im_mean": mean.imag,
        "mag_mean": mean_mag,
        "mag_std": std_mag,
        "mag_std_pct": (std_mag / mean_mag * 100.0) if mean_mag else 0.0,
        "min_mag": min(magnitudes),
        "max_mag": max(magnitudes),
    }


def evaluate(
    freq_hz,
    capacitance_f,
    samples,
    tol_pct=DEFAULT_TOL_PCT,
    tol_deg=DEFAULT_TOL_DEG,
    drift_pct=DEFAULT_DRIFT_PCT,
    drift_deg=DEFAULT_DRIFT_DEG,
):
    """Calibrate against the known capacitor and verify it on held-out samples.

    The first half of the samples derives ``K``; the second half is used to
    produce the reported impedance. That makes the check sensitive to drift and
    instability rather than trivially reusing the same samples to calibrate and
    verify. Absolute traceable accuracy still requires a second known component.
    """
    if len(samples) < 2:
        raise ValueError("at least two samples are required")
    split = len(samples) // 2
    if split < 1 or len(samples) - split < 1:
        raise ValueError("at least two samples are required")

    values = [complex(float(real), float(imag)) for real, imag in samples]
    calibration_values = values[:split]
    verification_values = values[split:]
    raw_cal = mean_complex(calibration_values)
    raw_verify = mean_complex(verification_values)

    expected = expected_impedance(freq_hz, capacitance_f)
    checks = []

    if raw_cal == 0 or raw_verify == 0:
        checks.append(
            check("stability", "fail", "zero raw measurement; check the fixture/AD5933")
        )
        return {
            "raw": summarize_samples(samples),
            "expected": _complex_record(expected),
            "calibration": None,
            "measured": None,
            "drift": None,
            "tolerances": {
                "mag_pct": tol_pct,
                "phase_deg": tol_deg,
                "drift_pct": drift_pct,
                "drift_deg": drift_deg,
            },
            "checks": checks,
        }

    factor_cal = calibration_factor(expected, raw_cal)
    factor_verify = calibration_factor(expected, raw_verify)
    measured = apply_calibration(raw_verify, factor_cal)

    factor_mag = magnitude(factor_cal)
    drift_mag_pct = (
        magnitude(factor_verify - factor_cal) / factor_mag * 100.0 if factor_mag else 0.0
    )
    drift_phase = abs(wrap_deg(phase_deg(factor_verify) - phase_deg(factor_cal)))

    mag_error_pct = abs(magnitude(measured) - magnitude(expected)) / magnitude(expected) * 100.0
    phase_error = abs(wrap_deg(phase_deg(measured) - phase_deg(expected)))

    if drift_mag_pct <= drift_pct and drift_phase <= drift_deg:
        checks.append(
            check(
                "stability",
                "pass",
                "K drift " + _fmt(drift_mag_pct) + "% / " + _fmt(drift_phase) + " deg",
            )
        )
    else:
        checks.append(
            check(
                "stability",
                "fail",
                "K drift "
                + _fmt(drift_mag_pct)
                + "% / "
                + _fmt(drift_phase)
                + " deg (limit "
                + _fmt(drift_pct)
                + "% / "
                + _fmt(drift_deg)
                + " deg)",
            )
        )

    measured_detail = (
        _fmt(magnitude(measured))
        + " ohm @ "
        + _fmt(phase_deg(measured))
        + " deg (error "
        + _fmt(mag_error_pct)
        + "% / "
        + _fmt(phase_error)
        + " deg"
    )
    if mag_error_pct <= tol_pct and phase_error <= tol_deg:
        checks.append(check("impedance", "pass", measured_detail + ")"))
    else:
        checks.append(
            check(
                "impedance",
                "fail",
                measured_detail
                + ", limit "
                + _fmt(tol_pct)
                + "% / "
                + _fmt(tol_deg)
                + " deg)",
            )
        )

    return {
        "raw": summarize_samples(samples),
        "expected": _complex_record(expected),
        "calibration": {
            "k_re": factor_cal.real,
            "k_im": factor_cal.imag,
            "k_mag": factor_mag,
            "k_phase_deg": phase_deg(factor_cal),
            "k_verify_re": factor_verify.real,
            "k_verify_im": factor_verify.imag,
        },
        "measured": _complex_record(measured),
        "drift": {
            "mag_pct": drift_mag_pct,
            "phase_deg": drift_phase,
        },
        "tolerances": {
            "mag_pct": tol_pct,
            "phase_deg": tol_deg,
            "drift_pct": drift_pct,
            "drift_deg": drift_deg,
        },
        "checks": checks,
    }
