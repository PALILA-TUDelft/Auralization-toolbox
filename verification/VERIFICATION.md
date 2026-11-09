# Verification

This folder checks that the Python toolbox gives the same results as the original MATLAB toolbox. Both sides run the same scenarios, save their intermediate results, and a script compares them step by step.

The list of what must be saved and compared for each step lives in [`manifest.py`](manifest.py). It is the single source of truth.

## How it works

Each scenario is one `.ini` file in `input_data/scenarios/` (identical in both toolboxes). Every pipeline step saves its data to one folder per scenario:

```
verification/scenarios/<scenario>/
    <step>/<step>_python.npz     saved by Python (--verification)
    <step>/<step>_matlab.mat     saved by MATLAB (run_all_scenarios.m)
    grade_report.txt             the comparison result
    run_python.log               the Python run log
```

Nothing is saved unless verification is switched on.

## Scenarios

| # | Name | What it tests |
|---|------|---------------|
| 0 | `base_case_grass_binaural90` | the default input file: 15 °C, grass, binaural |
| 1 | `isa_asphalt_mono` | ISA atmosphere, reflective ground |
| 2 | `hot_dry_snow_binaural180` | hot and dry air, soft ground, head turned 180° |
| 3 | `cold_humid_directonly` | no ground reflection |
| 4 | `concrete_44k1_attenuation` | 44.1 kHz sampling and `attenuation_db = -10` |
| 5 | `isa_forest_binaural90` | forest ground, longer trim window |
| 6 | `isa_log_wind_binaural` | logarithmic wind |
| 7 | `constant_wind_diagonal_mono` | constant wind, 10 m/s along `[1 1 0]` |
| 8 | `bbn_smoothing2_mono` | broadband smoothing (`smoothings_emission_based = 2`) |
| 9 | `three_receivers_binaural90` | three receivers (under the track, sideline, further along the track and higher), with its own source data |
| 10 | `two_receivers_binaural90` | exactly two receivers (under the track, further along the track and higher), with its own source data |

Scenario 0 is a copy of `input_data/input_file_auralization.ini`. `run_scenarios.py` warns if the two ever differ.

## Running it

1. **MATLAB** (in the MATLAB toolbox folder): `run_all_scenarios`, or `run_all_scenarios({'6','7'})` for some scenarios.
2. **Python** (in this repository's root): `python verification/run_scenarios.py`, or `--only 6 7` for some scenarios.

The Python script runs the scenarios, checks that both sides saved everything, and grades the comparison. Use `--skip-run` to only check and grade dumps that already exist.

Smaller pieces:

- `python verification/check_scenario_complete.py <scenario>`: only checks that everything was saved.
- `python verification/run_all_verifications.py --root verification/scenarios/<scenario>`: only grades.
- `python verification/test_python_port_fixes.py`: quick tests of MATLAB-specific details (time vectors, smoothing, index conventions).

## Comparing figures

`python verification/run_scenarios.py --figures all` also saves the Python figures, in the same layout and with the same file names as MATLAB. Then run `python verification/compare_plots.py` to get side-by-side HTML pages (MATLAB on the left, Python on the right) in `verification/plot_comparison/`. Point it to the MATLAB results with `--matlab-results` or the `MATLAB_RESULTS_DIR` environment variable.

The figures are styled to look like MATLAB's (same size, fonts and colours). Set `AURALIZATION_MATLAB_STYLE=0` to turn this off. The figure content itself is not identical, because the random phases differ.

## How results are graded

Each check gives one of:

- **PASS** and **FAIL**
- **SKIP**: a file or variable is missing on one side
- **N/A**: the check does not apply to this scenario (for example, binaural checks in a mono scenario)

What counts as a match depends on the data:

- **Deterministic data** (time axes, angles, distances, HRIRs) must match closely.
- **Synthesized audio** uses random phases, so Python and MATLAB can never match sample by sample. It is graded on level and spectrum instead.
- **Impulse responses** are graded on relative error.

## Good to know

- With several receivers, each receiver has its own folder of dumps and its own report, in `verification/scenarios/<scenario>/Receiver_<n>/`.
- A scenario with a folder `input_data/scenario_inputs/<scenario>/` reads its source data from there instead of `input_data/`. Only scenarios 9 and 10 do. Their data is synthetic, derived from the one-receiver file by `generate_multi_receiver_input.py`, because no PANAM output with several receivers is available. Before running them in MATLAB, apply changes 3 to 5 in [`matlab_patch/MATLAB_CHANGES.md`](matlab_patch/MATLAB_CHANGES.md).
- Wind only affects the ray tracing (paths, travel times, angles). Neither toolbox has wind terms in the transfer function or the Doppler shift.
- Scenario 8 compares the spectrum after smoothing. A single wrong index inside the smoothing loop would be too small to show up there, so it is covered by a unit test in `test_python_port_fixes.py`.

