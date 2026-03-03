#!/usr/bin/env python3
"""
GRBL surfacing raster generator.

Features:
- Stepover = 0.5 * bit diameter (fixed)
- Overshoot on BOTH axes, FULL coverage of overshot rectangle
- Overshoot length is USER-DEFINED (X and Y independently)
- Guarantees nominal boundary lines (0 and max on stepover axis) plus overshoot bounds
- User-defined Z depth schedule (comma-separated positive depths from stock top)
- Multi-depth cutting
- Ramp-in (optional)
- Last depth layer runs at 2/3 of the normal XY feed
- Stepover speed is NOT changed (no rapid stepovers at cut depth)

Z convention:
- You set Z=0 at STOCK TOP.
- Enter depths as POSITIVE numbers (mm) meaning "down into stock".
  The code cuts at Z = -depth.
"""

from math import ceil


def ask_float(prompt: str, *, allow_zero: bool = False, default=None, min_value=None) -> float:
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            val = float(default)
        else:
            try:
                val = float(raw)
            except ValueError:
                print("Please enter a valid number (e.g., 123.4).")
                continue

        if allow_zero and val == 0:
            return val
        if min_value is not None and val < min_value:
            print(f"Please enter a number >= {min_value}.")
            continue
        if val <= 0:
            print("Please enter a number greater than 0.")
            continue
        return val


def ask_axis(prompt: str) -> str:
    while True:
        raw = input(prompt).strip().upper()
        if raw in ("X", "Y"):
            return raw
        print("Please enter X or Y.")


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def fmt3(v: float) -> str:
    return f"{v:.3f}"


def unique_sorted(vals, tol=1e-9):
    vals = sorted(vals)
    out = []
    for v in vals:
        if not out or abs(v - out[-1]) > tol:
            out.append(v)
    return out


def positions_with_boundaries(start: float, end: float, stepover: float, must_include):
    if end < start:
        start, end = end, start

    span = end - start
    n = int(ceil(span / stepover)) + 1

    vals = [start + i * stepover for i in range(n)]
    vals.append(end)
    vals.extend(must_include)

    vals = [clamp(v, start, end) for v in vals]
    return unique_sorted(vals)


def build_raster_points(
    x_len: float,
    y_len: float,
    travel_axis: str,
    stepover: float,
    overshoot_x: float,
    overshoot_y: float,
):
    """
    Full overshoot coverage. Start point is (x_min, y_min) in overshoot zone.
    Also guarantees nominal boundary lines (0 and x_len or y_len) on stepover axis.
    """
    x_min = -overshoot_x
    x_max = x_len + overshoot_x
    y_min = -overshoot_y
    y_max = y_len + overshoot_y

    pts = []

    if travel_axis == "X":
        y_positions = positions_with_boundaries(
            start=y_min, end=y_max, stepover=stepover, must_include=[0.0, y_len]
        )
        for i, y in enumerate(y_positions):
            if i % 2 == 0:
                pts.append((x_min, y))
                pts.append((x_max, y))
            else:
                pts.append((x_max, y))
                pts.append((x_min, y))
        return pts, len(y_positions)

    # travel_axis == "Y"
    x_positions = positions_with_boundaries(
        start=x_min, end=x_max, stepover=stepover, must_include=[0.0, x_len]
    )
    for i, x in enumerate(x_positions):
        if i % 2 == 0:
            pts.append((x, y_min))
            pts.append((x, y_max))
        else:
            pts.append((x, y_max))
            pts.append((x, y_min))
    return pts, len(x_positions)


def parse_depth_schedule(total_depth: float):
    """
    User-defined Z depth steps.
    - Input positive depths, strictly increasing.
    - If the final depth isn't included, append total_depth.
    - Returns negative Z targets.
    """
    while True:
        raw = input(
            "Enter Z depth steps from stock top as comma-separated POSITIVE depths\n"
            "Example: 0.25,0.50,0.75,1.00\n"
            "Depth steps: "
        ).strip()

        try:
            parts = [p.strip() for p in raw.split(",") if p.strip() != ""]
            depths = [float(p) for p in parts]
        except ValueError:
            print("Could not parse. Please enter numbers separated by commas.")
            continue

        if not depths:
            print("Please enter at least one depth.")
            continue
        if any(d <= 0 for d in depths):
            print("All depths must be > 0.")
            continue
        if any(depths[i] <= depths[i - 1] for i in range(1, len(depths))):
            print("Depths must be strictly increasing (e.g., 0.25,0.50,0.75).")
            continue
        if depths[-1] > total_depth + 1e-9:
            print(f"Last depth step ({depths[-1]}) exceeds total depth ({total_depth}).")
            continue

        if abs(depths[-1] - total_depth) > 1e-6:
            depths.append(total_depth)

        return [-abs(d) for d in depths]


