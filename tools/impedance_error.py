#!/usr/bin/env python3
"""Measure live capacitor impedance error and project it onto an EIT map.

The bench rig has no multiplexer. A single known capacitor is connected to the
AD5933 front end in the same configuration used for calibration. The separate
``firmware/mp-firm/imperr`` firmware returns every individual complex sample at
one frequency, so 40 repeated readings of the same physical location become the
40 boundary values of a pseudo-frame.

The tool then:

1. compares the 40 measured magnitudes with the ideal capacitor magnitude,
2. reports systematic offset, repeatability and drift,
3. reconstructs the pseudo-frame against a constant ideal baseline with the
   real pyEIT solver, so any non-zero map is the map error caused by the
   impedance error.

Outputs (CSV, JSON, PNG, Markdown) go to ``crimson_veil/impedance-error`` by
default. Nothing is committed.

Examples:
    python tools/impedance_error.py upload
    python tools/impedance_error.py measure --freqs 1000,5000,10000,50000
    python tools/impedance_error.py project
    python tools/impedance_error.py run
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = Path(__file__).resolve().parent
HWTEST_DIR = ROOT / "firmware" / "mp-firm" / "hwtest"
IMPERR_DIR = ROOT / "firmware" / "mp-firm" / "imperr"
DEFAULT_OUT = ROOT / "crimson_veil" / "impedance-error"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import hwtest  # noqa: E402  (sibling bench serial helpers)

DEFAULT_SWEEP_START = 1_000.0
DEFAULT_SWEEP_STOP = 100_000.0
DEFAULT_SWEEP_POINTS = 50
DEFAULT_DETAIL_COUNT = 5
DEFAULT_C_F = 0.1e-6
DEFAULT_SAMPLES = 40
DEFAULT_RANGE = "1vpp"
DEFAULT_DISCARD = 1
DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT = 10.0
DEFAULT_GRID = 96
DEFAULT_TRIALS = 200
DEFAULT_SEED = 20261106
ELECTRODES = 8
CAPTURE_FILE = "capture.json"
REPORT_FILE = "report.md"
SUMMARY_FILE = "summary.json"
CSV_FILE = "samples.csv"

IMPERR_UPLOAD = (
    (IMPERR_DIR / "main.py", "main.py"),
    (HWTEST_DIR / "ad5933_driver.py", "ad5933_driver.py"),
    (HWTEST_DIR / "status_led.py", "status_led.py"),
)


class ImpedanceErrorToolError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# Serial and upload
# --------------------------------------------------------------------------- #


def _mpremote_command() -> list[str]:
    candidates = [
        Path(sys.executable).with_name("mpremote"),
        ROOT / "firmware" / "mp-firm" / ".venv" / "bin" / "mpremote",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return [str(candidate)]
    found = shutil.which("mpremote")
    if found:
        return [found]
    return [sys.executable, "-m", "mpremote"]


def _run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ImpedanceErrorToolError(
            "command failed: " + " ".join(command) + ": " + detail
        )


def upload_firmware(port: str, timeout: float) -> None:
    """Copy the imperr bench firmware and reset the ESP32."""
    missing = [str(source) for source, _ in IMPERR_UPLOAD if not source.is_file()]
    if missing:
        raise ImpedanceErrorToolError(
            "firmware files missing: " + ", ".join(missing)
        )
    mpremote = _mpremote_command()
    for source, destination in IMPERR_UPLOAD:
        _run(
            [
                *mpremote,
                "connect",
                port,
                "fs",
                "cp",
                str(source),
                ":" + destination,
            ]
        )
    try:
        subprocess.run(
            [
                *mpremote,
                "connect",
                port,
                "exec",
                "import machine; machine.reset()",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        pass


def _read_message(serial: hwtest.LineSerial, timeout: float) -> dict | None:
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        line = serial.read_line(min(remaining, 0.5))
        if line is None:
            continue
        text = line.strip()
        if not text.startswith("{"):
            continue
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(message, dict) and "type" in message:
            return message


def _wait_for(
    serial: hwtest.LineSerial,
    kinds: tuple[str, ...],
    timeout: float,
    seq: int | None = None,
) -> dict:
    deadline = time.monotonic() + timeout
    seen: list[str] = []
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            suffix = " (saw " + ", ".join(seen) + ")" if seen else ""
            raise ImpedanceErrorToolError(
                "timed out waiting for " + ", ".join(kinds) + suffix
            )
        message = _read_message(serial, remaining)
        if message is None:
            continue
        kind = str(message.get("type"))
        if kind not in seen:
            seen.append(kind)
        if kind in ("imperr_error", "hwtest_error", "error"):
            raise ImpedanceErrorToolError(str(message.get("message", kind)))
        if kind in kinds and (seq is None or message.get("seq") == seq):
            return message
        if kind == "hwtest_hello" and "imperr_hello" in kinds:
            raise ImpedanceErrorToolError(
                "the ESP32 is running the hwtest firmware, not imperr. "
                "Run this tool's upload command first."
            )


def _open_serial(port: str, timeout: float) -> hwtest.LineSerial:
    try:
        return hwtest.LineSerial(port, DEFAULT_BAUD, timeout)
    except OSError as exc:
        raise ImpedanceErrorToolError(f"could not open {port}: {exc}") from exc


def _identify(serial: hwtest.LineSerial, timeout: float) -> dict:
    serial.write_line({"type": "imperr_identify"})
    return _wait_for(serial, ("imperr_hello",), timeout)


# --------------------------------------------------------------------------- #
# Acquisition
# --------------------------------------------------------------------------- #


def _parse_freqs(text: str) -> list[float]:
    freqs: list[float] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = float(part)
        except ValueError as exc:
            raise ImpedanceErrorToolError(f"bad frequency: {part!r}") from exc
        if value <= 0:
            raise ImpedanceErrorToolError(f"frequency must be positive: {part!r}")
        if value not in freqs:
            freqs.append(value)
    if not freqs:
        raise ImpedanceErrorToolError("no frequencies given")
    return freqs


def _sweep_freqs(start: float, stop: float, points: int) -> list[float]:
    if start <= 0 or stop <= start:
        raise ImpedanceErrorToolError("sweep must satisfy 0 < start < stop")
    if points < 2:
        raise ImpedanceErrorToolError("sweep needs at least 2 points")
    ratio = (stop / start) ** (1.0 / (points - 1))
    freqs: list[float] = []
    for index in range(points):
        value = start * (ratio**index)
        value = float(round(value, 1))
        if not freqs or value != freqs[-1]:
            freqs.append(value)
    if freqs[-1] != float(round(stop, 1)):
        freqs.append(float(round(stop, 1)))
    return freqs


def _frequency_list(args: argparse.Namespace) -> list[float]:
    if getattr(args, "freqs", None):
        return _parse_freqs(args.freqs)
    return _sweep_freqs(args.sweep_start, args.sweep_stop, args.sweep_points)


def _detail_indices(count: int, detail_count: int) -> list[int]:
    if count <= 0:
        return []
    if detail_count >= count:
        return list(range(count))
    if detail_count <= 1:
        return [0]
    return sorted(
        {
            round(index * (count - 1) / (detail_count - 1))
            for index in range(detail_count)
        }
    )


def measure_frequencies(
    port: str | None,
    freqs: list[float],
    samples: int,
    range_name: str,
    discard: int,
    timeout: float,
    capacitance_f: float,
    out_dir: Path,
) -> dict:
    if samples < 1:
        raise ImpedanceErrorToolError("--samples must be at least 1")
    if discard < 0:
        raise ImpedanceErrorToolError("--discard must be non-negative")

    port = hwtest.find_port(port)
    serial = _open_serial(port, timeout)
    try:
        hello = _identify(serial, timeout)
        if not str(hello.get("firmware", "")).startswith("imperr"):
            raise ImpedanceErrorToolError(
                "unexpected firmware: " + repr(hello.get("firmware"))
            )

        measurements = []
        for index, frequency in enumerate(freqs, start=1):
            serial.write_line(
                {
                    "type": "imperr_run",
                    "seq": index,
                    "f": frequency,
                    "samples": samples,
                    "range": range_name,
                    "discard": discard,
                    "apply_calibration": False,
                }
            )
            point_timeout = max(timeout, 10.0 + 0.25 * samples)
            result = _wait_for(
                serial, ("imperr_result",), point_timeout, seq=index
            )
            if result.get("status") != "pass":
                raise ImpedanceErrorToolError(
                    f"{frequency:g} Hz acquisition failed: "
                    + str(result.get("error"))
                )
            if len(result.get("samples", [])) != samples:
                raise ImpedanceErrorToolError(
                    f"{frequency:g} Hz returned "
                    f"{len(result.get('samples', []))} of {samples} samples"
                )
            measurements.append(result)
            print(
                f"  {frequency:>9.0f} Hz  {samples} points  "
                f"temp {result.get('temp_ad5933_c')} C"
            )

        try:
            serial.write_line({"type": "imperr_stop"})
        except OSError:
            pass
    finally:
        serial.close()

    capture = {
        "captured_at": datetime.now(UTC).isoformat(),
        "port": port,
        "firmware": hello,
        "samples_requested": samples,
        "discard": discard,
        "range": range_name,
        "c_f": capacitance_f,
        "measurements": measurements,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / CAPTURE_FILE).write_text(json.dumps(capture, indent=2))
    return capture


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #


def _ideal_impedance(frequency: float, capacitance_f: float) -> complex:
    return complex(0.0, -1.0 / (2.0 * math.pi * frequency * capacitance_f))


def _device_factors(hello: dict) -> list[tuple[float, complex]]:
    factors = []
    for item in (hello.get("calibration") or {}).get("factors") or []:
        try:
            factors.append(
                (
                    float(item["f"]),
                    complex(float(item["k_re"]), float(item["k_im"])),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(factors)


def _select_device_factor(
    hello: dict,
    reference_frequency: float | None,
) -> tuple[complex | None, float | None]:
    factors = _device_factors(hello)
    if not factors:
        return None, None
    if reference_frequency is None:
        return factors[0][1], factors[0][0]
    frequency, factor = min(
        factors, key=lambda item: abs(item[0] - reference_frequency)
    )
    return factor, frequency


def _interpolate_factor(
    factors: list[tuple[float, complex]],
    frequency: float,
) -> complex:
    """Log-magnitude and phase interpolation across calibration points."""
    if len(factors) == 1:
        return factors[0][1]
    ordered = sorted(factors)
    if frequency <= ordered[0][0]:
        (f0, k0), (f1, k1) = ordered[0], ordered[1]
    elif frequency >= ordered[-1][0]:
        (f0, k0), (f1, k1) = ordered[-2], ordered[-1]
    else:
        for index in range(len(ordered) - 1):
            f0, k0 = ordered[index]
            f1, k1 = ordered[index + 1]
            if f0 <= frequency <= f1:
                break
    span = math.log(f1) - math.log(f0)
    if span == 0:
        return k0
    weight = (math.log(frequency) - math.log(f0)) / span
    magnitude = math.exp(
        math.log(abs(k0)) * (1.0 - weight) + math.log(abs(k1)) * weight
    )
    phase0 = math.atan2(k0.imag, k0.real)
    phase1 = math.atan2(k1.imag, k1.real)
    delta = phase1 - phase0
    while delta > math.pi:
        delta -= 2.0 * math.pi
    while delta < -math.pi:
        delta += 2.0 * math.pi
    phase = phase0 + delta * weight
    return complex(magnitude * math.cos(phase), magnitude * math.sin(phase))


def _prepare_calibration(
    capture: dict,
    capacitance_f: float,
    calibration_mode: str,
    reference_frequency: float | None,
) -> tuple[list[tuple[float, complex]] | None, str, float | None]:
    """Choose the calibration used for the sweep.

    ``auto`` interpolates between the available device calibration points so the
    front-end transfer is tracked across the range. A single point falls back to
    a constant factor, and ``ideal`` self-references each frequency.
    """
    hello = capture.get("firmware") or {}
    measurements = capture.get("measurements") or []
    if not measurements:
        raise ImpedanceErrorToolError("capture contains no measurements")

    if calibration_mode == "ideal":
        return None, "ideal", None

    factors = _device_factors(hello)
    if calibration_mode == "interpolate":
        if len(factors) >= 2:
            return factors, "interpolate", None
        if len(factors) == 1:
            return factors, "device", factors[0][0]
        raise ImpedanceErrorToolError(
            "interpolation needs at least one device calibration factor"
        )

    if calibration_mode == "device":
        if not factors:
            raise ImpedanceErrorToolError(
                "no device calibration factors available; run hwtest calibration "
                "or use --calibration auto/ideal"
            )
        factor, used_frequency = _select_device_factor(hello, reference_frequency)
        return [(used_frequency, factor)], "device", used_frequency

    if len(factors) >= 2:
        return factors, "interpolate", None
    if len(factors) == 1:
        return factors, "device", factors[0][0]

    first = measurements[0]
    frequency = float(first["f_hz"])
    samples = first.get("samples") or []
    if not samples:
        raise ImpedanceErrorToolError("first measurement has no samples")
    raw = [complex(float(s["raw_re"]), float(s["raw_im"])) for s in samples]
    split = max(1, len(raw) // 2)
    reference = sum(raw[:split], start=0j) / split
    if reference == 0:
        raise ImpedanceErrorToolError("zero raw reference; check the fixture")
    factor = _ideal_impedance(frequency, capacitance_f) * reference
    return [(frequency, factor)], "reference", frequency


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = fraction * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return float(ordered[lower] * (1.0 - weight) + ordered[upper] * weight)


def _linear_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    count = float(len(values))
    mean_x = (count - 1.0) / 2.0
    mean_y = sum(values) / count
    numerator = sum((index - mean_x) * (value - mean_y) for index, value in enumerate(values))
    denominator = sum((index - mean_x) ** 2 for index in range(len(values)))
    return numerator / denominator if denominator else 0.0


def analyze_measurement(
    measurement: dict,
    capacitance_f: float,
    calibration_factors: list[tuple[float, complex]] | None,
    resolved_mode: str,
    reference_frequency: float | None,
) -> dict:
    frequency = float(measurement["f_hz"])
    samples = measurement.get("samples") or []
    if not samples:
        raise ImpedanceErrorToolError(f"no samples at {frequency:g} Hz")
    raw = [complex(float(s["raw_re"]), float(s["raw_im"])) for s in samples]
    if any(value == 0 for value in raw):
        raise ImpedanceErrorToolError(f"zero raw sample at {frequency:g} Hz")

    ideal = _ideal_impedance(frequency, capacitance_f)
    if calibration_factors:
        if resolved_mode == "interpolate":
            factor = _interpolate_factor(calibration_factors, frequency)
        else:
            factor = calibration_factors[0][1]
        used_mode = resolved_mode
        used_reference = reference_frequency
    else:
        split = max(1, len(raw) // 2)
        reference = sum(raw[:split], start=0j) / split
        if reference == 0:
            raise ImpedanceErrorToolError("zero raw reference; check the fixture")
        factor = ideal * reference
        used_mode = "ideal"
        used_reference = frequency
    impedances = [factor / value for value in raw]
    magnitudes = [abs(value) for value in impedances]
    phases = [math.degrees(math.atan2(value.imag, value.real)) for value in impedances]
    ideal_mag = abs(ideal)
    ideal_phase = math.degrees(math.atan2(ideal.imag, ideal.real))
    errors = [value - ideal_mag for value in magnitudes]
    errors_pct = [100.0 * value / ideal_mag for value in errors]
    phase_errors = [_wrap_deg(phase - ideal_phase) for phase in phases]

    split = max(1, len(errors) // 2)
    first_half = statistics.fmean(errors[:split])
    second_half = statistics.fmean(errors[split:]) if split < len(errors) else first_half

    mean_error = statistics.fmean(errors)
    stdev = statistics.stdev(errors) if len(errors) > 1 else 0.0
    centered = [value - mean_error for value in errors]

    return {
        "f": frequency,
        "temp_ad5933_c": measurement.get("temp_ad5933_c"),
        "calibration_mode": used_mode,
        "reference_frequency_hz": used_reference,
        "calibration_factor": {"re": factor.real, "im": factor.imag},
        "ideal": {
            "re": ideal.real,
            "im": ideal.imag,
            "mag": ideal_mag,
            "phase_deg": ideal_phase,
        },
        "count": len(impedances),
        "raw_re": [value.real for value in raw],
        "raw_im": [value.imag for value in raw],
        "magnitudes": magnitudes,
        "phases_deg": phases,
        "errors_ohm": errors,
        "errors_pct": errors_pct,
        "phase_errors_deg": phase_errors,
        "errors_centered_ohm": centered,
        "first_half_mean_error_ohm": first_half,
        "second_half_mean_error_ohm": second_half,
        "half_drift_ohm": second_half - first_half,
        "mean_mag": statistics.fmean(magnitudes),
        "mean_error_ohm": mean_error,
        "mean_error_pct": statistics.fmean(errors_pct),
        "mean_phase_deg": statistics.fmean(phases),
        "mean_phase_error_deg": statistics.fmean(phase_errors),
        "std_error_ohm": stdev,
        "std_error_pct": statistics.stdev(errors_pct) if len(errors_pct) > 1 else 0.0,
        "min_error_ohm": min(errors),
        "max_error_ohm": max(errors),
        "median_error_ohm": statistics.median(errors),
        "p05_error_ohm": _percentile(errors, 0.05),
        "p95_error_ohm": _percentile(errors, 0.95),
        "drift_slope_ohm_per_point": _linear_slope(errors),
        "phase_drift_slope_deg_per_point": _linear_slope(phase_errors),
    }


def _wrap_deg(angle: float) -> float:
    while angle > 180.0:
        angle -= 360.0
    while angle < -180.0:
        angle += 360.0
    return angle


def _jsonable(value):
    if isinstance(value, complex):
        return {"re": value.real, "im": value.imag}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


# --------------------------------------------------------------------------- #
# Map projection
# --------------------------------------------------------------------------- #


def _scan_data(frequency: float, values: list[float]):
    from software.core.types import RawPoint, ScanData

    return ScanData(
        points=[
            RawPoint(freq_hz=frequency, real=float(value), imag=0.0)
            for value in values
        ],
        n_electrodes=ELECTRODES,
        frequency_hz=frequency,
        label="impedance-error pseudo-frame",
    )


def _map_values(solver, frequency: float, target: list[float], baseline: list[float]):
    cmap = solver.reconstruct(
        _scan_data(frequency, target),
        _scan_data(frequency, baseline),
    )
    import numpy as np

    return np.asarray(cmap.values, dtype=float)


def _map_metrics(values) -> dict:
    import numpy as np

    from software.pipeline import anomaly_score

    absolute = np.abs(values)
    peak = float(np.max(absolute)) if absolute.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(values)))) if values.size else 0.0
    row, column = np.unravel_index(int(np.argmax(absolute)), values.shape)
    threshold = 0.5 * peak
    area = float(np.mean(absolute >= threshold)) if peak else 0.0
    return {
        "peak": peak,
        "rms": rms,
        "anomaly_score": float(anomaly_score(values.tolist())),
        "peak_row": int(row),
        "peak_col": int(column),
        "area_fraction_at_half_peak": area,
    }


def _save_map_figure(values, destination: Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap

    from software.reconstruction.image import (
        HEATMAP_BLUE,
        HEATMAP_NEUTRAL,
        HEATMAP_RED,
    )

    def unit(rgb):
        return tuple(channel / 255.0 for channel in rgb)

    heat = LinearSegmentedColormap.from_list(
        "crimson_veil_eit",
        [unit(HEATMAP_BLUE), unit(HEATMAP_NEUTRAL), unit(HEATMAP_RED)],
    )
    values = np.asarray(values, dtype=float)
    scale = float(np.max(np.abs(values))) if values.size else 0.0
    if scale == 0.0:
        scale = 1.0
    xx, yy = np.meshgrid(
        np.linspace(-1.0, 1.0, values.shape[1]),
        np.linspace(1.0, -1.0, values.shape[0]),
    )
    shown = np.ma.masked_where(xx * xx + yy * yy > 1.0, values)
    fig, ax = plt.subplots(figsize=(5.2, 4.8), dpi=180)
    image = ax.imshow(
        shown,
        cmap=heat,
        vmin=-scale,
        vmax=scale,
        origin="upper",
        extent=[-1.0, 1.0, -1.0, 1.0],
        interpolation="nearest",
    )
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=9)
    colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.02)
    colorbar.set_label("Delta sigma (a.u.)", fontsize=8)
    colorbar.ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(destination)
    plt.close(fig)


def project_maps(
    analysis: list[dict],
    grid_size: int,
    trials: int,
    seed: int,
    detail_frequencies: set[float],
    out_dir: Path,
) -> list[dict]:
    import numpy as np

    from software.core.types import MeshConfig
    from software.reconstruction.image import conductivity_to_png
    from software.reconstruction.pyeit_solver import PyEITSolver

    solver = PyEITSolver(grid_size=grid_size)
    random_state = np.random.get_state()
    try:
        np.random.seed(seed)
        solver.setup(ELECTRODES, MeshConfig(n_electrodes=ELECTRODES))
    finally:
        np.random.set_state(random_state)

    rng = np.random.default_rng(seed)
    projections = []
    try:
        for item in analysis:
            frequency = item["f"]
            ideal_mag = item["ideal"]["mag"]
            magnitudes = item["magnitudes"]
            baseline = [ideal_mag] * len(magnitudes)
            nominal = _map_values(solver, frequency, magnitudes, baseline)
            centered = _map_values(
                solver,
                frequency,
                [ideal_mag + value for value in item["errors_centered_ohm"]],
                baseline,
            )

            bootstrap_peak = []
            bootstrap_rms = []
            for _ in range(trials):
                sample = rng.choice(item["errors_ohm"], size=len(magnitudes), replace=True)
                values = _map_values(
                    solver,
                    frequency,
                    [ideal_mag + float(value) for value in sample],
                    baseline,
                )
                metrics = _map_metrics(values)
                bootstrap_peak.append(metrics["peak"])
                bootstrap_rms.append(metrics["rms"])

            if frequency in detail_frequencies:
                nominal_png = out_dir / f"map-measured-{int(frequency)}.png"
                nominal_png.write_bytes(
                    conductivity_to_png(
                        _map_to_conductivity_map(nominal)
                    )
                )
                _save_map_figure(
                    nominal,
                    out_dir / f"map-measured-{int(frequency)}-figure.png",
                    f"Measured impedance error at {frequency:g} Hz",
                )
                _save_map_figure(
                    centered,
                    out_dir / f"map-centered-{int(frequency)}-figure.png",
                    f"Repeatability error at {frequency:g} Hz",
                )

            projections.append(
                {
                    "f": frequency,
                    "nominal": _map_metrics(nominal),
                    "centered": _map_metrics(centered),
                    "bootstrap": {
                        "trials": trials,
                        "peak_p05": _percentile(bootstrap_peak, 0.05),
                        "peak_p50": _percentile(bootstrap_peak, 0.50),
                        "peak_p95": _percentile(bootstrap_peak, 0.95),
                        "rms_p05": _percentile(bootstrap_rms, 0.05),
                        "rms_p50": _percentile(bootstrap_rms, 0.50),
                        "rms_p95": _percentile(bootstrap_rms, 0.95),
                    },
                }
            )
    finally:
        solver.close()
    return projections


def _map_to_conductivity_map(values):
    from software.core.types import ConductivityMap

    return ConductivityMap(values=values.tolist(), centered=True)


# --------------------------------------------------------------------------- #
# Graphs and report
# --------------------------------------------------------------------------- #


def _plot_results(
    analysis: list[dict],
    detail_frequencies: set[float],
    calibration_frequencies: list[float],
    out_dir: Path,
) -> None:
    import math

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for item in analysis:
        if item["f"] not in detail_frequencies:
            continue
        frequency = item["f"]
        indices = list(range(item["count"]))
        fig, ax = plt.subplots(figsize=(8.0, 4.2), dpi=160)
        ax.axhline(
            item["ideal"]["mag"],
            color="#1f4e79",
            linewidth=1.2,
            label="ideal |Z|",
        )
        ax.plot(indices, item["magnitudes"], "o-", color="#a61c1c", markersize=4,
                linewidth=0.9, label="measured |Z|")
        ax.set_xlabel("point index (same physical location)")
        ax.set_ylabel("|Z| (ohm)")
        ax.set_title(f"{frequency:g} Hz: intended vs measured magnitude")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(out_dir / f"magnitude-vs-point-{int(frequency)}.png")
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=160)
        ax.hist(item["errors_pct"], bins=12, color="#a61c1c", alpha=0.75,
                edgecolor="#5b0f0f")
        ax.axvline(0.0, color="#1f4e79", linewidth=1.2, label="ideal")
        ax.set_xlabel("magnitude error (%)")
        ax.set_ylabel("count")
        ax.set_title(
            f"{frequency:g} Hz error: mean {item['mean_error_pct']:.2f}%, "
            f"sigma {item['std_error_pct']:.2f}%"
        )
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(out_dir / f"error-histogram-{int(frequency)}.png")
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.2), dpi=160)
    frequencies = [item["f"] for item in analysis]
    means = [item["mean_error_ohm"] for item in analysis]
    stds = [item["std_error_ohm"] for item in analysis]
    ax.errorbar(frequencies, means, yerr=stds, fmt="o-", color="#a61c1c",
                capsize=3, markersize=4, linewidth=0.9, label="mean +/- sigma")
    ax.axhline(0.0, color="#1f4e79", linewidth=1.2, label="ideal")
    ax.set_xscale("log")
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel("magnitude error (ohm)")
    ax.set_title("Impedance error vs frequency")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "error-vs-frequency.png")
    plt.close(fig)

    capacitance_f = 1.0 / (
        2.0 * math.pi * analysis[0]["f"] * analysis[0]["ideal"]["mag"]
    )
    fig, (magnitude_ax, phase_ax) = plt.subplots(
        2, 1, figsize=(8.0, 6.4), dpi=160, sharex=True
    )
    if calibration_frequencies:
        low = min(calibration_frequencies)
        high = max(calibration_frequencies)
        for axis in (magnitude_ax, phase_ax):
            if frequencies[0] < low:
                axis.axvspan(frequencies[0], low, color="#f2e6d9", alpha=0.55)
            if frequencies[-1] > high:
                axis.axvspan(high, frequencies[-1], color="#f2e6d9", alpha=0.55)
            axis.axvline(low, color="#7f7f7f", linestyle="--", linewidth=0.9)
            axis.axvline(high, color="#7f7f7f", linestyle="--", linewidth=0.9)
    measured = [item["mean_mag"] for item in analysis]
    measured_sigma = [item["std_error_ohm"] for item in analysis]
    magnitude_ax.errorbar(
        frequencies, measured, yerr=measured_sigma, fmt="o", color="#a61c1c",
        markersize=4, capsize=3, label="measured mean +/- sigma",
    )
    dense = [
        10.0 ** (math.log10(frequencies[0])
                 + index * (math.log10(frequencies[-1])
                            - math.log10(frequencies[0])) / 300.0)
        for index in range(301)
    ]
    ideal = [1.0 / (2.0 * math.pi * frequency * capacitance_f) for frequency in dense]
    magnitude_ax.plot(dense, ideal, color="#1f4e79", linewidth=1.4,
                      label="ideal 1/(2 pi f C)")
    magnitude_ax.set_xscale("log")
    magnitude_ax.set_yscale("log")
    magnitude_ax.set_ylabel("|Z| (ohm)")
    magnitude_ax.set_title(
        f"0.1 uF frequency response over {frequencies[0]:g}-{frequencies[-1]:g} Hz"
    )
    magnitude_ax.grid(True, which="both", alpha=0.25)
    magnitude_ax.legend(fontsize=8)

    phase_ax.plot(frequencies, [item["mean_phase_deg"] for item in analysis],
                  "o-", color="#a61c1c", markersize=4, linewidth=0.9,
                  label="measured mean phase")
    phase_ax.axhline(-90.0, color="#1f4e79", linewidth=1.4,
                     label="ideal capacitor phase")
    phase_ax.set_xscale("log")
    phase_ax.set_xlabel("frequency (Hz)")
    phase_ax.set_ylabel("phase (deg)")
    phase_ax.grid(True, alpha=0.25)
    phase_ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "frequency-response.png")
    plt.close(fig)


def _plot_map_error(projections: list[dict], out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    frequencies = [item["f"] for item in projections]
    nominal_rms = [item["nominal"]["rms"] for item in projections]
    centered_rms = [item["centered"]["rms"] for item in projections]
    fig, ax = plt.subplots(figsize=(7.6, 4.4), dpi=160)
    ax.plot(frequencies, nominal_rms, "o-", color="#a61c1c", markersize=4,
            linewidth=0.9, label="measured (includes systematic offset)")
    ax.plot(frequencies, centered_rms, "o-", color="#1f4e79", markersize=4,
            linewidth=0.9, label="centred repeatability only")
    ax.set_xscale("log")
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel("map error RMS (a.u.)")
    ax.set_title("Conductivity-map error vs frequency")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "map-error-vs-frequency.png")
    plt.close(fig)


def _write_csv(analysis: list[dict], out_dir: Path) -> None:
    with (out_dir / CSV_FILE).open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "frequency_hz",
                "point_index",
                "raw_re",
                "raw_im",
                "z_mag_ohm",
                "z_phase_deg",
                "ideal_mag_ohm",
                "error_ohm",
                "error_pct",
                "phase_error_deg",
                "calibration_mode",
            ]
        )
        for item in analysis:
            for index in range(item["count"]):
                writer.writerow(
                    [
                        item["f"],
                        index,
                        item["raw_re"][index],
                        item["raw_im"][index],
                        item["magnitudes"][index],
                        item["phases_deg"][index],
                        item["ideal"]["mag"],
                        item["errors_ohm"][index],
                        item["errors_pct"][index],
                        item["phase_errors_deg"][index],
                        item["calibration_mode"],
                    ]
                )


def _fmt(value, digits=3) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def write_report(
    capture: dict,
    analysis: list[dict],
    projections: list[dict],
    capacitance_f: float,
    detail_frequencies: set[float],
    out_dir: Path,
) -> None:
    lines: list[str] = []
    lines.append("# Impedance error and conductivity-map projection")
    lines.append("")
    lines.append(f"Captured: {capture.get('captured_at', 'unknown')}")
    lines.append("")
    lines.append("## Rig")
    lines.append("")
    lines.append(
        "No multiplexer. A single capacitor is wired across Drive+/Drive- with "
        "Sense+ strapped to Drive+ and Sense- to Drive-. The AD5933 runs at "
        f"{capture.get('range', '1vpp')} and the same 0.1 uF-class fixture used "
        "for calibration."
    )
    lines.append("")
    lines.append(
        f"Nominal capacitance: {capacitance_f * 1e6:.3f} uF. "
        f"{analysis[0]['count']} repeated readings are taken at the same "
        f"physical location at each of {len(analysis)} frequencies "
        f"({analysis[0]['f']:g}-{analysis[-1]['f']:g} Hz) and treated as the "
        "40 boundary values of a pseudo-frame."
    )
    lines.append("")
    lines.append("## Procedure")
    lines.append("")
    lines.append(
        "1. Power the front end from an isolated/battery supply and keep the "
        "injected current below 1 mA peak."
    )
    lines.append(
        "2. Connect the capacitor between Drive+ and Drive- and strap the sense "
        "leads to the same nodes."
    )
    lines.append(
        "3. Upload the separate imperr bench firmware and identify the board."
    )
    lines.append(
        "4. Sweep the requested frequency range, acquiring individual samples at "
        "each frequency and discarding one warm-up conversion."
    )
    lines.append(
        "5. Compare measured magnitude and phase with the ideal capacitor and "
        "project the deviations through the pyEIT solver."
    )
    lines.append("")
    hello = capture.get("firmware") or {}
    sources: set[str] = set()
    for factor in (hello.get("calibration") or {}).get("factors") or []:
        sources.update(factor.get("sources") or [])
    if sources == {"capacitor"}:
        reference_text = (
            "The device calibration file is capacitor-only and was produced with "
            "a 0.1 uF fixture. Absolute accuracy is therefore not independently "
            "traceable: the same nominal capacitor supplies the reference. "
        )
    elif "resistor" in sources and "capacitor" in sources:
        reference_text = (
            "The device calibration combines a resistor magnitude reference and "
            "a capacitor phase reference. Absolute accuracy still depends on the "
            "tolerance of those two components. "
        )
    else:
        reference_text = (
            "The device calibration entries are not independently traceable. "
        )
    modes = sorted({item["calibration_mode"] for item in analysis})
    references = sorted(
        {
            item["reference_frequency_hz"]
            for item in analysis
            if item["reference_frequency_hz"] is not None
        }
    )
    device_factors = _device_factors(hello)
    lines.append("## Calibration")
    lines.append("")
    lines.append(reference_text)
    if "interpolate" in modes:
        factor_label = ", ".join(f"{value:g} Hz" for value, _ in device_factors)
        lines.append(
            "A frequency-dependent device calibration is interpolated in log "
            f"magnitude and phase between the calibration points ({factor_label}) "
            "and extrapolated outside that range. This compensates the measured "
            "front-end transfer so the curve shows the fixture response; the "
            "extrapolated ends are less certain."
        )
        response_note = (
            "The measured magnitude and phase are compensated with the "
            "interpolated front-end transfer. Deviations from the ideal "
            "1/(2 pi f C) and -90 degree lines are residual calibration and "
            "fixture error. The shaded regions in the graph mark the "
            "extrapolated ends outside the calibrated band."
        )
    elif modes == ["device"]:
        reference_label = ", ".join(f"{value:g} Hz" for value in references)
        lines.append(
            f"A single device calibration factor measured at {reference_label} "
            "is applied to the whole sweep. The measured curve therefore includes "
            "the front-end frequency response relative to that reference."
        )
        response_note = (
            "The measured magnitude and phase show the system response relative "
            "to the reference calibration. Deviations from the ideal "
            "1/(2 pi f C) and -90 degree lines are the front-end/fixture "
            "frequency response."
        )
    elif modes == ["reference"] and len(references) == 1:
        reference_label = f"{references[0]:g} Hz"
        lines.append(
            f"A single ideal reference at {reference_label} is applied to the "
            "whole sweep, so the curve shows the response relative to that "
            "reference."
        )
        response_note = (
            "The measured magnitude and phase show the response relative to the "
            "single ideal reference. Deviations from the ideal curves are the "
            "front-end/fixture frequency response."
        )
    else:
        lines.append(
            "Every frequency is self-referenced to the first half of its own "
            "samples. This removes the mean offset and preserves point-to-point "
            "drift, but the frequency-response curve is ideal by construction; "
            "use this mode only for repeatability."
        )
        response_note = (
            "Because each frequency is self-referenced, the magnitude curve is "
            "ideal by construction. The sigma and error-vs-frequency plots carry "
            "the repeatability information."
        )
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("### Frequency response")
    lines.append("")
    lines.append(response_note)
    lines.append("")
    lines.append("![frequency response](frequency-response.png)")
    lines.append("")
    lines.append("### Per-frequency error")
    lines.append("")
    lines.append(
        "| f (Hz) | ideal |Z| (ohm) | mean |Z| (ohm) | mean error (ohm) | "
        "mean error (%) | phase error (deg) | sigma (ohm) | drift (ohm/point) |"
    )
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for item in analysis:
        lines.append(
            f"| {item['f']:g} | {_fmt(item['ideal']['mag'])} | "
            f"{_fmt(item['mean_mag'])} | {_fmt(item['mean_error_ohm'])} | "
            f"{_fmt(item['mean_error_pct'], 2)} | "
            f"{_fmt(item['mean_phase_error_deg'], 2)} | "
            f"{_fmt(item['std_error_ohm'])} | "
            f"{_fmt(item['drift_slope_ohm_per_point'], 4)} |"
        )
    lines.append("")
    lines.append(
        "The mean error includes any systematic offset (capacitor tolerance and "
        "calibration); sigma and drift isolate the repeatability of the system. "
        "The half-to-half drift is:"
    )
    lines.append("")
    lines.append("| f (Hz) | first-half mean (ohm) | second-half mean (ohm) | drift (ohm) |")
    lines.append("|---:|---:|---:|---:|")
    for item in analysis:
        lines.append(
            f"| {item['f']:g} | {_fmt(item['first_half_mean_error_ohm'])} | "
            f"{_fmt(item['second_half_mean_error_ohm'])} | "
            f"{_fmt(item['half_drift_ohm'])} |"
        )
    lines.append("")
    lines.append("### Intended vs real")
    lines.append("")
    for item in analysis:
        if item["f"] not in detail_frequencies:
            continue
        lines.append(
            f"![magnitude {item['f']:g} Hz]"
            f"(magnitude-vs-point-{int(item['f'])}.png)"
        )
        lines.append("")
        lines.append(
            f"![histogram {item['f']:g} Hz]"
            f"(error-histogram-{int(item['f'])}.png)"
        )
        lines.append("")
    lines.append("![error vs frequency](error-vs-frequency.png)")
    lines.append("")
    lines.append("## Conductivity-map projection")
    lines.append("")
    lines.append(
        "The ideal baseline is a constant |Z|. The measured frame is the measured "
        "|Z| values in the standard boundary order. Because the true field is "
        "homogeneous, any non-zero reconstruction is the map error caused by the "
        "impedance error. Values are arbitrary units (pyEIT BP, normalised per "
        "frame), so only relative magnitudes are meaningful."
    )
    lines.append("")
    lines.append("![map error vs frequency](map-error-vs-frequency.png)")
    lines.append("")
    lines.append(
        "| f (Hz) | map peak | map RMS | centred peak | centred RMS | "
        "anomaly score | area >= 50% peak | bootstrap RMS p50 |"
    )
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for item, projection in zip(analysis, projections, strict=True):
        if item["f"] not in detail_frequencies:
            continue
        lines.append(
            f"| {item['f']:g} | {_fmt(projection['nominal']['peak'], 6)} | "
            f"{_fmt(projection['nominal']['rms'], 6)} | "
            f"{_fmt(projection['centered']['peak'], 6)} | "
            f"{_fmt(projection['centered']['rms'], 6)} | "
            f"{_fmt(projection['nominal']['anomaly_score'], 6)} | "
            f"{_fmt(100.0 * projection['nominal']['area_fraction_at_half_peak'], 2)}% | "
            f"{_fmt(projection['bootstrap']['rms_p50'], 6)} |"
        )
    lines.append("")
    lines.append(
        "The un-centred map includes the systematic offset and is the error the "
        "device would show if the current fixture differed from its reference by "
        "that mean amount. The centred map removes the mean offset and isolates "
        "the effect of repeatability alone. Full map metrics for every frequency "
        "are in `summary.json`; the table above shows the selected detail "
        "frequencies."
    )
    lines.append("")
    for item in analysis:
        if item["f"] not in detail_frequencies:
            continue
        lines.append(
            f"![map {item['f']:g} Hz]"
            f"(map-measured-{int(item['f'])}-figure.png)"
        )
        lines.append("")
    lines.append("## Sources of error")
    lines.append("")
    lines.append(
        "- Capacitor tolerance and calibration provenance dominate the "
        "systematic offset."
    )
    lines.append(
        "- Point-to-point spread reflects AD5933 quantisation, warm-up, supply "
        "and thermal drift, and fixture contact repeatability."
    )
    lines.append("")
    lines.append("## Limitations and next steps")
    lines.append("")
    lines.append(
        "- The device calibration band is 10-50 kHz. The 1-10 kHz and "
        "50-100 kHz ends are extrapolated; the low-frequency end is not "
        "reliable and needs an additional calibration point."
    )
    lines.append(
        "- Only one capacitor is connected. The four-capacitor series/parallel "
        "matrix is the next step and will separate capacitor tolerance from "
        "front-end error."
    )
    lines.append(
        "- The pseudo-frame assigns the same-location error to the 40 standard "
        "boundary channels; it is a sensitivity projection, not a phantom scan."
    )
    lines.append(
        "- A full-ring mux scan and an independent impedance analyser are still "
        "required for absolute physical validation."
    )
    lines.append("")
    (out_dir / REPORT_FILE).write_text("\n".join(lines))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _add_measure_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--port", help="serial port (default: auto-detect ESP32)")
    parser.add_argument(
        "--freqs",
        default=None,
        help="explicit comma-separated frequencies; overrides the sweep",
    )
    parser.add_argument("--sweep-start", type=float, default=DEFAULT_SWEEP_START,
                        help="log sweep start frequency (default: 1000 Hz)")
    parser.add_argument("--sweep-stop", type=float, default=DEFAULT_SWEEP_STOP,
                        help="log sweep stop frequency (default: 100000 Hz)")
    parser.add_argument("--sweep-points", type=int, default=DEFAULT_SWEEP_POINTS,
                        help="number of log-spaced sweep points (default: 50)")
    parser.add_argument("--c-f", type=float, default=DEFAULT_C_F,
                        help="nominal fixture capacitance (F)")
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES,
                        help="points per frequency (default: 40)")
    parser.add_argument("--range", dest="range_name", default=DEFAULT_RANGE,
                        choices=("2vpp", "1vpp", "400mv", "200mv"))
    parser.add_argument("--discard", type=int, default=DEFAULT_DISCARD,
                        help="warm-up conversions to discard (default: 1)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--calibration",
                        choices=("auto", "interpolate", "device", "ideal"),
                        default="auto",
                        help="calibration source for converting raw codes to ohms")


def _add_project_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--grid-size", type=int, default=DEFAULT_GRID)
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS,
                        help="bootstrap trials per frequency")
    parser.add_argument("--detail-count", type=int, default=DEFAULT_DETAIL_COUNT,
                        help="number of frequencies detailed with per-point and map plots")
    parser.add_argument("--reference-frequency", type=float, default=None,
                        help="device calibration frequency used as the sweep reference")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)


def _run_project(
    capture: dict,
    capacitance_f: float,
    calibration_mode: str,
    reference_frequency: float | None,
    grid_size: int,
    trials: int,
    detail_count: int,
    seed: int,
    out_dir: Path,
) -> tuple[list[dict], list[dict]]:
    calibration_factors, resolved_mode, used_reference = _prepare_calibration(
        capture, capacitance_f, calibration_mode, reference_frequency
    )
    analysis = [
        analyze_measurement(
            item, capacitance_f, calibration_factors, resolved_mode, used_reference
        )
        for item in capture.get("measurements", [])
    ]
    indices = _detail_indices(len(analysis), detail_count)
    detail_frequencies = {analysis[index]["f"] for index in indices}
    projections = project_maps(
        analysis, grid_size, trials, seed, detail_frequencies, out_dir
    )
    summary = {
        "captured_at": capture.get("captured_at"),
        "capacitance_f": capacitance_f,
        "requested_calibration_mode": calibration_mode,
        "resolved_calibration_mode": resolved_mode,
        "reference_frequency_hz": used_reference,
        "seed": seed,
        "detail_frequencies": sorted(detail_frequencies),
        "analysis": analysis,
        "projections": projections,
    }
    (out_dir / SUMMARY_FILE).write_text(json.dumps(_jsonable(summary), indent=2))
    _write_csv(analysis, out_dir)
    _plot_results(
        analysis, detail_frequencies,
        [value for value, _ in _device_factors(capture.get("firmware") or {})],
        out_dir,
    )
    _plot_map_error(projections, out_dir)
    write_report(
        capture, analysis, projections, capacitance_f, detail_frequencies, out_dir
    )
    return analysis, projections


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools/impedance_error.py",
        description=(
            "Measure live capacitor impedance error and project it onto a "
            "conductivity-map error using the pyEIT solver."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    upload_parser = sub.add_parser("upload", help="upload the imperr bench firmware")
    upload_parser.add_argument("--port", help="serial port")
    upload_parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)

    measure_parser = sub.add_parser("measure", help="acquire 40-point captures")
    _add_measure_args(measure_parser)
    measure_parser.add_argument("--out", default=str(DEFAULT_OUT), help="output directory")
    measure_parser.add_argument("--upload", action="store_true",
                                help="upload the imperr firmware first")

    project_parser = sub.add_parser("project", help="analyse a saved capture")
    project_parser.add_argument("--data", help="capture JSON (default: out/capture.json)")
    project_parser.add_argument("--c-f", type=float, default=None)
    project_parser.add_argument("--calibration",
                                choices=("auto", "interpolate", "device", "ideal"),
                                default="auto")
    _add_project_args(project_parser)
    project_parser.add_argument("--out", default=str(DEFAULT_OUT), help="output directory")

    run_parser = sub.add_parser("run", help="upload, measure, project and report")
    _add_measure_args(run_parser)
    _add_project_args(run_parser)
    run_parser.add_argument("--out", default=str(DEFAULT_OUT), help="output directory")
    run_parser.add_argument("--no-upload", action="store_true",
                            help="do not re-upload the imperr firmware")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_dir = Path(args.out)

    try:
        if args.command == "upload":
            port = hwtest.find_port(args.port)
            upload_firmware(port, args.timeout)
            print(f"uploaded imperr firmware to {port}")
            print("restore production firmware later with: python dev.py upload-firmware")
            return 0

        if args.command == "measure":
            if args.upload:
                port = hwtest.find_port(args.port)
                upload_firmware(port, args.timeout)
                print(f"uploaded imperr firmware to {port}")
                time.sleep(2.0)
            freqs = _frequency_list(args)
            print("capturing imperr points:")
            measure_frequencies(
                args.port, freqs, args.samples, args.range_name,
                args.discard, args.timeout, args.c_f, out_dir,
            )
            return 0

        if args.command == "project":
            data_path = Path(args.data) if args.data else out_dir / CAPTURE_FILE
            if not data_path.is_file():
                raise ImpedanceErrorToolError(
                    f"capture file not found: {data_path}; run measure first"
                )
            capture = json.loads(data_path.read_text())
            capacitance_f = (
                args.c_f
                if args.c_f is not None
                else float(capture.get("c_f", DEFAULT_C_F))
            )
            out_dir.mkdir(parents=True, exist_ok=True)
            analysis, _ = _run_project(
                capture, capacitance_f, args.calibration,
                args.reference_frequency, args.grid_size, args.trials,
                args.detail_count, args.seed, out_dir,
            )
            print(f"wrote {out_dir / REPORT_FILE}")
            print(f"wrote {out_dir / SUMMARY_FILE}")
            print(f"wrote {out_dir / CSV_FILE}")
            for item in analysis:
                print(
                    f"  {item['f']:>9.0f} Hz  mean {item['mean_error_ohm']:+.3f} ohm  "
                    f"sigma {item['std_error_ohm']:.3f} ohm  "
                    f"({item['calibration_mode']})"
                )
            return 0

        if args.command == "run":
            if not args.no_upload:
                port = hwtest.find_port(args.port)
                upload_firmware(port, args.timeout)
                print(f"uploaded imperr firmware to {port}")
                args.port = port
                time.sleep(2.0)
            freqs = _frequency_list(args)
            print("capturing imperr points:")
            capture = measure_frequencies(
                args.port, freqs, args.samples, args.range_name,
                args.discard, args.timeout, args.c_f, out_dir,
            )
            analysis, _ = _run_project(
                capture, args.c_f, args.calibration, args.reference_frequency,
                args.grid_size, args.trials, args.detail_count, args.seed, out_dir,
            )
            print(f"wrote {out_dir / REPORT_FILE}")
            print(f"wrote {out_dir / SUMMARY_FILE}")
            print(f"wrote {out_dir / CSV_FILE}")
            for item in analysis:
                print(
                    f"  {item['f']:>9.0f} Hz  mean {item['mean_error_ohm']:+.3f} ohm  "
                    f"sigma {item['std_error_ohm']:.3f} ohm  "
                    f"({item['calibration_mode']})"
                )
            return 0

        raise ImpedanceErrorToolError(f"unknown command: {args.command}")
    except (ImpedanceErrorToolError, OSError) as exc:
        print(f"impedance_error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
