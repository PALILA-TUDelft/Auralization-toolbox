#utilities/mhdrload.py

# Translated to Python by Ricardo Rocha
# Original author: Jeff Daniels (MATLAB version), Gil Greco integration

from pathlib import Path
import numpy as np

def mhdrload(filepath):
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    header_blocks = []
    data_blocks = []

    # Try UTF-8 first, fallback to Latin-1 if it fails
    try:
        with open(filepath, "r", encoding="utf-8") as file:
            lines = file.readlines()
    except UnicodeDecodeError:
        with open(filepath, "r", encoding="latin-1") as file:
            lines = file.readlines()


    current_header = []
    current_data = []
    reading_data = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        try:
            # Try parsing numbers from the line
            numeric = [float(x) for x in stripped.split()]
            if not reading_data:
                header_blocks.append(current_header)
                current_header = []
                reading_data = True
            current_data.append(numeric)
        except ValueError:
            if reading_data:
                # Save completed data block
                data_blocks.append(np.array(current_data))
                current_data = []
                reading_data = False
            current_header.append(stripped)

    if current_data:
        data_blocks.append(np.array(current_data))

    if current_header:
        header_blocks.append(current_header)

    # Convert to uniform shapes
    max_lines = max(len(h) for h in header_blocks)
    max_cols = max(len(line) for header in header_blocks for line in header)

    header_mat = np.full((max_lines, max_cols, len(header_blocks)), ' ', dtype='<U100')
    for j, header in enumerate(header_blocks):
        for i, line in enumerate(header):
            header_mat[i, :len(line), j] = list(line)

    max_rows = max(d.shape[0] for d in data_blocks)
    max_cols = max(d.shape[1] if d.ndim > 1 else 1 for d in data_blocks)

    data_mat = np.zeros((max_rows, max_cols, len(data_blocks)))
    for j, d in enumerate(data_blocks):
        if d.ndim == 1:
            data_mat[:len(d), 0, j] = d
        else:
            rows, cols = d.shape
            data_mat[:rows, :cols, j] = d

    return header_mat, data_mat