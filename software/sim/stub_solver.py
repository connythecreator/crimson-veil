"""Placeholder solver.

Implements :class:`~software.interfaces.solver.SolverBackend` by returning the
phantom ground truth, so the pipeline and kiosk produce a real image before the
actual reconstruction engine (pyEIT/EIDORS) is chosen. Selected when
``config.SOLVER_BACKEND == "stub"``.
"""

from __future__ import annotations

from ..core.types import ConductivityMap, MeshConfig, ScanData
from . import phantom


class StubSolver:
    def __init__(self, include_bleed: bool = True) -> None:
        self.include_bleed = include_bleed

    def setup(self, n_electrodes: int, mesh: MeshConfig) -> None:
        pass

    def reconstruct(self, frame: ScanData, baseline: ScanData | None = None) -> ConductivityMap:
        return phantom.ground_truth(include_bleed=self.include_bleed)

    def close(self) -> None:
        pass
