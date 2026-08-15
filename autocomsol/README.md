# AutoCOMSOL Skill

AutoCOMSOL is a documentation-and-reference skill for designing and validating new COMSOL Multiphysics Java models that run through `comsolcompile` and `comsolbatch`.

It contains no COMSOL installation, launcher, execution wrapper, dependency, or binary. The complete Java models under `references/examples/` are locally validated API references, not a packaged simulation runtime.

## Install

Install the entire `autocomsol` directory as a Codex skill. Its directory name and the `name` field in `SKILL.md` must remain `autocomsol`.

### From a local checkout

From the root of this repository, copy the checked-out directory into the Codex skills directory:

```powershell
Copy-Item -Recurse -Force (Get-Item .) $env:USERPROFILE\.codex\skills
```

Restart Codex or refresh its installed skills after copying. Invoke it explicitly with `$autocomsol`, or let Codex select it for COMSOL Java modelling requests.

### From a Git repository

Clone the repository into the parent directory of your choosing, then run the local-checkout command from the cloned `autocomsol` directory. Keep the directory contents together; `SKILL.md`, `agents/openai.yaml`, and `references/` are all required parts of this distribution.

## What it provides

- A workflow for turning a simulation requirement into a distinct Java model, batch run, export contract, and model-specific numerical checks.
- Locally evidenced COMSOL Java API patterns for electric currents, electrostatics, heat transfer, solid mechanics, electric-thermal and electric-thermal-structural couplings, and frequency-domain electromagnetic waves (emw).
- Deterministic 2D and 3D geometry-selection methods, so models do not depend on guessed boundary, face, or domain numbers.
- Twelve complete Java references, including stationary, transient, multiphysics, multi-material, complex busbar, and periodic EM-wave cases.

## Use

Example request:

```text
Use $autocomsol to create a 3D transient electric-thermal COMSOL Java model for a cylindrical conductor with convective cooling, then define an analytical or physics-based validation plan.
```

The Skill directs Codex to inspect the closest complete Java example and locally recorded API evidence before using nontrivial COMSOL calls. It expects compilation and batch execution to take place in the consuming project's COMSOL environment.

## Contents

```text
autocomsol/
├── SKILL.md                 # Trigger metadata and workflow
├── agents/openai.yaml       # Codex UI metadata
└── references/
    ├── examples/            # Complete Java API references
    ├── command-usage.md     # comsolcompile/comsolbatch usage
    ├── case-naming.md       # Naming and physics/materials/variables mapping
    ├── geometry-selection.md
    ├── physics-api-recipes.md  # Validated recipes, pitfalls, advanced patterns
    └── verification-guidelines.md
```

## Scope

The bundled evidence was collected on a local COMSOL 6.2 installation. API names and availability can vary by COMSOL version and licensed modules. Confirm unfamiliar APIs with the target installation before relying on them.
