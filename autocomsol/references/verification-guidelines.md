# Verification guidelines

Define acceptance criteria while designing the model, before a batch run.

## Prefer independent checks

1. Compare with an analytical solution when the geometry and boundary conditions allow it.
2. Check imposed boundary values and physically valid ranges.
3. Check symmetry, conservation, and constitutive identities.
4. For discretization-sensitive results, perform a mesh-convergence comparison.

## Export deliberately

- Export values valid for the selected dataset and entity dimension.
- Do not use global evaluation for a domain-only expression.
- Save enough coordinates, time values, domain identifiers, and fields to reproduce the check.

## Batch success criteria

Require all of the following:

- compilation succeeds and the expected class exists;
- `comsolbatch` exits successfully;
- expected MPH and exported data files exist;
- batch log has no meaningful exception, license, failure, divergence, or out-of-memory signal;
- model-specific numerical checks pass.

A solver can exit with code zero while returning a trivial field caused by a wrong selection or terminal definition. Detect this using independent numerical checks.
