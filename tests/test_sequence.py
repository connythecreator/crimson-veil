"""Sequencing and the tetrapolar invariant."""

import pytest

from software.acquisition import electrode, sequence


def test_drive_and_sense_are_disjoint_for_all_measurements():
    plan = sequence.adjacent_drive_plan([5_000.0, 50_000.0], n_electrodes=8)
    for m in plan:
        assert not (set(m.drive) & set(m.sense)), m


def test_plan_size_is_frequencies_times_electrodes():
    plan = sequence.adjacent_drive_plan([5_000.0, 20_000.0, 50_000.0], n_electrodes=8)
    assert len(plan) == 3 * 8


def test_all_measurements_use_only_valid_electrodes():
    plan = sequence.adjacent_drive_plan([5_000.0], n_electrodes=8)
    for m in plan:
        for idx in (*m.drive, *m.sense):
            assert 0 <= idx < 8


def test_validate_rejects_overlap():
    with pytest.raises(electrode.ElectrodeError):
        electrode.validate((0, 4), (0, 6), n_electrodes=8)


def test_validate_rejects_same_electrode_twice():
    with pytest.raises(electrode.ElectrodeError):
        electrode.validate((2, 2), (4, 6), n_electrodes=8)


def test_validate_rejects_out_of_range():
    with pytest.raises(electrode.ElectrodeError):
        electrode.validate((0, 4), (6, 99), n_electrodes=8)
