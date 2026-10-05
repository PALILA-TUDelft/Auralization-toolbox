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
        pp         -- (nBins, nBlocks), pressure amplitudes for each frequency bin (post-smoothing)
        pp_equal   -- (nBins, nBlocks), pressure amplitudes before spectral smoothing (equal distribution)
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
    # fM must be (n_blocks, n_bands) here, i.e. the input fM was (n_bands, n_blocks); this used to be guessed from
    # the shapes, which silently transposed the wrong way for inputs with fewer blocks than bands.
    if fM.shape != pM.T.shape:
        raise ValueError(f"convert_freq_bands: fM must have shape (n_bands, n_blocks) = {pM.shape}, "
                         f"got {fM.T.shape}")


    for tt in range(min(len(t), fM.shape[0])):
        fL = np.concatenate([(fM[tt, :] / G**(1 / (2 * b))).reshape(-1),
                            [fM[tt, -1] * G**(1 / (2 * b))]])

        n = np.diff(fL) / df

        max_bands = pM.shape[0]          # all bands (MATLAB: i = 1:size(fM,1)); pM is (n_bands, n_blocks)
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
                if fMs[i] > fL[min(5 * j - 1, len(fL) - 1)]:      # MATLAB: fL(tt, 5*j), 1-based
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
        pp_equal = np.vstack((p_equal, padding))
    else:
        pp = p[:len(ff), :]
        pp_equal = p_equal[:len(ff), :]

    return pp, pp_equal
