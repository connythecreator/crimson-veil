"""Electrode roles and the tetrapolar invariant.

Eight Ag/AgCl electrodes around the abdomen (see
``docs/eit-bioimpedance/SENSOR-PLACEMENT.md``). Any electrode can take any of
the four roles (drive+/drive-/sense+/sense-) via the mux bank, but within a
single measurement the drive pair and sense pair must be four DISTINCT
electrodes.
"""

from __future__ import annotations

N_ELECTRODES = 8


class ElectrodeError(ValueError):
    """Raised when a measurement violates the electrode rules."""


def validate(
    drive: tuple[int, int],
    sense: tuple[int, int],
    n_electrodes: int = N_ELECTRODES,
) -> None:
    """Validate a tetrapolar measurement.

    Rules:
      * electrode indices in range [0, n_electrodes)
      * drive pair has two distinct electrodes
      * sense pair has two distinct electrodes
      * drive and sense do not overlap
    """
    for name, pair in (("drive", drive), ("sense", sense)):
        a, b = pair
        if not (0 <= a < n_electrodes and 0 <= b < n_electrodes):
            raise ElectrodeError(f"{name} pair {pair} out of range 0..{n_electrodes - 1}")
        if a == b:
            raise ElectrodeError(f"{name} pair {pair} uses the same electrode twice")

    overlap = set(drive) & set(sense)
    if overlap:
        raise ElectrodeError(
            f"drive {drive} and sense {sense} overlap on electrode(s) {sorted(overlap)}"
        )
