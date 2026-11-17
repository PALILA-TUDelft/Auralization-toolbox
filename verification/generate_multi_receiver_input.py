"""Generate the source data of the multi-receiver verification scenarios (scenarios 9 and 10).

No PANAM output with several observers is available, so the file is derived from the single-receiver
input_data/auralization_input.dat. The same file goes to both toolboxes, so it only has to be plausible, not a PANAM
prediction. For every receiver the file repeats all time steps, one receiver after the other (the PANAM layout both
parsers expect):
  - Receiver 1 is a verbatim copy of the original receiver.
  - The other receivers keep the time steps, source positions and engine state (source_time, xpos, ypos, alt, n1, ...).
    dist, distxy, retarded time, phix and phiy are recomputed for the new position; phix keeps the body-angle offset
    of the original data at that time step.
  - Their spectra are the original spectra at the time step with the nearest emission angle phix, because the
    levels in the file are emission levels (directivity) and the frequencies include the Doppler shift of that angle.

Output (also read by MATLAB, see VERIFICATION.md):
    input_data/scenario_inputs/<scenario>/auralization_input.dat
    input_data/scenario_inputs/<scenario>/geschw_hoehe_verlauf.dat

Usage:
    python verification/generate_multi_receiver_input.py
"""
import re
import shutil
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
INPUT_DIR = REPO / "input_data"

# [x, y, z] in metres. The flight track runs along +x at y = 0.
UNDER_TRACK = (0.0, 0.0, 1.2)          # the original receiver
SIDELINE = (0.0, 350.0, 1.2)
ALONG_TRACK = (400.0, -200.0, 4.0)     # further along the track, on the other side, higher (shifts the trim window)

SCENARIOS = {
    "scenario_9_three_receivers_binaural90": [UNDER_TRACK, SIDELINE, ALONG_TRACK],
    "scenario_10_two_receivers_binaural90": [UNDER_TRACK, ALONG_TRACK],
}

SEPARATOR = "#" * 42
FIELDS = ["retarded time", "source time", "speed of sound", "xpos", "ypos", "alt", "xobs", "yobs", "zobs",
          "phix", "phiy", "dist", "distxy", "vel", "n1"]


def split_steps(lines):
    """[(header lines, zone lines)] per time step; lines[:2] is the file title, the rest is one block per step."""
    marks = [i for i, line in enumerate(lines) if line == SEPARATOR]
    starts, ends = marks[::2], marks[1::2]
    next_starts = starts[1:] + [len(lines)]
    return [(lines[a + 1:b], lines[b + 1:c]) for a, b, c in zip(starts, ends, next_starts)]


def header_value(header, field):
    line = header[FIELDS.index(field)]
    return float(line.rsplit("=", 1)[1])


def set_header_value(header, field, value):
    i = FIELDS.index(field)
    header[i] = f"{header[i].rsplit('=', 1)[0]}={value:12.4f}"


def polar_angle(x, y, alt, receiver):
    dx, dy, dz = receiver[0] - x, receiver[1] - y, receiver[2] - alt
    return np.degrees(np.arccos(dx / np.sqrt(dx ** 2 + dy ** 2 + dz ** 2)))


def receiver_steps(steps, receiver):
    """The (header, zone lines) of all time steps for one new receiver position."""
    table = {f: np.array([header_value(h, f) for h, _ in steps]) for f in FIELDS}
    x, y, alt = table["xpos"], table["ypos"], table["alt"]
    original = (table["xobs"][0], table["yobs"][0], table["zobs"][0])

    phix = polar_angle(x, y, alt, receiver) + (table["phix"] - polar_angle(x, y, alt, original))
    phiy = np.degrees(np.arctan2(receiver[1] - y, alt - receiver[2]))
    dist_xy = np.hypot(receiver[0] - x, receiver[1] - y)
    dist = np.hypot(dist_xy, receiver[2] - alt)
    retarded = table["source time"] + dist / table["speed of sound"]

    out = []
    for i, (header, _) in enumerate(steps):
        header = list(header)
        new_values = {"retarded time": retarded[i], "xobs": receiver[0], "yobs": receiver[1], "zobs": receiver[2],
                      "phix": phix[i], "phiy": phiy[i], "dist": dist[i], "distxy": dist_xy[i]}
        for field, value in new_values.items():
            set_header_value(header, field, value)
        nearest = int(np.argmin(np.abs(table["phix"] - phix[i])))
        zones = [re.sub(r"time=\s*[\d.]+", f"time={retarded[i]:12.2f}", line) if line.startswith("ZONE") else line
                 for line in steps[nearest][1]]
        out.append((header, zones))
    return out


def main():
    source = INPUT_DIR / "auralization_input.dat"
    with open(source, encoding="ascii", newline="") as fh:
        text = fh.read()
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    steps = split_steps(lines)

    for scenario, receivers in SCENARIOS.items():
        out = lines[:2]
        for receiver in receivers:
            is_original = receiver == (header_value(steps[0][0], "xobs"), header_value(steps[0][0], "yobs"),
                                       header_value(steps[0][0], "zobs"))
            for header, zones in (steps if is_original else receiver_steps(steps, receiver)):
                out += [SEPARATOR, *header, SEPARATOR, *zones]

        target = INPUT_DIR / "scenario_inputs" / scenario
        target.mkdir(parents=True, exist_ok=True)
        # the last block of the original ends with the file's final (empty) line: keep it only at the end of the new file
        body = [line for line in out if line != ""]
        with open(target / "auralization_input.dat", "w", encoding="ascii", newline="") as fh:
            fh.write(newline.join(body) + (newline if text.endswith(newline) else ""))
        shutil.copyfile(INPUT_DIR / "geschw_hoehe_verlauf.dat", target / "geschw_hoehe_verlauf.dat")

        print(f"Written: {target}")
        print(f"{len(receivers)} receivers x {len(steps)} time steps")


if __name__ == "__main__":
    main()
