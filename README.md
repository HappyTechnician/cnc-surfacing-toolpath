# CNC surfacing toolpath (GRBL)

A simple Python script that generates a surfacing/facing raster toolpath for GRBL CNC controllers.

## What it does
- Prompts for:
  - X length, Y length
  - Total Z depth (from **stock top**, Z=0)
  - Travel axis (X or Y)
  - Bit diameter
  - Overshoot length in X and Y (user-defined)
  - User-defined Z depth steps (schedule)
  - Feeds, safe Z, spindle RPM
- Uses **stepover = 50% of bit diameter**
- Generates a zig-zag raster covering the overshot rectangle
- Runs the **final depth layer** at **2/3** of the normal XY feed rate

## Run
```bash
python3 surfacing_toolpath_generator_grbl.py
```

## Safety
Always:
- Simulate the G-code
- Air-cut first
- Confirm overshoot motion won’t hit clamps/fixtures
