# pyEIT solver

`software/reconstruction/pyeit_solver.py` implements difference-EIT using
pyEIT's adjacent-drive protocol and back-projection solver. It interpolates
the reconstruction onto a 96 × 96 conductivity map and is selected with
`CV_SOLVER=pyeit`.

## API checklist

| Member | Contract |
|---|---|
| `PyEITSolver(grid_size=96, frequency_hz=50000.0)` | Configure output resolution and default frequency |
| `setup(n_electrodes, mesh)` | Build the circular FEM mesh, protocol and BP solver |
| `mesh_obj` | Expose the pyEIT mesh for diagnostics and digital tests |
| `reconstruct(frame, baseline=None)` | Return a `ConductivityMap`; use a supplied baseline or homogeneous forward reference |
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

Each scan contains one frequency. The frame's frequency is authoritative, so
a frequency changed through the scan session is used for the next frame. A
supplied baseline must have the same frequency, electrode count and point
count as the target frame.

## Baseline behavior

Pass a separately captured saline frame as `baseline` for measured
baseline-to-target reconstruction. When no frame is supplied, the solver uses
pyEIT's homogeneous forward solution as its reference. The digital integration
test supplies a baseline; capturing and retaining a baseline in the user-facing
`ScanSession` is a separate feature.

## Dependencies

The pyEIT backend requires `pyeit`, `numpy`, `scipy` and `matplotlib`. They
remain optional for users of the default stub solver and are not added to the
base requirements. Install them in the environment where `CV_SOLVER=pyeit` is
selected.
