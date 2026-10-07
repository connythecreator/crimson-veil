r"""Diagnostic test for pyEIT's 40-measurement adjacent protocol.

This test verifies that:

1. pyEIT generates 40 simulated baseline/anomaly measurements.
2. Back projection localizes anomalies in four different quadrants.

Test using: .\.venv\Scripts\python.exe -m pytest -s tests\test_pyeit_project.py
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

# pyEIT, numpy and matplotlib are installed manually (see
# software/reconstruction/PYEIT_SOLVER.md); skip cleanly when they are absent.
pytest.importorskip("pyeit")
pytest.importorskip("matplotlib")
pytest.importorskip("numpy")

import numpy as np
import pyeit.mesh as mesh
from pyeit.eit.fem import EITForward
from pyeit.mesh.wrapper import PyEITAnomaly_Circle

from software import pipeline
from software.core import config
from software.core.types import MeshConfig, RawPoint, ScanData
from software.reconstruction.image import conductivity_to_png
from software.reconstruction.pyeit_solver import PyEITSolver


FREQ_HZ = 50_000.0
N_ELECTRODES = 8
GRID_SIZE = 96


# +ve x moves right, -ve x moves left
# +ve y moves up, -ve y moves down
ANOMALY_POSITIONS = {
    "upper_right": [0.5, 0.5],
    "upper_left": [-0.5, 0.5],
    "lower_left": [-0.5, -0.5],
    "lower_right": [0.5, -0.5],
}


def _scan_data(
    protocol_obj,
    values: np.ndarray,
    label: str,
    frequency_hz: float,
) -> ScanData:
    """Convert pyEIT-ordered values into the firmware's frame order."""
    n_electrodes = N_ELECTRODES
    firmware_pairs = [
        (
            (electrode, (electrode + 1) % n_electrodes),
            (
                (electrode + 2 + offset) % n_electrodes,
                (electrode + 3 + offset) % n_electrodes,
            ),
        )
        for electrode in range(n_electrodes)
        for offset in range(n_electrodes - 3)
    ]
    firmware_indices = {
        measurement: index for index, measurement in enumerate(firmware_pairs)
    }
    firmware_values = np.empty(len(firmware_pairs), dtype=float)

    protocol_index = 0
    for drive_index, drive in enumerate(protocol_obj.ex_mat):
        drive_pair = tuple(int(value) for value in drive)
        for sense in protocol_obj.meas_mat[drive_index]:
            sense_pair = tuple(int(value) for value in sense)
            firmware_index = firmware_indices.get((drive_pair, sense_pair))
            polarity = 1.0
            if firmware_index is None:
                firmware_index = firmware_indices[
                    (drive_pair, (sense_pair[1], sense_pair[0]))
                ]
                polarity = -1.0
            firmware_values[firmware_index] = values[protocol_index] * polarity
            protocol_index += 1

    assert protocol_index == len(values)
    return ScanData(
        points=[
            RawPoint(
                freq_hz=frequency_hz,
                real=float(np.real(value)),
                imag=float(np.imag(value)),
            )
            for value in firmware_values
        ],
        label=label,
        n_electrodes=n_electrodes,
        frequency_hz=frequency_hz,
    )


class _DigitalHardware:
    n_electrodes = N_ELECTRODES

    def __init__(
        self,
        points: list[RawPoint],
        frequency_hz: float,
    ) -> None:
        self._points = points
        self.frequency_hz = frequency_hz

    def open(self, _cfg) -> None:
        pass

    def identify(self) -> str:
        return "digital:test"

    def scan(self) -> list[RawPoint]:
        return self._points

    def close(self) -> None:
        pass


def test_default_solver_selects_pyeit(monkeypatch):
    monkeypatch.setattr(config, "SOLVER_BACKEND", "pyeit")
    solver = pipeline.default_solver()
    assert isinstance(solver, PyEITSolver)
    assert solver.frequency_hz == config.DEFAULT_FREQUENCY_HZ
    solver.close()


