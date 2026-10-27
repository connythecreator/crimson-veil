# pyEIT solver

`software/reconstruction/pyeit_solver.py` implements difference-EIT using
pyEIT's adjacent-drive protocol and back-projection solver. It interpolates
the reconstruction onto a 96 × 96 conductivity map and is selected with
`CV_SOLVER=pyeit`.

## API checklist

| Member | Contract |
|---|---|
| `PyEITSolver(grid_size=96, frequency_hz=50000.0, *, allow_homogeneous_reference=False)` | Configure output resolution; model reference is an explicit simulation-only option |
| `setup(n_electrodes, mesh)` | Build the circular FEM mesh, protocol and BP solver |
| `mesh_obj` | Expose the pyEIT mesh for diagnostics and digital tests |
| `reconstruct(frame, baseline=None)` | Return a `ConductivityMap`; a measured baseline is required by default |
| `_to_conductivity_map(ds)` | Interpolate FEM values to `grid_size × grid_size` pixels |
| `close()` | Release references to solver and mesh resources |

The implementation satisfies `software/interfaces/solver.py`. pyEIT, NumPy
and Matplotlib imports are lazy so selecting the default stub backend does not
require those optional dependencies.

## Scan data and ordering

The ESP32 owns acquisition and sends one frame per scan. A frame contains
`n_electrodes * (n_electrodes - 3)` points, plus its frequency and electrode
count; the host does not send or store a measurement plan. The solver validates
those fields and maps firmware order to pyEIT's protocol.

The protocols agree on drive-pair order but not on sense-pair orientation:
firmware measures `(e + 2, e + 3)`, while pyEIT can represent the same pair as
`(e + 3, e + 2)`. The solver maps each pyEIT measurement to the corresponding
firmware point and negates the real value when the sense pair is reversed. It
builds and validates this one-to-one mapping during setup.

Both pyEIT 1.2.4's grouped `(n_exc, n_meas, 2)` layout and upstream's flat
`(n_meas_total, 3)` layout (`N, M, excitation_index`) are supported. The
adapter follows the actual row order rather than assuming each drive has a
contiguous block. Eight electrodes produce 40 measurements.

Each scan contains one frequency. The frame's frequency is authoritative, so
a frequency changed through the scan session is used for the next frame. A
supplied baseline must have the same frequency, electrode count and point
count as the target frame.

Real and imaginary components must be finite. Reconstruction uses the real
component to image conductivity changes; it does not reconstruct complex
admittivity or estimate absolute conductivity. Upstream BP's `normalize=True`
divides by `sign(v0.real)`, not the reference amplitude. Zero-real reference
measurements are rejected. A constant gain therefore still scales the output,
which is in arbitrary units. PNG brightness is normalised per image.

The circular mesh is a unit disk. Electrode 0 is at `(-1, 0)` and increasing
indices go clockwise through the upper half of the circle. Image rows run from
positive to negative y. Physical electrode numbering must follow that geometry
to interpret the image direction correctly.

## Baseline behavior

Pass a separately captured saline frame as `baseline` for measured
baseline-to-target reconstruction. `ScanSession.capture_baseline()` acquires
and validates that frame, retains it across scans, and passes it through
`pipeline.run_scan()`. A frequency change or session close clears it. Capturing,
scanning and changing frequency cannot overlap. Failed boot produces an error.

In the kiosk, open **CALIB**, prepare the unchanged reference phantom, and
select **Capture baseline**. Wait for capture to complete before introducing
the target change. pyEIT continuous scanning starts after a successful capture.
Recapture after changing frequency or reconnecting/repositioning electrodes.
This reference capture is separate from the hardware's gain/phase calibration.

For model-consistent FEM simulations only, construct the solver with
`allow_homogeneous_reference=True` to use its homogeneous forward reference.
That reference assumes unit current and unit background conductivity; it cannot
be subtracted directly from arbitrary AD5933 counts or unscaled measured values.

## Dependencies

Install the optional backend with `python -m pip install -r requirements-pyeit.txt`,
then select `CV_SOLVER=pyeit`. This pins the tested pyEIT 1.2.4 release and installs
its NumPy, SciPy and Matplotlib dependencies. The default stub remains lightweight.

See [PYEIT_VALIDATION.md](PYEIT_VALIDATION.md) for upstream references, tested
versions, reproducible commands, coverage, and the remaining hardware limits.
