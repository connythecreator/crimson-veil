"""Interface contracts stay dependency-free and structurally correct."""

from software.core.types import (
    ConductivityMap,
    DeviceConfig,
    Measurement,
    RawPoint,
    ScanData,
)


def test_measurement_is_hashable_and_frozen():
    m = Measurement(freq_hz=5_000.0, drive=(0, 4), sense=(2, 6))
    assert m.drive == (0, 4)
    assert {m, m} == {m}


def test_rawpoint_magnitude_and_phase():
    p = RawPoint(freq_hz=1_000.0, real=3.0, imag=4.0)
    assert abs(p.magnitude - 5.0) < 1e-9
    assert abs(p.phase - 0.927295218) < 1e-6


def test_conductivity_map_dimensions():
    cmap = ConductivityMap(values=[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    assert cmap.width == 3
    assert cmap.height == 2


def test_scan_data_len_tracks_points():
    frame = ScanData(points=[RawPoint(1.0, 1.0, 0.0), RawPoint(2.0, 1.0, 0.0)])
    assert len(frame) == 2


def test_default_device_config_is_sim():
    cfg = DeviceConfig()
    assert cfg.backend == "sim"
    assert cfg.frequency_hz > 0
