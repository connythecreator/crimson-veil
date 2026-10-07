"""pyEIT reconstruction backend for Crimson Veil.

The reconstruction protocol follows pyEIT's standard adjacent-drive,
adjacent-measurement ordering for a circular electrode array. For the current
8-electrode system this yields 8 drive pairs and 5 valid adjacent voltage
measurements per drive, giving 40 measurements per frequency. Voltage
measurements involving either current-injection electrode are excluded.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.types import ConductivityMap, MeshConfig, ScanData

if TYPE_CHECKING:
    import numpy as np
    from pyeit.eit.fem import EITForward
    from pyeit.eit.protocol import PyEITProtocol


DEFAULT_RECONSTRUCTION_FREQUENCY_HZ = 50_000.0


def _build_project_protocol(
    n_electrodes: int,
) -> tuple[PyEITProtocol, list[tuple[int, float]]]:
    """Map the firmware's ordered measurements to pyEIT's protocol."""
    import pyeit.eit.protocol as protocol

    if n_electrodes < 4:
        raise ValueError("n_electrodes must be at least 4 for tetrapolar EIT.")

    protocol_obj = protocol.create(
        n_electrodes,
        dist_exc=1,
        step_meas=1,
        parser_meas="std",
    )

    if len(protocol_obj.ex_mat) != n_electrodes:
        raise RuntimeError(
            f"Expected {n_electrodes} excitation pairs, got {len(protocol_obj.ex_mat)}."
        )

    expected_count = n_electrodes * (n_electrodes - 3)
    if protocol_obj.n_meas_tot != expected_count:
        raise RuntimeError(
            f"Expected {expected_count} measurements for the "
            f"{n_electrodes}-electrode protocol, "
            f"got {protocol_obj.n_meas_tot}."
        )

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
    protocol_mapping: list[tuple[int, float]] = []

    for exc_index, drive_pair in enumerate(protocol_obj.ex_mat):
        for sense_pair in protocol_obj.meas_mat[exc_index]:
            pyeit_drive = tuple(int(value) for value in drive_pair)
            pyeit_sense = tuple(int(value) for value in sense_pair)

            firmware_index = firmware_indices.get((pyeit_drive, pyeit_sense))
            polarity = 1.0
            if firmware_index is None:
                firmware_index = firmware_indices.get(
                    (pyeit_drive, (pyeit_sense[1], pyeit_sense[0]))
                )
                polarity = -1.0

            if firmware_index is None:
                raise RuntimeError(
                    "Firmware scan sequence does not match pyEIT: "
                    f"no firmware measurement corresponds to drive="
                    f"{pyeit_drive}, sense={pyeit_sense}."
                )
            protocol_mapping.append((firmware_index, polarity))

    if len({index for index, _ in protocol_mapping}) != len(firmware_pairs):
        raise RuntimeError(
            "pyEIT protocol does not map one-to-one to the firmware scan sequence."
        )

    return protocol_obj, protocol_mapping


class PyEITSolver:
    """Difference-EIT reconstruction using pyEIT Back Projection."""

    def __init__(
        self,
        grid_size: int = 96,
        frequency_hz: float = DEFAULT_RECONSTRUCTION_FREQUENCY_HZ,
    ) -> None:
        self.grid_size = grid_size
        self.frequency_hz = float(frequency_hz)

        self.mesh_obj = None
        self.protocol_obj: PyEITProtocol | None = None
        self.eit = None
        self.forward: EITForward | None = None

        self.n_electrodes: int | None = None
        self._protocol_mapping: list[tuple[int, float]] = []

    def setup(
        self,
        n_electrodes: int,
        mesh: MeshConfig,
    ) -> None:
        """Create the FEM mesh, project-matched protocol and BP solver."""

        if mesh.shape != "circle":
            raise ValueError(
                f"PyEITSolver currently supports only a circular mesh, "
                f"got {mesh.shape!r}."
            )
        if mesh.n_electrodes != n_electrodes:
            raise ValueError(
                f"MeshConfig has {mesh.n_electrodes} electrodes but setup "
                f"received {n_electrodes}."
            )

        self.n_electrodes = int(n_electrodes)

        import pyeit.eit.bp as bp
        import pyeit.mesh as pyeit_mesh
        from pyeit.eit.fem import EITForward

        self.mesh_obj = pyeit_mesh.create(
            self.n_electrodes,
            h0=0.1,
        )

        self.protocol_obj, self._protocol_mapping = _build_project_protocol(
            self.n_electrodes
        )
        self.forward = EITForward(self.mesh_obj, self.protocol_obj)

        self.eit = bp.BP(
            self.mesh_obj,
            self.protocol_obj,
        )

        self.eit.setup(
            weight="none",
        )

    def reconstruct(
        self,
        frame: ScanData,
        baseline: ScanData | None = None,
    ) -> ConductivityMap:
        """Reconstruct ``frame`` relative to ``baseline``.

        Each frame contains one frequency. Firmware measurements are reordered
        into pyEIT order, including correcting reversed sense-pair polarity.
        Without a captured baseline, use pyEIT's homogeneous forward solution.
        """

        if self.eit is None or self.protocol_obj is None or self.forward is None:
            raise RuntimeError(
                "PyEITSolver.setup() must be called before reconstruct()."
            )
        import numpy as np

        v1, frame_frequency = self._values_for_scan(
            frame,
            scan_name="frame",
        )
        self.frequency_hz = frame_frequency

        if baseline is None:
            v0 = np.asarray(self.forward.solve_eit(), dtype=float)
        else:
            v0, baseline_frequency = self._values_for_scan(
                baseline,
                scan_name="baseline",
            )
            if not np.isclose(
                frame_frequency,
                baseline_frequency,
                rtol=0.0,
                atol=1e-6,
            ):
                raise ValueError(
                    "Frame and baseline frequencies do not match: "
                    f"{frame_frequency:g} Hz vs {baseline_frequency:g} Hz."
                )

        if len(v1) != len(v0):
            raise ValueError(
                "Frame and baseline do not contain the same number of "
                f"{frame_frequency:g} Hz measurements."
            )

        expected_count = self.protocol_obj.n_meas_tot

        if len(v1) != expected_count:
            raise ValueError(
                "Measurement count mismatch: "
                f"received {len(v1)} measurements at "
                f"{frame_frequency:g} Hz, but the project-matched pyEIT "
                f"protocol expects {expected_count}."
            )

        ds = self.eit.solve(
            v1,
            v0,
            normalize=True,
        )
        ds = np.real(ds)

        return self._to_conductivity_map(ds)

    def _values_for_scan(
        self,
        scan: ScanData,
        scan_name: str,
    ) -> tuple[np.ndarray, float]:
        """Validate a single-frequency frame and convert it to pyEIT order."""

        if self.protocol_obj is None or self.n_electrodes is None:
            raise RuntimeError(
                "PyEITSolver.setup() must be called before reading measurements."
            )
        import numpy as np

        if scan.n_electrodes and scan.n_electrodes != self.n_electrodes:
            raise ValueError(
                f"{scan_name} has {scan.n_electrodes} electrodes; expected "
                f"{self.n_electrodes}."
            )

        expected_count = self.protocol_obj.n_meas_tot
        if len(scan.points) != expected_count:
            raise ValueError(
                f"{scan_name} contains {len(scan.points)} measurements; "
                f"expected {expected_count}."
            )

        scan_frequency = scan.frequency_hz
        if not np.isfinite(scan_frequency) or scan_frequency <= 0:
            scan_frequency = scan.points[0].freq_hz
        if not np.isfinite(scan_frequency) or scan_frequency <= 0:
            raise ValueError(
                f"{scan_name} does not report a positive scan frequency."
            )

        for index, point in enumerate(scan.points):
            if not np.isclose(
                point.freq_hz,
                scan_frequency,
                rtol=0.0,
                atol=1e-6,
            ):
                raise ValueError(
                    f"{scan_name} point {index} frequency {point.freq_hz:g} Hz "
                    f"does not match scan frequency {scan_frequency:g} Hz."
                )

        firmware_values = np.asarray(
            [point.real for point in scan.points],
            dtype=float,
        )
        protocol_values = np.empty(expected_count, dtype=float)
        for protocol_index, (firmware_index, polarity) in enumerate(
            self._protocol_mapping
        ):
            protocol_values[protocol_index] = (
                firmware_values[firmware_index] * polarity
            )

        return protocol_values, float(scan_frequency)

    def _to_conductivity_map(
        self,
        ds: np.ndarray,
    ) -> ConductivityMap:
        """Interpolate the FEM result onto a rectangular image grid."""

        if self.mesh_obj is None:
            raise RuntimeError(
                "PyEITSolver.setup() must be called before creating an image."
            )
        import matplotlib.tri as mtri
        import numpy as np

        nodes = self.mesh_obj.node
        triangles = self.mesh_obj.element

        if len(ds) == len(nodes):
            node_values = ds

        elif len(ds) == len(triangles):
            node_sum = np.zeros(len(nodes))
            node_count = np.zeros(len(nodes))

            for element_index, triangle in enumerate(triangles):
                for node_index in triangle:
                    node_sum[node_index] += ds[element_index]
                    node_count[node_index] += 1

            node_count[node_count == 0] = 1
            node_values = node_sum / node_count

        else:
            raise ValueError(
                f"Unexpected reconstruction size: {len(ds)}"
            )

        triangulation = mtri.Triangulation(
            nodes[:, 0],
            nodes[:, 1],
            triangles,
        )

        interpolator = mtri.LinearTriInterpolator(
            triangulation,
            node_values,
        )

        x_axis = np.linspace(
            -1.0,
            1.0,
            self.grid_size,
        )

        # PNG rows run top -> bottom, while Cartesian +y runs bottom -> top.
        y_axis = np.linspace(
            1.0,
            -1.0,
            self.grid_size,
        )

        x_grid, y_grid = np.meshgrid(
            x_axis,
            y_axis,
        )

        image = interpolator(
            x_grid,
            y_grid,
        )

        image = np.ma.filled(
            image,
            0.0,
        )

        return ConductivityMap(
            values=image.tolist()
        )

    def close(self) -> None:
        """Release solver resources."""

        self.eit = None
        self.protocol_obj = None
        self.mesh_obj = None
        self.forward = None
        self._protocol_mapping = []
        self.n_electrodes = None
