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

    print("Environment setup completed.")

if __name__ == "__main__":
    setup_paths()