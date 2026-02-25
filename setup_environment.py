# setup_environment.py

import sys
from pathlib import Path

def setup_paths(base_path=None):
    if base_path is None:
        base_path = Path(__file__).resolve().parent

    def add_path(path: Path):
        if path.exists() and path.is_dir():
            sys.path.append(str(path))
            print(f"Added to path: {path}")
        else:
            print(f"Path not found: {path}")

    # Core directories
    add_path(base_path)
    add_path(base_path / 'auralization')
    add_path(base_path / 'utilities')

    # Third-party dependencies
    third_party = base_path / 'third_party'
    add_path(third_party / 'ITA-Toolbox')
    add_path(third_party / 'ARTMatlab_v2023a')
    add_path(third_party / 'Faddeeva_MATLAB')
    add_path(third_party / 'AKtools')
    add_path(third_party / 'AKtools' / 'Plotting')
    add_path(third_party / 'AKtools' / 'Plotting' / 'cbrewer')
    add_path(third_party / 'FABIAN_HRTF_DATABASE_v4')

    print("Environment setup completed.")

if __name__ == "__main__":
    setup_paths()