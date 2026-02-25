# main.py

from pathlib import Path
import numpy as np
import globals as pg
from setup_environment import setup_paths
from utilities.flight_profile_utils import get_flight_profile
from utilities.ini_parser import ini2dict
from utilities.io import PANAM_SQAT_data_conversion
from utilities.create_results_folder import create_auralization_results_folder
from utilities.prepare_input_SQ import prepare_input_SQ
from auralization.master_auralization_engine_airframe import master_auralization_engine_airframe

def auralization_main(main_input_path_in, tag=None, input_file_path=None, results_path=None):
    setup_paths()

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
    g['fs'] = int(input_file.get("sampling_freq", 48000))
    g['save_mat_fig'] = False  # Or True, if needed

    save_mat_fig = False
    show_flight_profile = True
    flight_profile_save_fig = True
    show_auralization = True
    save_figs = True

    # Step 1: Load sound source data
    source_file = main_input_path / "auralization_input.dat"
    source_data, source_OASPL, source_OASPL_dBA, source_SPECTROGRAM, source_SPECTROGRAM_dBA = PANAM_SQAT_data_conversion(source_file)

    for index, row in enumerate(source_data):
        print(f"Row {index}: {row}")
    nReceiver = len(source_data[0])  # number of observers


    # Step 2: Create results folder
    if results_path is None:
        results_path = main_input_path
    results_folder = create_auralization_results_folder(results_path, nReceiver)


    # Step 3: Load flight profile
    flight_profile_file = main_input_path / "geschw_hoehe_verlauf.dat"
    flight_procedure = 2  # 0: approach, 1: departure, 2: flyover
    flight_profile = get_flight_profile(
        flight_profile_file,
        show=show_flight_profile,
        procedure=flight_procedure,
        save_figs=flight_profile_save_fig,
        tag=tag,
        output_dir=results_folder["main_folder"]
    )

    # Step 4: Trim and synthesize for each receiver

    trim_time = float(input_file.get("trim_time", 20))  # fallback to 20 if not set

    # Optional smoothing (default = 0)
    smoothings_emission_based = int(input_file.get("smoothings_emission_based", 0))

    input_type = "emission"

    for i in range(nReceiver):
        if save_figs:   
            tag_auralization = str(results_folder["receiver_folders"][i] / f"{tag}_Receiver_{i+1}")
        else:
            tag_auralization = ""

        source_data_trimmed, source_SPECTROGRAM_trimmed, source_SPECTROGRAM_dBA_trimmed, flight_profile_trimmed = \
            prepare_input_SQ(
                source_data=[row[i] for row in source_data],
                spectrogram=source_SPECTROGRAM[i],
                spectrogram_dBA=source_SPECTROGRAM_dBA[i],
                flight_profile=flight_profile,
                trim_time=trim_time,
                tag=tag_auralization
            )
        
        np.savez("verification/Prepare_input_SQ/python_trimmed_output.npz",
         source_data_trimmed=source_data_trimmed,
         source_SPECTROGRAM_trimmed=source_SPECTROGRAM_trimmed,
         source_SPECTROGRAM_dBA_trimmed=source_SPECTROGRAM_dBA_trimmed,
         flight_profile_trimmed=flight_profile_trimmed)

        master_auralization_engine_airframe(
            input_data=source_data_trimmed,
            flight_profile=flight_profile_trimmed,
            smoothing=smoothings_emission_based,
            input_type=input_type,
            tag_auralization=tag_auralization,
            show=show_auralization,
        )


    return {
        "input_file": input_file,
        "nReceiver": nReceiver,
        "flight_profile": flight_profile,
        "source_data": source_data,
        "results_folder": results_folder
    }

if __name__ == "__main__":
    auralization_main("input_data") 