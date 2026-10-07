"""Reconstruction solver contract.

Separates "how do we turn measurements into a conductivity image" from the rest
of the suite. The target engine is pyEIT (see
``software/reconstruction/PYEIT_SOLVER.md`` for the implementation brief), so
this contract is intentionally small and dependency-free.

Implementations live in ``software/reconstruction/`` (real) or
``software/sim/stub_solver.py`` (placeholder).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..core.types import ConductivityMap, MeshConfig, ScanData


@runtime_checkable
class SolverBackend(Protocol):
    """Reconstructs a conductivity map from a frame of measurements."""

    def setup(self, n_electrodes: int, mesh: MeshConfig) -> None:
        """Prepare the forward model / mesh for the given electrode count."""
        ...

    def reconstruct(
        self,
        frame: ScanData,
        baseline: ScanData | None = None,
    ) -> ConductivityMap:
        """Reconstruct ``frame``.

        ``frame.points`` are in the front end's standard adjacent order, so the
        implementation maps them straight onto its protocol (no reordering).
        When ``baseline`` is given, reconstruction is difference-based against
        it (the intended mode for phantom work: plain saline vs simulated
        bleed).
        """
        ...

    def close(self) -> None:
        """Release solver resources."""
        ...
