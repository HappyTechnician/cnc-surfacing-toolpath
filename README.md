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

## CLI mode (non-interactive)

The script also supports optional command-line arguments so you can generate files without prompts.

```bash
python3 surfacing_toolpath_generator_grbl.py \
  --x-len 100 \
  --y-len 60 \
  --total-depth 1.0 \
  --travel-axis X \
  --bit-diam 10 \
  --overshoot-x 5 \
  --overshoot-y 3 \
  --ramp-len 0 \
  --feed-xy 800 \
  --feed-z 300 \
  --safe-z 5 \
  --spindle-rpm 12000 \
  --depth-steps 0.25,0.5,0.75,1.0 \
  --output surfacing.nc
```

### Notes
- `--depth-steps` accepts comma-separated positive values from stock top.
- Blank `--depth-steps` means one pass at total depth.
- Out-of-order depth steps are auto-sorted; duplicates are removed.
- Use `--spindle-rpm 0` to omit `M3/M5` commands.

## UGS quick start

1. Generate your G-code file (`.nc`) with the script.
2. Open UGS and connect to your GRBL controller.
3. Unlock/home as needed (`$X`, `$H` if your setup uses homing).
4. Set work zero:
   - X0/Y0 at your chosen stock corner
   - Z0 at stock top
5. Load the `.nc` file in UGS and check visual bounds.
6. Do an air cut first.
7. Run the job.

## First-run safe preset (example)

Use this conservative example to validate motion before real cutting:

```bash
python3 surfacing_toolpath_generator_grbl.py \
  --x-len 100 \
  --y-len 60 \
  --total-depth 0.2 \
  --travel-axis X \
  --bit-diam 10 \
  --overshoot-x 2 \
  --overshoot-y 2 \
  --ramp-len 0 \
  --feed-xy 300 \
  --feed-z 120 \
  --safe-z 8 \
  --spindle-rpm 0 \
  --depth-steps 0.2 \
  --output surfacing_first_run.nc
```

## Safety
Always:
- Simulate the G-code
- Air-cut first
- Confirm overshoot motion won’t hit clamps/fixtures
