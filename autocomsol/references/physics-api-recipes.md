# Validated physics API recipes

Use these as local COMSOL 6.2 evidence. Read the linked full Java case before applying a recipe.

| Scope | Interface / coupling | Important evidence | Full reference |
| --- | --- | --- | --- |
| Electrostatics | `Electrostatics` | Explicit `TerminalType="Voltage"` is required for a voltage terminal. | `examples/EcSquareStationary.java` |
| Electric currents | `ConductiveMedia` | `ElectricCurrents` was not registered locally; use `electricconductivity`, and use `relpermittivity` where required. | `examples/EcSquareStationary.java` |
| Solid heat transfer | `HeatTransfer` | Boundary features use `TemperatureBoundary` and `HeatFluxBoundary`; material properties include `thermalconductivity`, `density`, `heatcapacity`. | `examples/TCylinderStationary.java` |
| Solid mechanics | `SolidMechanics` | Use `Fixed`, `Roller`, and `BoundaryLoad`; configure `lemm1` elastic properties deliberately. | `examples/SmCylinderAxialStationary.java` |
| Electric to thermal | `multiphysics().create(..., "ElectromagneticHeating")` | Set `EMHeat_physics` and `Heat_physics`; use `multiphysics()`, not `coupling()`. | `examples/EcTCylinderTransient.java` |
| Thermal to structural | `multiphysics().create(..., "ThermalExpansion")` | Select all intended domains explicitly; thermal expansion is `thermalexpansioncoefficient`. | `examples/EcTSmCylinderStationary.java` |

For exact feature tags, properties, study creation, datasets, and exports, use `case-naming.md`, then inspect the full reference code. Search `lab-notebook.md` for a failed alternative before substituting an unverified name.
