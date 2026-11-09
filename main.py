# main.py

import json
from utilities.verification_paths import verif_path, set_verification_root, get_verification_root
from pathlib import Path
import numpy as np
import globals as pg
from setup_environment import setup_paths
from utilities.flight_profile_utils import get_flight_profile
from utilities.ini_parser import ini2dict, ini_int
from utilities.io import PANAM_SQAT_data_conversion
from utilities.create_results_folder import create_auralization_results_folder
from utilities.prepare_input_SQ import prepare_input_SQ
from utilities.interpolate_panam_input import interpolate_panam_input
from auralization.master_auralization_engine_airframe import master_auralization_engine_airframe

# Figure keys accepted in the `figures` argument / --figures CLI option
FIGURE_KEYS = [
    "flight_profile",
    "trim_data",
    "tonal_fan",
    "tonal_buzzsaw",
    "broadband_engine",
    "broadband_airframe",
    "engine_spectrogram",
    "overall_spectrogram",
    "propagation_rays",
    "propagation_tf",
    "propagated_spectrogram",
    "binaural",
]

FIGURE_FORMAT_KEYS = ["png", "pdf"]

# Insert one interpolated sample between each pair of PANAM samples, halving the time step (e.g. 0.125 s -> 0.0625 s).
# True = interpolate, False = PANAM samples only. The GUI checkbox and --[no-]interpolate-panam override this value.
INTERPOLATE_PANAM = False

