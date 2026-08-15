# Deterministic geometry selection

Do not hard-code entity numbers. Create geometry, call `geom.run()`, then derive the entities needed by physics selections from `GeomInfo`.

## 2D edges

For each edge from `1` to `geom.getNEdges()`, call `edgeX(edge, new double[] {0.5})`. Classify the sampled midpoint by coordinate tolerance, then use the resulting edge IDs in `selection().set(...)`.

Validated square ordering happened to be left=1, bottom=2, top=3, right=4. This is evidence for `edgeX`, not a numbering convention to reuse.

## 3D faces

Call `faceParamRange(face)` before `faceX`. Use the midpoint of each returned parameter interval, and sample multiple points where a curved or segmented surface is possible.

- Planar faces: classify a constant x, y, or z coordinate.
- Cylindrical walls: classify with `x*x + y*y` near the target radius; a cylinder wall may be partitioned into multiple faces.
- Use all matching face IDs for a physical boundary such as an inner or outer cylindrical wall.

## Domains and exterior faces

- `geom.getUpDown()[1]` provides the face-to-domain relation used in the validated multi-domain cases.
- `geom.getAdj(2, 3)` identifies face/domain adjacency: one adjacent domain indicates an exterior face, two indicate an interior interface.
- Combine adjacency with face samples or domain-level geometric measures to classify materials and contacts.

Read `examples/EcTCylinderStationary.java` for core/shell identification, and `examples/EcTSmBusbarStationary.java` for exterior-face and bolt-end identification.

## Ordering caveat

Face numbering is not consistently ordered across `getAdj(2, 3)`, `getUpDown()`, and
`faceX()` enumeration. On some geometries the adjacency array can disagree with the face
samples (validated on the emw slab). When the two conflict, classify faces by their
sampled face-center coordinates instead of by adjacency counts — do not trust either
ordering to match physics selection numbering.
