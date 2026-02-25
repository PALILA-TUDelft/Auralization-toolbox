#utilities/plot_utils.py

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from mpl_toolkits.axes_grid1 import make_axes_locatable

def export_figures(filename, save_mat_fig=True, save_png=True, save_pdf=False, dpi=600):
    """
    Save current matplotlib figure with standardized format and resolution.

    Args:
        filename (str or Path): Base filename without extension.
        save_mat_fig (bool): If True, saves as a .pickle using plt.savefig.
        save_png (bool): If True, saves as .png.
        save_pdf (bool): If True, saves as .pdf.
        dpi (int): Dots per inch for PNG/PDF exports.
    """
    filename = Path(filename)
    results_dir = Path.cwd() / "results_auralization"
    results_dir.mkdir(parents=True, exist_ok=True)

    base_name = filename.stem
    target_path = results_dir / base_name

    print(f"[EXPORT] Saving to: {target_path}")

    # if save_mat_fig:
    #     plt.savefig(target_path.with_suffix(".fig.pickle"), format='pickle')
    if save_png:
        plt.savefig(target_path.with_suffix(".png"), format='png', dpi=dpi, bbox_inches='tight')
    if save_pdf:
        plt.savefig(target_path.with_suffix(".pdf"), format='pdf', dpi=dpi, bbox_inches='tight')

def plot_buzzsaw_panamsynthesis(freq_plot_panam, SPL_plot_panam, freq_synthesis, SPL_synthesis, f1, f2, source, tag_auralization):
    idx_plot_panam = (freq_plot_panam[:, np.newaxis] >= f1) & (freq_plot_panam[:, np.newaxis] <= f2) 
    idxx = np.where(np.sum(idx_plot_panam, axis=0) != 0)[0]

    if len(idxx) < len(SPL_plot_panam):
        return

    fig, ax = plt.subplots(figsize=(8, 6))
    color_panam = 'black'
    color_stem = '#7d2e8f'

    # Plot bars for PANAM prediction
    for i in range(len(SPL_plot_panam)):
        ax.plot([f1[idxx[i]], f2[idxx[i]]], [SPL_plot_panam[i]]*2, color=color_panam)
        ax.plot([f1[idxx[i]]]*2, [0, SPL_plot_panam[i]], color=color_panam)
        ax.plot([f2[idxx[i]]]*2, [0, SPL_plot_panam[i]], color=color_panam)

    # Plot synthesis with stem plot
    markerline, stemlines, baseline = ax.stem(freq_synthesis, SPL_synthesis, basefmt=" ", linefmt=color_stem, markerfmt='o')
    plt.setp(markerline, markersize=4)

    ax.set_xscale("log")
    ax.set_xlabel("Frequency, $f$ (Hz)", fontsize=12)
    ax.set_ylabel("SPL, $L_{\\mathrm{Z}}$ (dB re 20$~\\mu$Pa)", fontsize=12)
    ax.set_title("Buzzsaw Noise Synthesis at Overhead Position")
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    ax.legend(["PANAM", "Synthesis"])
    fig.tight_layout()

    if tag_auralization:
        filename = f"{tag_auralization}_synthesised_overhead_{source}"
        export_figures(filename, save_mat_fig=True, save_png=True, save_pdf=True)

    plt.close(fig)

def plot_spectrogram(signal, fs, title, tag_auralization, tag_save):

    # Ensure 2D shape: (samples, channels)
    signal = np.atleast_2d(signal)
    if signal.shape[0] < signal.shape[1]:
        signal = signal.T

    window_size = 1024
    overlap = 0.75
    pref = 20e-6  # SPL reference pressure

    fig, ax = plt.subplots(figsize=(10, 5))

    # Only plot first channel (can loop for stereo if needed)
    P, F, T = myspecgram(signal[:, 0], fs, window_size, overlap)
    SPL = 20 * np.log10(np.abs(P) / pref + 1e-12)

    vmin = 100 if np.max(SPL) > 110 else 0
    im = ax.imshow(SPL, extent=[T[0], T[-1], F[0]/1000, F[-1]/1000],
                   aspect='auto', origin='lower', cmap='jet',
                   norm=Normalize(vmin=vmin, vmax=np.max(SPL)))

    ax.set_xlim([T[0], T[-1]])
    ax.set_ylim([0, 15])  # kHz
    ax.set_xlabel("Time, $t$ (s)", fontsize=12)
    ax.set_ylabel("Frequency, $f$ (kHz)", fontsize=12)
    ax.set_title(title, fontsize=12, loc='center')

    # Add colorbar to the right
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="4%", pad=0.1)
    cb = fig.colorbar(im, cax=cax)
    cb.set_label('SPL, $L_{\\mathrm{Z}}$ (dB re 20$~\\mu$Pa)', fontsize=12)

    fig.tight_layout()

    # Save if tag is provided
    if tag_auralization:
        filename = f"{tag_auralization}{tag_save}"
        export_figures(filename, save_mat_fig=False, save_png=True, save_pdf=True)

    plt.show()


def myspecgram(signal, fs, nfft, overlap):
    signal = signal.flatten()
    samples = len(signal)

    # Pad if shorter than window
    if samples < nfft:
        signal = np.pad(signal, (0, nfft - samples), mode='constant')

    window = np.hanning(nfft)
    offset = int((1 - overlap) * nfft)
    num_segments = 1 + (len(signal) - nfft) // offset

    # Prepare output arrays
    fft_specgram = np.zeros((nfft//2 + 1, num_segments))
    for i in range(num_segments):
        start = i * offset
        segment = signal[start:start + nfft]
        windowed = segment * window
        fft_result = np.fft.fft(windowed) * 4 / nfft  # match MATLAB scaling
        fft_magnitude = np.abs(fft_result[:nfft//2 + 1])
        fft_specgram[:, i] = fft_magnitude

    freq_vector = np.linspace(0, fs/2, nfft//2 + 1)
    time_vector = (np.arange(num_segments) * offset + offset // 2) / fs  # center time

    return fft_specgram, freq_vector, time_vector