def auralization_main(main_input_path_in, tag=None, input_file_path=None, results_path=None,
                      figures=None, save_figs=True, source_file_path=None, flight_profile_file_path=None,
                      figure_formats=None, verification=False, verification_dir=None, interpolate_panam=None):
    """
    figures: None -> plot all figures (previous behavior);
             otherwise an iterable of FIGURE_KEYS entries selecting which figures to produce.
    source_file_path: path to the sound source .dat file (defaults to auralization_input.dat in main_input_path_in).
    flight_profile_file_path: path to the flight profile .dat file (defaults to geschw_hoehe_verlauf.dat in main_input_path_in).
    figure_formats: None -> save both png and pdf (previous behavior);
             otherwise an iterable of FIGURE_FORMAT_KEYS entries selecting which file formats to write.
    verification: when True, every pipeline step dumps its plot vectors to <verification_dir>/<step>/*_python.npz
    verification_dir: root folder for the dumps (default: verification/). Use e.g. verification/scenarios/<name>
             (and prints [VERIFICATION] logs). Default False -> no .npz files are written.
    interpolate_panam: True/False to interpolate or not; None -> INTERPOLATE_PANAM, except for verification runs,
             which stay off because the MATLAB reference data has no interpolated samples.
    """
    setup_paths()

    if interpolate_panam is None:
        interpolate_panam = INTERPOLATE_PANAM and not verification

    if figures is None:
        figures = set(FIGURE_KEYS)
    else:
        figures = set(figures)
        unknown = figures - set(FIGURE_KEYS)
        if unknown:
            raise ValueError(f"Unknown figure keys: {sorted(unknown)}. Valid keys: {FIGURE_KEYS}")

    if figure_formats is None:
        figure_formats = set(FIGURE_FORMAT_KEYS)
    else:
        figure_formats = set(figure_formats)
        unknown = figure_formats - set(FIGURE_FORMAT_KEYS)
        if unknown:
            raise ValueError(f"Unknown figure format(s): {sorted(unknown)}. Valid keys: {FIGURE_FORMAT_KEYS}")

    main_input_path = Path(main_input_path_in)
    if tag is None:
        tag = "auralization_results"

    if input_file_path is None:
        ini_files = list(main_input_path.glob("*.ini"))
        if len(ini_files) == 0:
            raise FileNotFoundError(f"No .ini file found in {main_input_path}")
        elif len(ini_files) > 1:
            raise RuntimeError(f"Multiple .ini files found in import utilities.ini_parser{main_input_path}. Specify one explicitly.")
        input_file_path = ini_files[0]

        print(f"You forgot to provide an input .ini file. Using: {input_file_path}")

    input_file = ini2dict(input_file_path)

    # === Set globals ===
    from globals import __dict__ as g  # Import globals dictionary
    g['input_file'] = input_file
    g['fs'] = ini_int(input_file, "sampling_freq", 48000)
    g['panam_upsampling'] = 2 if interpolate_panam else 1
    g['save_mat_fig'] = False  # Or True, if needed
    g['figure_formats'] = figure_formats
    g['verification'] = verification
    if verification:
        set_verification_root(verification_dir)
        root = get_verification_root()
        root.mkdir(parents=True, exist_ok=True)
        # Parsed ini parameters, so the MATLAB side can be checked for identical inputs
        (root / "scenario_params_python.json").write_text(
            json.dumps({"ini_file": str(input_file_path), **{k: str(v) for k, v in input_file.items()}}, indent=2),
            encoding="utf-8")

    show_flight_profile = "flight_profile" in figures
    flight_profile_save_fig = save_figs and show_flight_profile

    # Step 1: Load sound source data
    source_file = Path(source_file_path) if source_file_path else main_input_path / "auralization_input.dat"
    source_data, source_OASPL, source_OASPL_dBA, source_SPECTROGRAM, source_SPECTROGRAM_dBA = PANAM_SQAT_data_conversion(source_file)

    for index, row in enumerate(source_data):
        print(f"Row {index}: {row}")
    nReceiver = len(source_data[0])  # number of observers


    # Step 2: Create results folder
    if results_path is None:
        results_path = main_input_path
    results_folder = create_auralization_results_folder(results_path, nReceiver)


    # Step 3: Load flight profile
    flight_profile_file = Path(flight_profile_file_path) if flight_profile_file_path else main_input_path / "geschw_hoehe_verlauf.dat"
    flight_procedure = 2  # 0: approach, 1: departure, 2: flyover
    flight_profile = get_flight_profile(
        flight_profile_file,
        show=show_flight_profile,
        procedure=flight_procedure,
        save_figs=flight_profile_save_fig,
        tag=tag,
        output_dir=results_folder["main_folder"]
    )

    # Verification: flight-profile vectors that feed the flight_profile figure
    if verification:
        verif_dir = verif_path("flight_profile")
        np.savez(verif_dir / "flight_profile_python.npz",
                 x=np.asarray(flight_profile["x"], dtype=float),
                 y=np.asarray(flight_profile["y"], dtype=float),
                 z=np.asarray(flight_profile["z"], dtype=float),
                 TAS=np.asarray(flight_profile["TAS"], dtype=float),
                 thrust=np.asarray(flight_profile["thrust"], dtype=float))
        print(f"[VERIFICATION] Saved flight-profile vectors to {verif_dir}/flight_profile_python.npz")

    # Step 4: Trim and synthesize for each receiver

    trim_time = float(input_file.get("trim_time", 20))  # fallback to 20 if not set

    # Optional smoothing (default = 0)
    smoothings_emission_based = ini_int(input_file, "smoothings_emission_based", 0)

    input_type = "emission"

    for i in range(nReceiver):
        if verification and nReceiver > 1:
            # one set of dumps per receiver; the ini parameters and flight profile above stay in the scenario folder
            set_verification_root(root / f"Receiver_{i+1}")

        tag_receiver = str(results_folder["receiver_folders"][i] / f"{tag}_Receiver_{i+1}")
        # Empty tag disables figure saving; the output .wav files are always saved (wav_path)
        tag_auralization = tag_receiver if save_figs else ""

        # Trim-data figures are produced (and saved) only when a tag is passed down
        tag_trim = tag_auralization if "trim_data" in figures else ""
        source_data_trimmed, source_SPECTROGRAM_trimmed, source_SPECTROGRAM_dBA_trimmed, flight_profile_trimmed = \
            prepare_input_SQ(
                source_data=[row[i] for row in source_data],
                spectrogram=source_SPECTROGRAM[i],
                spectrogram_dBA=source_SPECTROGRAM_dBA[i],
                flight_profile=flight_profile,
                trim_time=trim_time,
                tag=tag_trim
            )
        
        if verification:
            trimmed_path = verif_path("Prepare_input_SQ") / "python_trimmed_output.npz"
            np.savez(trimmed_path,
             source_data_trimmed=source_data_trimmed,
             source_SPECTROGRAM_trimmed=source_SPECTROGRAM_trimmed,
             source_SPECTROGRAM_dBA_trimmed=source_SPECTROGRAM_dBA_trimmed,
             flight_profile_trimmed=flight_profile_trimmed)
            print(f"[VERIFICATION] Saved trimmed-input vectors to {trimmed_path}")

        if g['panam_upsampling'] == 2:
            source_data_trimmed, flight_profile_trimmed = interpolate_panam_input(source_data_trimmed, flight_profile_trimmed)

        master_auralization_engine_airframe(
            input_data=source_data_trimmed,
            flight_profile=flight_profile_trimmed,
            smoothing=smoothings_emission_based,
            input_type=input_type,
            tag_auralization=tag_auralization,
            show={key: (key in figures) for key in FIGURE_KEYS},
            wav_path=tag_receiver,
        )


    return {
        "input_file": input_file,
        "nReceiver": nReceiver,
        "flight_profile": flight_profile,
        "source_data": source_data,
        "results_folder": results_folder
    }

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Aircraft noise auralization toolbox")
    parser.add_argument("--input-dir", default="input_data",
                        help="Folder containing auralization_input.dat, geschw_hoehe_verlauf.dat and the .ini file")
    parser.add_argument("--ini", default=None,
                        help="Path to the input .ini file (defaults to the single .ini in --input-dir)")
    parser.add_argument("--source-file", default=None,
                        help="Path to the sound source .dat file (defaults to auralization_input.dat in --input-dir)")
    parser.add_argument("--flight-profile-file", default=None,
                        help="Path to the flight profile .dat file (defaults to geschw_hoehe_verlauf.dat in --input-dir)")
    parser.add_argument("--tag", default=None, help="Tag used for the results folder and figure filenames")
    parser.add_argument("--results", default=None, help="Folder in which to create the results folder")
    parser.add_argument("--figures", default=None,
                        help=f"Comma-separated list of figures to plot (default: all). Keys: {','.join(FIGURE_KEYS)}. "
                             "Use 'none' to disable all figures.")
    parser.add_argument("--no-save-figs", action="store_true", help="Do not save figures to disk")
    parser.add_argument("--verification", action="store_true",
                        help="Dump per-step verification vectors to verification/<step>/*_python.npz "
                             "and print [VERIFICATION] logs (off by default)")
    parser.add_argument("--verification-dir", default=None,
                        help="Root folder for --verification dumps (default: verification/). "
                             "run_scenarios.py uses verification/scenarios/<scenario>")
    parser.add_argument("--figure-formats", default=None,
                        help=f"Comma-separated list of file formats to write for saved figures "
                             f"(default: both). Keys: {','.join(FIGURE_FORMAT_KEYS)}.")
    parser.add_argument("--interpolate-panam", action=argparse.BooleanOptionalAction, default=None,
                        help="Insert one interpolated sample between each pair of PANAM samples "
                             "(default: INTERPOLATE_PANAM in main.py)")
    args = parser.parse_args()

    if args.figures is None:
        figures = None
    elif args.figures.strip().lower() == "none":
        figures = set()
    else:
        figures = {f.strip() for f in args.figures.split(",") if f.strip()}

    if args.figure_formats is None:
        figure_formats = None
    else:
        figure_formats = {f.strip() for f in args.figure_formats.split(",") if f.strip()}

    auralization_main(
        args.input_dir,
        tag=args.tag,
        input_file_path=args.ini,
        results_path=args.results,
        figures=figures,
        save_figs=not args.no_save_figs,
        source_file_path=args.source_file,
        flight_profile_file_path=args.flight_profile_file,
        figure_formats=figure_formats,
        verification=args.verification,
        verification_dir=args.verification_dir,
        interpolate_panam=args.interpolate_panam,
    )