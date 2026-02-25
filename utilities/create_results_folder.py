#utilities/create_results_folder.py

from pathlib import Path

def create_auralization_results_folder(base_path, n_receivers):
    """
    Create results folders for each receiver under <base_path>/results_auralization.

    Parameters:
    - base_path (str or Path): Root directory where 'results_auralization' will be created.
    - n_receivers (int): Number of receivers (creates one subfolder per receiver).

    Returns:
    - dict with:
        - 'main_folder': Path to the main results folder.
        - 'receiver_folders': List of receiver-specific subfolder paths.
    """
    base_path = Path(base_path)
    main_folder = base_path / "results_auralization"
    main_folder.mkdir(parents=True, exist_ok=True)

    receiver_folders = []
    for i in range(1, n_receivers + 1):
        receiver_folder = main_folder / f"Receiver_{i}"
        receiver_folder.mkdir(parents=True, exist_ok=True)
        receiver_folders.append(receiver_folder)

    return {
        "main_folder": main_folder,
        "receiver_folders": receiver_folders
    }