def emit_layer(g, pts, *, target_z, feed_xy, feed_z, ramp_len):
    """
    Emits the cut moves for one layer.
    - Stepdown/ramp happens at overshoot start (pts[0]) => "step down in overshoot area".
    - All XY moves at cut depth are G1 at feed_xy (stepover speed unchanged).
    """
    start_x, start_y = pts[0]
    x1, y1 = pts[1]

    # Entry: ramp along first segment or plunge in place
    if ramp_len > 0:
        dx = x1 - start_x
        dy = y1 - start_y
        seg_len = (dx * dx + dy * dy) ** 0.5
        use_ramp = clamp(ramp_len, 0.0, seg_len)

        if use_ramp <= 1e-9:
            g.append(f"G1 Z{fmt3(target_z)} F{feed_z:.1f}")
            g.append(f"F{feed_xy:.1f}")
            g.append(f"G1 X{fmt3(x1)} Y{fmt3(y1)}")
        else:
            t = use_ramp / seg_len if seg_len > 0 else 0.0
            xr = start_x + dx * t
            yr = start_y + dy * t

            g.append(
                f"G1 X{fmt3(xr)} Y{fmt3(yr)} Z{fmt3(target_z)} F{feed_z:.1f}"
            )
            g.append(f"F{feed_xy:.1f}")

            if use_ramp < seg_len - 1e-9:
                g.append(f"G1 X{fmt3(x1)} Y{fmt3(y1)}")
    else:
        g.append(f"G1 Z{fmt3(target_z)} F{feed_z:.1f}")
        g.append(f"F{feed_xy:.1f}")
        g.append(f"G1 X{fmt3(x1)} Y{fmt3(y1)}")

    # Remaining path: all G1 at feed_xy
    for (x, y) in pts[2:]:
        g.append(f"G1 X{fmt3(x)} Y{fmt3(y)}")


def main():
    print("=== GRBL Surfacing Toolpath Generator ===")
    x_len = ask_float("What is the X-axis length (mm): ")
    y_len = ask_float("What is the Y-axis length (mm): ")

    total_depth_pos = ask_float("What is the TOTAL Z depth from stock top (mm, positive): ")
    total_depth = abs(total_depth_pos)

    travel_axis = ask_axis("What axis do you want the travel to be (X or Y): ")
    bit_diam = ask_float("What Diameter bit is used (mm): ")
    stepover = 0.5 * bit_diam

    # Overshoot lengths are user-defined (X and Y independently)
    overshoot_x = ask_float("Overshoot length in X (mm): ", allow_zero=True, min_value=0.0)
    overshoot_y = ask_float("Overshoot length in Y (mm): ", allow_zero=True, min_value=0.0)

    ramp_len = ask_float(
        "Ramp length along first move (mm, 0 disables): ",
        allow_zero=True,
        min_value=0.0,
        default=0,
    )

    feed_xy = ask_float("Travel/Cut feed rate XY (mm/min): ", default=800)
    feed_z = ask_float("Plunge/Ramp feed (mm/min): ", default=300)
    safe_z = ask_float("Safe Z above stock top (mm): ", default=5)
    spindle_rpm = ask_float("Spindle RPM (0 to omit M3/M5): ", allow_zero=True, default=12000)

    layers = parse_depth_schedule(total_depth)

    pts, num_lines = build_raster_points(
        x_len=x_len,
        y_len=y_len,
        travel_axis=travel_axis,
        stepover=stepover,
        overshoot_x=overshoot_x,
        overshoot_y=overshoot_y,
    )

    start_x, start_y = pts[0]
    feed_xy_last = (2.0 / 3.0) * feed_xy

    g = []
    g.append("(GRBL surfacing raster - user Z steps; stepdown in overshoot; last layer 2/3 feed)")
    g.append("(Z=0 is stock top; cuts are at negative Z)")
    g.append(
        f"(Nominal X={{x_len}}mm Y={{y_len}}mm  OvershootX={{overshoot_x}}mm OvershootY={{overshoot_y}}mm)"
    )
    g.append(
        f"(TotalDepth={{total_depth}}mm  Travel={{travel_axis}}  Bit={{bit_diam}}mm Stepover={{stepover}}mm)"
    )
    g.append(f"(Lines/layer={{num_lines}} Layers={{len(layers)}} RampLen={{ramp_len}}mm)")
    g.append("G90 (absolute)")
    g.append("G21 (mm)")
    g.append("G17 (XY plane)")
    g.append("G94 (feed/min)")
    g.append("")

    if spindle_rpm > 0:
        g.append(f"M3 S{{int(round(spindle_rpm)}}")
        g.append("G4 P1")
        g.append("")

    # Move into overshoot zone first at safe Z
    g.append(f"G0 Z{{fmt3(safe_z)}}")
    g.append(f"G0 X{{fmt3(start_x)}} Y{{fmt3(start_y)}}")
    g.append("")

    for idx, target_z in enumerate(layers):
        is_last = idx == (len(layers) - 1)
        layer_feed_xy = feed_xy_last if is_last else feed_xy

        g.append(f"(--- Layer {{idx+1}}/{{len(layers)}} at Z{{fmt3(target_z)}} ---)")
        if is_last:
            g.append(f"(Last layer XY feed = 2/3: {{layer_feed_xy:.1f}})")

        g.append(f"G0 Z{{fmt3(safe_z)}}")
        g.append(f"G0 X{{fmt3(start_x)}} Y{{fmt3(start_y)}}")

        emit_layer(g, pts, target_z=target_z, feed_xy=layer_feed_xy, feed_z=feed_z, ramp_len=ramp_len)
        g.append("")

    g.append(f"G0 Z{{fmt3(safe_z)}}")
    if spindle_rpm > 0:
        g.append("M5")
    g.append("M30")

    out = "\n".join(g)

    print("\n=== G-code Output ===")
    print(out)

    save = input("\nSave to file? (y/n): ").strip().lower()
    if save == "y":
        fn = input("Filename [default surfacing_grbl.nc]: ").strip() or "surfacing_grbl.nc"
        with open(fn, "w", encoding="utf-8") as f:
            f.write(out)
            f.write("\n")
        print(f"Saved: {{fn}}")


if __name__ == "__main__":
    main()