#auralization/private/convert_freq_bands.py
import numpy as np
import globals

def convert_freq_bands(pMspl, fM, df, t, block_len, smoothing):
    """
    Converts third-octave band SPL data into narrowband pressure amplitudes over time.

    Parameters:
        pMspl      -- shape (nBlocks, nBands) in dB
        fM         -- shape (nBands, nBlocks), center frequencies of 1/3-oct bands
        df         -- float, desired frequency resolution
        t          -- time vector [s]
        block_len  -- int, block length in samples
        smoothing  -- int, number of smoothing iterations

    Returns:
        pp         -- (nBins, nBlocks), pressure amplitudes for each frequency bin
    """
    fs = globals.fs
    pref = globals.pref

    # Enforce MATLAB-like shapes: pM and fM should be (nBands, nTimeSteps)
    pM = pref**2 * 10**(pMspl.T / 10)
    fM = fM.T

    f = np.linspace(0, fs / 2, block_len // 2 + 1)

    p = np.zeros((len(f), len(t)))
    p_equal = np.zeros_like(p)

    b = 3  # 1/3-octave
    G = 10**(3 / 10)
    # No transpose needed if fM is already [time, bands]
    fM = fM.T if fM.shape[0] < fM.shape[1] else fM


    for tt in range(min(len(t), fM.shape[0])):
        fL = np.concatenate([(fM[tt, :] / G**(1 / (2 * b))).reshape(-1),
                            [fM[tt, -1] * G**(1 / (2 * b))]])

        n = np.diff(fL) / df

        max_bands = min(pM.shape[1], len(n), fM.shape[1])
        for i in range(max_bands):
            if n[i] > 0:
                idx = (f >= fL[i]) & (f <= fL[i + 1])
                p[idx, tt] = np.sqrt(pM[i, tt] / n[i]) * np.sqrt(2)




        p_equal[:, tt] = p[:, tt].copy()
        fMs = fM[tt, :].copy()

        for j in range(1, smoothing + 1):
            for i in range(len(fMs) - 1):
                idx = (f > fMs[i] * G**(1 / (4**j * b))) & (f < fMs[i + 1] / G**(1 / (4**j * b)))
                if np.any(idx):
                    p[idx, tt] = np.mean(p[idx, tt])

            fMtmp = []
            for i in range(len(fMs)):
                if fMs[i] > fL[min(5 * j, len(fL) - 1)]:
                    fMtmp.extend([
                        fMs[i] / G**(3 / (2 * 4**j * b)),
                        fMs[i] / G**(1 / (2 * 4**j * b)),
                        fMs[i] * G**(1 / (2 * 4**j * b)),
                        fMs[i] * G**(3 / (2 * 4**j * b)),
                    ])
            fMs = np.array(fMtmp)

    ff = np.linspace(0, fs / 2, block_len // 2 + 1)
    if len(ff) > len(f):
        padding = np.zeros((len(ff) - len(f), len(t)))
        pp = np.vstack((p, padding))
    else:
        pp = p[:len(ff), :]

    return pp
