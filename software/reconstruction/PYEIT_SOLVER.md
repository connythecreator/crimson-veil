# pyEIT solver — implementation brief

Where and how to implement the real reconstruction backend. Until this exists,
`CV_SOLVER=pyeit` raises `NotImplementedError` in `software/pipeline.py`.

## File to create

`software/reconstruction/pyeit_solver.py` — `class PyEITSolver`.

## API it must expose

`tests/test_pyeit_project.py` pins the surface:

| Member | Signature | Notes |
|---|---|---|
| `PyEITSolver(...)` | `grid_size: int`, `frequency_hz: float` | constructor kwargs |
| `setup` | `setup(n_electrodes: int, mesh: MeshConfig)` | build mesh + protocol |
| `mesh_obj` | attribute | the pyEIT mesh object |
| `reconstruct` | `reconstruct(frame: ScanData, baseline: ScanData \| None = None) -> ConductivityMap` | `SolverBackend` method |
| `_to_conductivity_map` | `_to_conductivity_map(ds) -> ConductivityMap` | grid-sized map |
| `close` | `close()` | release resources |

Also satisfy `software/interfaces/solver.py` so it can be a `SolverBackend`.

## Algorithm

```python
import numpy as np
import pyeit.mesh as mesh
import pyeit.eit.protocol as protocol
import pyeit.eit.bp as bp
from pyeit.eit.fem import EITForward

# setup(n_electrodes, mesh_cfg)
self.mesh_obj = mesh.create(n_electrodes)                       # circular mesh
self.protocol = protocol.create(
    n_electrodes, dist_exc=1, step_meas=1, parser_meas="std",   # the project protocol
)
self.forward = EITForward(self.mesh_obj, self.protocol)
self.eit = bp.BP(self.mesh_obj, self.protocol)
self.eit.setup(weight="none")
self.v0 = self.forward.solve_eit()                              # baseline (optional cache)

# reconstruct(frame, baseline)
v1 = <frame points as a 1-D array>                              # len == protocol.n_meas_tot
v0 = <baseline points> if baseline else self.v0
ds = np.real(self.eit.solve(v1, v0, normalize=True))
return self._to_conductivity_map(ds)
```

## Point ordering (already aligned)

The **front end owns the scan plan**. `frame.points` arrive in the firmware's
standard adjacent order — firmware `default_scan`
(`firmware/mp-firm/src/main.py`) produces `drive=(e,e+1)`,
`sense=(e+2..e+n-1)` for `e` in `0..n-1`. That is exactly
`protocol.create(n, dist_exc=1, step_meas=1, parser_meas="std")`'s order, so
map `points[i]` straight to measurement `i` — **no reordering**. The host does
not build a plan.

Use the point's complex value: `v[i] = point.real` for the real part, or
`complex(point.real, point.imag)` if the solver takes complex input. One
frequency per scan today, so `v` is 1-D length `n * (n - 3)` (8 → 40).

## `_to_conductivity_map(ds)`

`ds` is a per-element array on the pyEIT mesh. Interpolate it onto a
`grid_size × grid_size` image (either `pyeit.eit.interp2d` or a regular grid via
`scipy.interpolate`) and return
`ConductivityMap(values=<grid_size x grid_size floats>)`. The test asserts
`width == height == grid_size`.

## Wiring it in

1. `software/core/config.py` — `SOLVER_BACKEND = os.environ.get("CV_SOLVER", "stub")`.
2. `software/pipeline.py` `default_solver()` — replace the `"pyeit"`
   `NotImplementedError` branch with:
   ```python
   from .reconstruction.pyeit_solver import PyEITSolver
   return PyEITSolver(grid_size=96, frequency_hz=config.DEFAULT_FREQUENCY_HZ)
   ```
3. `service/session.py` calls `solver.setup(config.N_ELECTRODES, config.mesh_config())`
   at boot, which now takes the pyEIT path.

## Dependencies (installed manually, not pinned here)

`pyeit`, `numpy`, `scipy` (pyEIT pulls the latter two). They are deliberately
**not** added to `requirements*.txt`; install them by hand on the machine that
runs the solver.

## Notes

- `frequency_hz` is the single scan frequency (`ScanData.frequency_hz`); a
  multi-frequency sweep is a future change.
- Difference mode: pass `baseline=ScanData(...)` from a plain-saline capture to
  `reconstruct`; otherwise the solver differences against the homogeneous
  forward solution `v0`.
- Keep the class import-cheap: import `pyeit`/`numpy` inside `setup()` so the
  base suite still runs without them.
