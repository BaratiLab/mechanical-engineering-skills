# Printer setup (Klipper + Moonraker)

1. Install Klipper, Moonraker and a camera streamer (Crowsnest) with KIAUH. Mount a
   **top** camera above the bed and a **front** camera at bed level. Name them `top` and
   `front` in Moonraker's webcam settings. `snapshot` saves one image per webcam.
2. Add to `printer.cfg`:

```ini
[pause_resume]
[firmware_retraction]          # lets SET_RETRACTION work; slice with firmware retraction (G10/G11)
retract_length: 0.8
retract_speed: 35

[gcode_macro LAYER_INSPECT]
description: Park the head clear of both cameras and pause for agent inspection
gcode:
    {% set L = params.LAYER|default(0)|int %}
    M400
    SAVE_GCODE_STATE NAME=inspect
    G91
    G1 Z5 F600                 ; lift
    G90
    G1 X{printer.toolhead.axis_maximum.x - 5} Y{printer.toolhead.axis_maximum.y - 5} F6000
    M400
    G4 P1500                   ; let the camera settle
    RESPOND MSG="inspect layer {L}"
    PAUSE
    # RESUME restores the position through pause_resume. If your PAUSE macro also parks,
    # remove the lift and park above to avoid a double move.
```

3. Post-process the sliced file:
   `python scripts/add_layer_pauses.py part.gcode part_mon.gcode --every 1`.
   Use `--every 2` or more for tall parts. Each pause costs about 30–90 s of agent time,
   and long pauses can leave a seam.
4. Moonraker endpoints used:
   - `GET /printer/objects/query?…`
   - `POST /printer/gcode/script`
   - `POST /printer/print/resume`
   - `GET /server/webcams/list` and each webcam's `snapshot_url`

   If Moonraker has an API key, put the printer behind your LAN and use trusted clients. The
   client does not send keys.