def test_pyeit_with_project_protocol():
    """Test digital baseline-to-anomaly reconstruction through the pipeline."""

    solver = PyEITSolver(
        grid_size=GRID_SIZE,
        frequency_hz=FREQ_HZ,
    )

    solver.setup(
        N_ELECTRODES,
        MeshConfig(
            n_electrodes=N_ELECTRODES,
            shape="circle",
        ),
    )

    mesh_obj = solver.mesh_obj
    protocol_obj = solver.protocol_obj

    assert mesh_obj is not None
    assert protocol_obj is not None

    print("\n--- Crimson Veil pyEIT Protocol ---")

    print("\nExcitation matrix:")
    print(protocol_obj.ex_mat)

    print("\nMeasurement pairs by drive:")
    for exc_index in range(len(protocol_obj.ex_mat)):
        print(
            f"\nDrive {protocol_obj.ex_mat[exc_index]}:"
        )
        print(protocol_obj.meas_mat[exc_index])

    print(
        "\nProtocol measurement count:",
        protocol_obj.n_meas_tot,
    )

    assert protocol_obj.n_meas_tot == 40

    forward = EITForward(
        mesh_obj,
        protocol_obj,
    )

    v0 = forward.solve_eit()

    print("\n--- Baseline ---")

    print(
        "Reference measurements:",
        len(v0),
    )

    assert len(v0) == 40
    assert len(v0) == protocol_obj.n_meas_tot

    output_dir = (
        Path(__file__).resolve().parent
        / "pyeit_outputs"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for position_name, center in ANOMALY_POSITIONS.items():

        print(
            f"\n--- Testing {position_name} "
            f"at {center} ---"
        )

        # Determines the anomaly's location in the mesh's coordinate system.
        anomaly = PyEITAnomaly_Circle(
            center=center,
            r=0.15,
            perm=10.0,
        )

        mesh_anomaly = mesh.set_perm(
            mesh_obj,
            anomaly=anomaly,
            background=1.0,
        )

        v1 = forward.solve_eit(
            perm=mesh_anomaly.perm
        )

        print(
            "Anomaly measurements:",
            len(v1),
        )

        assert len(v1) == 40

        # Check that the anomaly actually changed
        # the simulated measurements.
        measurement_change = np.max(
            np.abs(v1 - v0)
        )

        print(
            "Maximum measurement change:",
            measurement_change,
        )

        assert measurement_change > 1e-12

        baseline = _scan_data(
            protocol_obj,
            v0,
            "digital baseline",
            FREQ_HZ,
        )
        frame = _scan_data(
            protocol_obj,
            v1,
            f"digital {position_name}",
            FREQ_HZ,
        )
        conductivity_map = solver.reconstruct(
            frame,
            baseline,
        )

        values = np.asarray(
            conductivity_map.values,
            dtype=float,
        )

        assert conductivity_map.width == GRID_SIZE
        assert conductivity_map.height == GRID_SIZE

        assert np.all(
            np.isfinite(values)
        )

        assert np.max(values) != np.min(values)

        # Positive reconstructed values indicate increased conductivity.
        peak_absolute_change = np.max(
            np.abs(values)
        )

        assert peak_absolute_change > 1e-12

        peak_row, peak_col = np.unravel_index(
            np.argmax(np.abs(values)),
            values.shape,
        )
        assert values[peak_row, peak_col] > 0

        # Image rows run from top to bottom, so the grid midpoint separates
        # upper/lower and left/right quadrants in pixel coordinates.
        middle_row = values.shape[0] / 2
        middle_col = values.shape[1] / 2

        if peak_row < middle_row:
            vertical_position = "upper"
        else:
            vertical_position = "lower"

        if peak_col < middle_col:
            horizontal_position = "left"
        else:
            horizontal_position = "right"

        reconstructed_position = (
            f"{vertical_position}_"
            f"{horizontal_position}"
        )

        assert reconstructed_position == position_name, (
            f"Expected anomaly in {position_name}, "
            f"but reconstruction peak was in {reconstructed_position}"
        )

        if position_name == "upper_right":
            homogeneous_baseline_map = solver.reconstruct(frame)
            assert homogeneous_baseline_map.width == GRID_SIZE
            assert homogeneous_baseline_map.height == GRID_SIZE
            assert np.all(np.isfinite(homogeneous_baseline_map.values))
            assert np.max(np.abs(homogeneous_baseline_map.values)) > 1e-12

        print(
            "Expected position:",
            position_name,
        )

        print(
            "Peak pixel:",
            f"row={peak_row}, col={peak_col}",
        )

        print(
            "Detected quadrant:",
            reconstructed_position,
        )

        print(
            "Minimum conductivity change:",
            np.min(values),
        )

        print(
            "Maximum conductivity change:",
            np.max(values),
        )

        hardware = _DigitalHardware(frame.points, FREQ_HZ)
        png = pipeline.run_scan(
            hardware=hardware,
            solver=solver,
            baseline=baseline,
        )
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        assert png == conductivity_to_png(conductivity_map)

        output_path = (
            output_dir
            / f"{position_name}.png"
        )
        output_path.write_bytes(png)

        print(
            "Saved image:",
            output_path,
        )

    solver.close()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))