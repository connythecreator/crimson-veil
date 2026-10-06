"""Diagnostic test for pyEIT's 40-measurement adjacent protocol.

This test verifies that:

1. pyEIT generates 40 simulated baseline/anomaly measurements.
2. Back projection localizes anomalies in four different quadrants.
"""

import pyeit.eit.bp as bp
import pyeit.eit.protocol as protocol
import matplotlib.pyplot as plt
import numpy as np
import pyeit.mesh as mesh

from pyeit.eit.fem import EITForward
from pyeit.mesh.wrapper import PyEITAnomaly_Circle
from pathlib import Path
from software.core.types import MeshConfig
from software.reconstruction.pyeit_solver import PyEITSolver


# ============================================================
# TEST SETTINGS
# ============================================================

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

    # ========================================================
    # 1. CREATE THE pyEIT SOLVER
    # ========================================================

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
    protocol_obj = protocol.create(
        N_ELECTRODES,
        dist_exc=1,
        step_meas=1,
        parser_meas="std",
    )

    assert mesh_obj is not None
    assert protocol_obj is not None


    # ========================================================
    # 2. CHECK THE STANDARD PROTOCOL
    # ========================================================

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

    # ========================================================
    # 3. CREATE FORWARD MODEL
    # ========================================================

    forward = EITForward(
        mesh_obj,
        protocol_obj,
    )


    # ========================================================
    # 4. CREATE HOMOGENEOUS BASELINE
    # ========================================================

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

    # ========================================================
    # 5. CREATE OUTPUT DIRECTORY
    # ========================================================

    output_dir = (
        Path(__file__).resolve().parent
        / "pyeit_outputs"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )


    # ========================================================
    # 6. TEST EACH ANOMALY POSITION
    # ========================================================

    for position_name, center in ANOMALY_POSITIONS.items():

        print(
            f"\n--- Testing {position_name} "
            f"at {center} ---"
        )


        # ----------------------------------------------------
        # 8A. CREATE SIMULATED ANOMALY
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # 8B. FORWARD SIMULATION
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # 8C. BACK PROJECT USING THE 40-VALUE PROTOCOL
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # 8D. CHECK RECONSTRUCTION
        # ----------------------------------------------------

        assert conductivity_map.width == GRID_SIZE
        assert conductivity_map.height == GRID_SIZE

        assert np.all(
            np.isfinite(values)
        )

        assert np.max(values) != np.min(values)

        # The solver convention is:
        #
        # increased conductivity
        #       ->
        # positive reconstructed value
        peak_absolute_change = np.max(
            np.abs(values)
        )

        assert peak_absolute_change > 1e-12


        # ----------------------------------------------------
        # 8E. FIND STRONGEST RECONSTRUCTED LOCATION
        # ----------------------------------------------------

        peak_row, peak_col = np.unravel_index(
            np.argmax(np.abs(values)),
            values.shape,
        )
        assert values[peak_row, peak_col] > 0

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


        # ----------------------------------------------------
        # 8F. PRINT RESULT
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # 8G. SAVE RECONSTRUCTED IMAGE
        # ----------------------------------------------------

        output_path = (
            output_dir
            / f"{position_name}.png"
        )

        plt.imsave(
            output_path,
            values,
            origin="upper",
        )

        print(
            "Saved image:",
            output_path,
        )


    # ========================================================
    # 9. CLEAN UP
    # ========================================================

    solver.close()