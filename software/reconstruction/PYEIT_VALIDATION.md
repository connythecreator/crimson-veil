# pyEIT integration validation

Validated on 14 October 2026. The numerical solver and host pipeline pass
synthetic end-to-end checks. Physical acquisition is not yet validated because
the firmware measurement routine and mux selection still have blockers below.

## Reference comparison

The [EIT Community page](https://eit.org.uk/systems/software_python/pyEIT/pyEIT_index.html)
identifies pyEIT and links to its repository; it does not specify a separate
pipeline or API. Implementation checks used the official
[eitcom/pyEIT repository](https://github.com/eitcom/pyEIT), at commit
`106863ab123e7763e6cdad0d43b338672731121c`, and the installed 1.2.4 release.

| Reference | Project behavior and result |
| --- | --- |
| [BP example](https://github.com/eitcom/pyEIT/blob/106863ab123e7763e6cdad0d43b338672731121c/examples/eit_dynamic_bp.py) | Circular mesh, adjacent drive/sense, `parser_meas="std"`, `weight="none"`, and `solve(v1, v0, normalize=True)` match. The example's display multiplier is not needed for arbitrary-unit, per-frame PNG scaling. |
| [Protocol](https://github.com/eitcom/pyEIT/blob/106863ab123e7763e6cdad0d43b338672731121c/pyeit/eit/protocol.py) | Added support for upstream flat `[N, M, excitation_index]` rows while retaining 1.2.4's grouped sense pairs. Count is derived from the mapped rows. Drive electrodes are excluded from voltage measurement. |
| [BP normalization](https://github.com/eitcom/pyEIT/blob/106863ab123e7763e6cdad0d43b338672731121c/pyeit/eit/bp.py) | BP divides differences by `sign(v0.real)`. Finite readings and nonzero real baseline values are now required. This is not amplitude normalisation or an absolute conductivity estimate. |
| [Forward solver](https://github.com/eitcom/pyEIT/blob/106863ab123e7763e6cdad0d43b338672731121c/pyeit/eit/fem.py) | Independent test acquisition samples node potentials in firmware order, without consulting the adapter mapping. Reordered measurements agree with upstream boundary voltages. |
| [Mesh geometry](https://github.com/eitcom/pyEIT/blob/106863ab123e7763e6cdad0d43b338672731121c/pyeit/mesh/shape.py) | Electrode 0 lies at the left of the unit disk; increasing indices run clockwise through the upper half. Descending image y coordinates preserve quadrant orientation. Physical placement must match. |

## Corrections made

- Support both upstream protocol layouts, maintaining one-to-one ordering and
  sense polarity correction.
- Require a captured baseline by default. The homogeneous unit-model reference
  is available only with explicit `allow_homogeneous_reference=True` for FEM
  simulations. Raw device counts do not have a demonstrated common scale with it.
- Add validated baseline capture and retention in `ScanSession`, WebSocket
  commands, and the kiosk's CALIB page. Frequency changes invalidate references;
  concurrent capture, scan and frequency changes are rejected.
- Validate serial frame lengths, finite values and indices; restore firmware
  order when indexed points arrive shuffled. Wholly unindexed legacy frames
  retain their incoming order.
- Prevent telemetry from consuming scan responses. Buffer incomplete serial
  lines so nonblocking polling does not discard part of a JSON frame. After a
  receive error, drain through a new identify handshake before another scan;
  delayed old responses cannot become a new target or baseline. Recovery keeps
  the requested frequency and rejects changed electrode counts.
- Keep the firmware command loop alive after scans and stop commands. Close
  partially opened resources after setup failure, and wait for an active scan
  before closing its resources.
- Add `requirements-pyeit.txt` with pyEIT 1.2.4 pinned. Base stub dependencies
  remain separate. Existing untracked user scripts and OneDrive conflict files
  were left unchanged.

## Test evidence

Runtime: Windows, Python 3.13.13, NumPy 2.5.3, SciPy 1.18.1, Matplotlib 3.11.2,
pytest 9.1.1. The working interpreter is `.venv-win/Scripts/python.exe`.
The `.venv` environment points to an unavailable macOS Python and was not altered.

| Final run | Result |
| --- | --- |
| Installed pyEIT 1.2.4 | **118 passed**, 12.64 seconds |
| Official GitHub source at `106863ab123e7763e6cdad0d43b338672731121c` | **118 passed**, 12.75 seconds |
| Whitespace/error check (`git diff --check`) | Passed |
| Rust build and runtime UI | Not run: Cargo/rustc unavailable |

The release and upstream test runs cover:

- Adjacent protocols for 4, 8 and 16 electrodes; eight electrodes yield 40 points.
- Independent FEM voltage acquisition, equal baseline/frame producing zero,
  and both increased and decreased conductivity localized in all four quadrants.
- Correct positive/negative reconstruction signs and finite image values.
- Rejection of malformed counts, electrode/frequency mismatches, NaN/Inf and
  zero-real baseline measurements.
- Real `Esp32Hardware` parsing → `ScanSession` baseline capture → `pipeline` →
  `PyEITSolver` → PNG → live localhost WebSocket client. The fake serial device
  sends independently generated FEM readings, shuffled indices and telemetry.
  Two target scans return the expected PNG exactly and retain the same baseline.
- Frequency invalidation, busy handling, capture failure/retry, cleanup after
  setup failure, shutdown during acquisition, and recovery from complete or
  partial delayed serial frames without reusing stale data.
- Firmware command-loop behavior using host-side driver doubles; these do not
  exercise real GPIO, I2C or an AD5933.

Run the installed release suite from the repository root in PowerShell:

```powershell
& .\.venv-win\Scripts\python.exe -m pytest --ignore-glob='*MacBook*' -v
```

The exclusion preserves the pre-existing untracked OneDrive conflict copy
`tests/test_pyeit_project-Adam’s MacBook Pro.py`; it is not the maintained test.
All maintained tests are included. Network tests need functioning localhost
sockets; this environment's restricted sandbox blocks Python's event-loop
socket pair, so the successful network runs used approved execution outside it.

For upstream verification, download the repository at the commit above into a
separate folder and place that folder first on `sys.path` for a test process.
Do not overwrite the installed package. Both layouts are exercised against
actual pyEIT implementations, not just mocked protocol objects.

## Remaining limits

1. **AD5933 acquisition is unfinished.** `firmware/mp-firm/src/ad5933_driver.py`
   implements `measure()` as an unconditional `AD5933Error`. Physical scans
   cannot currently produce readings through this firmware.
2. **Mux roles do not retain distinct addresses.** `MuxBank` shares address
   pins across the four roles. `select_measurement()` changes that same address
   repeatedly while enabling each role. With requested drive `(0, 1)` and sense
   `(2, 3)`, the code leaves all enabled roles on address 3. Confirm the schematic
   and independent selection/latching mechanism before changing GPIO behavior.
3. **Calibration is not established.** Startup supplies no measured gain/phase
   correction table. The default correction is identity. A captured reference
   does not replace verified front-end calibration, polarity, units and geometry.
4. **Default `SimHardware` is a demonstration model.** Its heuristic impedance
   values are not FEM-consistent. Quantitative validation uses independent FEM
   acquisition in the tests, not the default toy phantom.
5. **Rust kiosk compilation is unverified here.** Protocol/state tests were
   added and the UI changes reviewed, but Cargo/rustc are unavailable. Run
   `cargo test --manifest-path kiosk-rs/Cargo.toml` and check the CALIB flow on
   the target kiosk before deployment.

These checks demonstrate numerical and host transport correctness for synthetic
data. They do not establish physical phantom performance, clinical accuracy,
absolute conductivity, or robustness to electrode contact impedance and noise.
