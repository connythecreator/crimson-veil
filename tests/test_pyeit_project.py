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

import matplotlib.pyplot as plt
import numpy as np
import pyeit.eit.bp as bp
import pyeit.eit.protocol as protocol
import pyeit.mesh as mesh
from pyeit.eit.fem import EITForward
from pyeit.mesh.wrapper import PyEITAnomaly_Circle

from software.core.types import MeshConfig
from software.reconstruction.pyeit_solver import PyEITSolver


FREQ_HZ = 50_000.0
N_ELECTRODES = 8
GRID_SIZE = 96


ANOMALY_POSITIONS = {
    "upper_right": [0.5, 0.5],
    "upper_left": [-0.5, 0.5],
    "lower_left": [-0.5, -0.5],
    "lower_right": [0.5, -0.5],
}


def test_pyeit_with_project_protocol():
    """Test pyEIT's standard adjacent protocol with quadrant anomalies."""

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
    # Use pyEIT's 40-measurement standard protocol for localization testing;
    # the production project protocol currently contains only 8 measurements.
    protocol_obj = protocol.create(
        N_ELECTRODES,
        dist_exc=1,
        step_meas=1,
        parser_meas="std",
    )

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

    eit = bp.BP(
        mesh_obj,
        protocol_obj,
    )
    eit.setup(
        weight="none",
    )

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

        ds = eit.solve(
            v1,
            v0,
            normalize=True,
        )
        ds = np.real(ds)
        conductivity_map = solver._to_conductivity_map(ds)

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

        output_path = (
            output_dir
            / f"{position_name}.png"
        )

        # Keep PNG row zero at the top to match the reconstructed map grid.
        plt.imsave(
            output_path,
            values,
            origin="upper",
        )

        print(
            "Saved image:",
            output_path,
        )

    solver.close()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))