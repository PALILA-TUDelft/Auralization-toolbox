# auralization/private/save_wav.py
#
# Port of MATLAB save_wav.m
from __future__ import annotations
import numpy as np
from pathlib import Path
from scipy.io import wavfile


def save_wav(input_signal, fs, attenuation_db, file_tag, save_path):
    """
    Write .wav file with optional attenuation.

    Port of MATLAB save_wav.m

    Parameters
    ----------
    input_signal : array — signal in Pascal
    fs : int — sampling rate (Hz)
    attenuation_db : float — attenuation in dB (0 = no change, -10 = attenuate 10 dB)
    file_tag : str — suffix for the filename
    save_path : str — base path/tag for saving
    """
    if not save_path:
        return

    attenuation = 10.0 ** (attenuation_db / 20.0)
    output = np.asarray(input_signal, dtype=np.float32) * attenuation

    attenuation_tag = f"_FS{94 - attenuation_db:.0f}dBSPL"
    file_name = f"{save_path}{file_tag}{attenuation_tag}.wav"

    Path(file_name).parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(file_name, fs, output)
    print(f"[EXPORT] Saved wav: {file_name}")
