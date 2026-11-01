# Safety model

`printer.py` sends nothing to the printer without `--live`. With `--live`, every line of a plan
goes through `safety.check()`. If **any** line is refused, the whole plan is not sent.

Allowed, with default bounds (override with `--limits my_limits.json`):

| Command | Bound |
|---|---|
| `M220 S` speed factor | 50–150% |
| `M221 S` flow | 85–115%, at most ±10% per step |
| `M104/M109 S` hotend | 170–290 °C, and within ±15 °C of the session's starting target |
| `M140/M190 S` bed | 0–110 °C, at most ±10 °C from the current target |
| `M106 S` / `M107` fan | 0–255 |
| `SET_PRESSURE_ADVANCE ADVANCE=` | 0–0.2 |
| `SET_RETRACTION` | length 0–6 mm, speeds 10–70 mm/s |
| `SET_GCODE_OFFSET Z_ADJUST=` [`MOVE=1`] | ±0.05 mm per step, ±0.2 mm cumulative |
| `M204` / `SET_VELOCITY_LIMIT ACCEL=` | 300–6000 mm/s² |

Always refused:
- motion (G0–G3), homing, probing and mesh
- firmware or host restart, `SAVE_CONFIG`, stepper and kinematic overrides, `M112`
- cancel, SD card commands, pin and heater overrides
- any command not on the list

Stage gates:
- `apply` only runs while the printer reports `paused`.
- `apply` requires a recorded detect and plan for this layer.
- A plan requires at least one query when problems were reported.
- `resume` requires an applied plan, possibly empty, when problems were reported.

The human stays in charge:
- Run the first job in dry-run mode, read `report`, then switch to `--live`.
- Never leave a live loop unattended on a printer that has no thermal-runaway protection.
- Stop and tell the user about layer shifts, spaghetti, detachment, smoke or smell, and
  anything mechanical.
