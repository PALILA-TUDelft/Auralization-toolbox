#utilities/plot_utils.py

import os
import warnings
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from mpl_toolkits.axes_grid1 import make_axes_locatable
import globals
from utilities.plot_style import MATLAB_COLORS, apply_matlab_style, color_yyaxis, latex_legend, style_figure

# MATLAB look for all figures; set the environment variable AURALIZATION_MATLAB_STYLE=0 (or globals.matlab_style = False
# before this import) to keep matplotlib's own look
if getattr(globals, "matlab_style", True) and os.environ.get("AURALIZATION_MATLAB_STYLE", "1") != "0":
    apply_matlab_style()


def show_figure():
    """plt.show() for interactive backends.

    With a non-interactive backend (Agg, e.g. MPLBACKEND=Agg in the verification chain) there is nothing to show and the
    figures have already been saved by export_figures, so they are closed quietly instead of triggering matplotlib's
    "FigureCanvasAgg is non-interactive, and thus cannot be shown" warning. This also frees the memory of the (600 dpi)
    figures, which pile up otherwise.
    """
    import matplotlib
    for num in plt.get_fignums():
        style_figure(plt.figure(num))
    # (matplotlib.rcsetup.non_interactive_bk no longer exists in recent matplotlib versions, hence the fixed list)
    if matplotlib.get_backend().lower() in ("agg", "cairo", "pdf", "pgf", "ps", "svg", "template"):
        plt.close("all")
    else:
        plt.show()

# Every MATLAB figure of the original toolbox is a default-size MATLAB figure (5.83 x 4.375 in) exported at 600 dpi:
# 3500 x 2625 px PNG, 420 x 315 pt PDF page. Python figures are saved on the same canvas so they can be compared 1:1.
MATLAB_FIGURE_SIZE_IN = (3500 / 600, 2625 / 600)


def _to_matlab_canvas(fig):
    """Put the figure on the MATLAB canvas and lay it out with constrained layout (tight_layout silently gives up when
    the labels do not fit on the small canvas, which clips them). Returns a function that restores the figure.

    Note: fig.tight_layout() leaves a *placeholder* layout engine on the figure, so "has a layout engine" does not
    mean "is constrained"."""
    from matplotlib.layout_engine import ConstrainedLayoutEngine
    own_size = tuple(fig.get_size_inches())
    was_constrained = isinstance(fig.get_layout_engine(), ConstrainedLayoutEngine)
    fig.set_size_inches(MATLAB_FIGURE_SIZE_IN[0], MATLAB_FIGURE_SIZE_IN[1], forward=True)
    if not was_constrained:
        fig.set_layout_engine("constrained")
    fig.get_layout_engine().set(w_pad=0.12, h_pad=0.12)        # inches of white space around the decorations

    def restore():
        fig.set_size_inches(own_size[0], own_size[1], forward=True)
        if not was_constrained:
            fig.set_layout_engine("none")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fig.tight_layout()
            except Exception:  # noqa: BLE001
                pass
    return restore


def export_figures(filename, save_mat_fig=True, save_png=True, save_pdf=False, dpi=600):
    """
    Save current matplotlib figure with standardized format and resolution.

    Args:
        filename (str or Path): Base filename without extension.
        save_mat_fig (bool): If True, saves as a .pickle using plt.savefig.
        save_png (bool): If True, saves as .png (also gated by globals.figure_formats).
        save_pdf (bool): If True, saves as .pdf (also gated by globals.figure_formats).
        dpi (int): Dots per inch for PNG/PDF exports.

    The figure is saved on the MATLAB canvas (MATLAB_FIGURE_SIZE_IN, exactly 3500 x 2625 px at 600 dpi) so that it can
    be compared with the MATLAB figure of the same name. Set ``globals.match_matlab_figure_size = False`` to keep the
    figure's own size and crop it to its content (bbox_inches='tight') instead. The figure is restored to its own
    size afterwards, so interactive windows are not affected.
    """
    filename = Path(filename)
    if filename.parent != Path("."):
        # Tag contains a folder (e.g. <results>/results_auralization/Receiver_1/...): save there
        results_dir = filename.parent
    else:
        results_dir = Path.cwd() / "results_auralization"
    results_dir.mkdir(parents=True, exist_ok=True)

    base_name = filename.stem
    target_path = results_dir / base_name

    print(f"[EXPORT] Saving to: {target_path}")

    enabled_formats = getattr(globals, "figure_formats", {"png", "pdf"})

    # if save_mat_fig:
    #     plt.savefig(target_path.with_suffix(".fig.pickle"), format='pickle')
    match_matlab = getattr(globals, "match_matlab_figure_size", True)
    fig = plt.gcf()
    style_figure(fig)
    if match_matlab:
        restore = _to_matlab_canvas(fig)
        save_kwargs = {}                                  # exact canvas size: no cropping
    else:
        save_kwargs = {"bbox_inches": "tight"}
    try:
        if save_png and "png" in enabled_formats:
            plt.savefig(target_path.with_suffix(".png"), format='png', dpi=dpi, **save_kwargs)
        if save_pdf and "pdf" in enabled_formats:
            plt.savefig(target_path.with_suffix(".pdf"), format='pdf', dpi=dpi, **save_kwargs)
    finally:
        if match_matlab:
            restore()

def plot_buzzsaw_panamsynthesis(freq_plot_panam, SPL_plot_panam, freq_synthesis, SPL_synthesis, f1, f2, source, tag_auralization):
    idx_plot_panam = (freq_plot_panam[:, np.newaxis] >= f1) & (freq_plot_panam[:, np.newaxis] <= f2) 
    idxx = np.where(np.sum(idx_plot_panam, axis=0) != 0)[0]

    if len(idxx) < len(SPL_plot_panam):
        return

    fig, ax = plt.subplots(figsize=(8, 6))
    _window_title(fig, "PROCESSING - Buzzsaw noise synthesis- overhead position")
    color_panam = 'black'
    color_stem = (0.49, 0.18, 0.56)

    # Plot bars for PANAM prediction
    panam_handle = None
    for i in range(len(SPL_plot_panam)):
        lines = ax.plot([f1[idxx[i]], f2[idxx[i]]], [SPL_plot_panam[i]]*2, color=color_panam)
        ax.plot([f1[idxx[i]]]*2, [0, SPL_plot_panam[i]], color=color_panam)
        ax.plot([f2[idxx[i]]]*2, [0, SPL_plot_panam[i]], color=color_panam)
        if panam_handle is None:
            panam_handle = lines[0]

    # Synthesis: stem plot, purple, '*' markers of size 4 (MATLAB: stem(..., 'Marker', '*', MarkerSize=4))
    markerline, stemlines, baseline = ax.stem(freq_synthesis, SPL_synthesis, basefmt=" ", linefmt=color_stem, markerfmt='*')
    plt.setp(markerline, marker=(6, 2, 0), markersize=4, color=color_stem, markeredgecolor=color_stem)
    plt.setp(stemlines, linewidth=0.5)

    ax.set_xscale("log")
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Frequency, $f$ (Hz)")
    ax.set_ylabel(r"SPL, $L_{\mathrm{Z}}$ (dB re 20$~\mu$Pa)")
    if panam_handle is not None:
        ax.legend(handles=[panam_handle, markerline], labels=["PANAM", "Synthesis"], loc="upper right")
    fig.tight_layout()

    if tag_auralization:
        filename = f"{tag_auralization}_synthesised_overhead_{source}"
        export_figures(filename, save_mat_fig=True, save_png=True, save_pdf=True)

    plt.close(fig)

def plot_doppler_theta_buzzsaw(theta_deg, doppler_ratio, tag_auralization):
    """
    Port of MATLAB "plot angle theta_doppler" block.
    theta_deg      -- emission angle theta, in degrees, per time bin
    doppler_ratio  -- doppler-shifted / base frequency ratio (f'/f0), per time bin
    """
    x = np.arange(len(theta_deg))

    fig, ax1 = plt.subplots(figsize=(9, 5))
    _window_title(fig, "PROCESSING - Buzzsaw noise synthesis - doppler effect")

    c1, c2 = MATLAB_COLORS[0], MATLAB_COLORS[1]
    a, = ax1.plot(x, theta_deg, color=c1)
    ax1.axhline(90, color=(0.15, 0.15, 0.15), linewidth=0.5)          # MATLAB: yline(90)
    ax1.set_ylim(0, 180)
    ax1.set_ylabel(r"$\theta$ (deg)")
    ax1.set_xlabel("Time, $t$ (bins)")

    ax2 = ax1.twinx()
    b, = ax2.plot(x, doppler_ratio, color=c2)
    ax2.set_ylim(0.5, 1.5)
    ax2.set_ylabel(r"Doppler-shift, $f^\prime/f_0$ (-)")
    color_yyaxis(ax1, ax2, c1, c2)

    latex_legend(ax1.legend([a, b], [r"$\theta$", r"$f^\prime/f_0$"], loc="lower right"))
    fig.tight_layout()

    if tag_auralization:
        filename = f"{tag_auralization}_Doppler_theta_buzzsaw"
        export_figures(filename, save_mat_fig=False, save_png=False, save_pdf=True)

    plt.close(fig)

def plot_bbn_toc_to_narrowband(freq_bands, SPL_bands, freq_narrowband, SPL_narrowband, source, df, tag_auralization):
    """
    Port of MATLAB ConvertFreqBands "plot spl vs freq (1/3-OB and NB for a time-step)" block.
    freq_bands/SPL_bands   -- 1/3-octave PANAM band centers/SPL at the middle time block
    freq_narrowband/SPL_narrowband -- equal-distribution narrowband spectrum at the first time block
    df -- frequency resolution (Hz) of the narrowband synthesis, shown in the legend
    """
    b = 3  # 1/3-octave
    G = 10 ** (3 / 10)
    f_lower = freq_bands / G ** (1 / (2 * b))
    f_upper = freq_bands * G ** (1 / (2 * b))

    fig, ax = plt.subplots(figsize=(8, 6))
    fig.canvas.manager.set_window_title("PROCESSING - BBN auralization: TOC to Narrowband conversion (1st block)")
    color_panam = 'black'
    color_narrowband = 'b'

    panam_handle = None
    for i in range(len(freq_bands)):
        lines = ax.semilogx([f_lower[i], f_upper[i]], [SPL_bands[i]] * 2, color=color_panam)
        ax.semilogx([f_lower[i]] * 2, [0, SPL_bands[i]], color=color_panam)
        ax.semilogx([f_upper[i]] * 2, [0, SPL_bands[i]], color=color_panam)
        if panam_handle is None:
            panam_handle = lines[0]

    # A handful of leading low-frequency bins can end up with no PANAM energy
    # assigned: some 1/3-OB bands below ~30 Hz are narrower than the df=10 Hz
    # FFT bin spacing, so by coincidence no bin lands inside that band's
    # window and its energy is silently dropped. Since SPL_narrowband is
    # computed as 20*log10(x/pref) with no epsilon (matching MATLAB's
    # p2spl exactly), those bins come out as -inf; mask them out here the
    # same way MATLAB's plotting naturally skips non-finite points.
    valid = np.isfinite(SPL_narrowband)
    narrowband_line, = ax.semilogx(freq_narrowband[valid], SPL_narrowband[valid], color=color_narrowband)

    ax.set_xlabel("Frequency, $f$ (Hz)")      # (the MATLAB label says kHz, but the axis is in Hz)
    ax.set_ylabel(r"SPL, $L_{\mathrm{p,Z}}$ (dB re 20$~\mu$Pa)")
    ax.set_xlim(20, 15000)
    ax.set_ylim(bottom=0)
    ax.grid(True, which="major")
    ax.grid(True, which="minor", axis="x", linestyle=":")       # MATLAB: grid on (log axis: dotted minor lines)
    if panam_handle is not None:
        latex_legend(ax.legend(handles=[panam_handle, narrowband_line],
                               labels=["input: 1/3-OB", f"Equal Distribution: $\\Delta f={df:.4g}$ Hz"],
                               loc="lower left"))
    fig.tight_layout()

    if tag_auralization:
        filename = f"{tag_auralization}_BBN_TOC_to_narrowband_{source}"
        export_figures(filename, save_mat_fig=False, save_png=True, save_pdf=True)

    plt.close(fig)

_SPL_LABEL = r'SPL, $L_{\mathrm{Z}}$ (dB re 20$~\mu$Pa)'


def _window_title(fig, text):
    """MATLAB: figure('name', ...). The text only shows in the window's title bar, never inside the saved figure."""
    try:
        fig.canvas.manager.set_window_title(text)
    except Exception:  # noqa: BLE001 - non-interactive backends may not have a window
        pass


def _spectrogram_tiles(spls, T, F, window_title, tile_titles, cmap, vmin, vmax, cbar_label):
    """Vertical stack of spectrograms with ONE colorbar on the east side (MATLAB: tiledlayout('vertical') and
    colorbar with Layout.Tile = 'east', label font size 16)."""
    n = len(spls)
    fig, axs = plt.subplots(n, 1, figsize=(10, 5 if n == 1 else 8), layout="constrained", squeeze=False)
    axs = list(axs[:, 0])
    _window_title(fig, window_title)
    # MATLAB imagesc(T, F/1000, SPL) centres the pixels on T and F: the axis starts half a pixel before the first window
    # centre, i.e. exactly at 0 s (so that the tick label "0" is drawn)
    dT = (T[1] - T[0]) if len(T) > 1 else 0.0
    dF = (F[1] - F[0]) if len(F) > 1 else 0.0
    extent = [T[0] - dT / 2, T[-1] + dT / 2, (F[0] - dF / 2) / 1000, (F[-1] + dF / 2) / 1000]
    im = None
    for ax, spl, tile_title in zip(axs, spls, tile_titles):
        im = ax.imshow(spl, extent=extent, aspect="auto", origin="lower", cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_xlim(extent[0], extent[1])
        ax.set_ylim([0, 15])                       # kHz
        ax.set_yticks([0, 5, 10, 15])
        ax.set_xlabel("Time, $t$ (s)")
        ax.set_ylabel("Frequency, $f$ (kHz)")
        if tile_title:
            ax.set_title(tile_title)
    cb = fig.colorbar(im, ax=axs, location="right", fraction=0.05, pad=0.02, aspect=30)
    cb.set_label(cbar_label, fontsize=16)
    return fig


def plot_spectrogram(signal, fs, title, tag_auralization, tag_save):
    """MATLAB PLOT_spectrogram: one tile per channel ('Left ear' / 'Right ear' titles for stereo), common colorbar."""
    signal = np.atleast_2d(signal)
    if signal.shape[0] < signal.shape[1]:
        signal = signal.T

    window_size = 1024
    overlap = 0.75
    pref = 20e-6  # SPL reference pressure

    spls = []
    for ch in range(signal.shape[1]):
        P, F, T = myspecgram(signal[:, ch], fs, window_size, overlap)
        spls.append(20 * np.log10(np.abs(P) / pref + 1e-12))

    vmax = max(np.max(spl) for spl in spls)
    vmin = 100 if vmax > 110 else 0                # MATLAB: probably emission at the source
    tile_titles = [None] if len(spls) == 1 else ["Left ear", "Right ear"][:len(spls)]

    _spectrogram_tiles(spls, T, F, title, tile_titles, "jet", vmin, vmax, _SPL_LABEL)

    if tag_auralization:
        filename = f"{tag_auralization}{tag_save}"
        export_figures(filename, save_mat_fig=False, save_png=True, save_pdf=True)

    show_figure()


def plot_spectrogram_binaural(signal_stereo, fs, title, tag_auralization, tag_save):
    """Left and right ear spectrograms. signal_stereo : (N, 2), column 0 = left ear, column 1 = right ear."""
    plot_spectrogram(signal_stereo, fs, title, tag_auralization, tag_save)


def plot_hrir_spectrogram(hrir_direct, hrir_reflected, dt_panam, tag_auralization, tag_save):
    """
    Port of MATLAB PLOT_HRIR_spectrogram.
    2x2 tiles: direct left/right, reflected left/right, one colorbar on the east side.
    Each panel shows the magnitude spectrum of the HRIRs over time.

    hrir_direct / hrir_reflected: dicts with "l_a" and "r_a", each (n_samples, n_time_steps)
    """
    panels = [
        (hrir_direct["l_a"],    "Direct - left ear"),
        (hrir_direct["r_a"],    "Direct - right ear"),
        (hrir_reflected["l_a"], "Reflected - left ear"),
        (hrir_reflected["r_a"], "Reflected - right ear"),
    ]

    fig = plt.figure(figsize=(10, 8), layout="constrained")
    _window_title(fig, "OUTPUT - Spectrogram of HRIRs")
    gs = fig.add_gridspec(2, 3, width_ratios=[1, 1, 0.07])
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]
    cax = fig.add_subplot(gs[1, 2])

    dr = [-20, 20]

    for idx, (data, title) in enumerate(panels):
        n_samples, n_steps = data.shape
        time_vec = np.linspace(0, n_steps * dt_panam, n_steps)

        n_fft_bins = n_samples // 2 + 1
        mag_db = np.zeros((n_fft_bins, n_steps))
        for t in range(n_steps):
            spec = np.fft.rfft(data[:, t])
            mag_db[:, t] = 20 * np.log10(np.abs(spec) + 1e-30)

        freq_vec = np.fft.rfftfreq(n_samples, d=1.0 / 44100)

        ax = axes[idx]
        pcm = ax.pcolormesh(time_vec, freq_vec, mag_db, cmap='RdBu_r',
                            vmin=dr[0], vmax=dr[1], shading='auto')
        ax.set_yscale('log')
        ax.set_ylim([200, 22050])
        ax.set_yticks([1000, 10000, 20000])
        ax.set_yticklabels(['1k', '10k', '20k'])
        ax.yaxis.set_minor_locator(plt.NullLocator())
        # MATLAB: XTick = [0, floor(timeVec(round(length/2))), floor(timeVec(end))]
        mid = int(np.floor(len(time_vec) / 2 + 0.5)) - 1
        ax.set_xticks([0, np.floor(time_vec[mid]), np.floor(time_vec[-1])])
        ax.set_xlim(time_vec[0], time_vec[-1])
        ax.set_title(title)

        if idx >= 2:
            ax.set_xlabel("Time, $t$ (s)")
        else:
            ax.set_xticklabels([])
        if idx % 2 == 0:
            ax.set_ylabel("Frequency, $f$ (Hz)")
        else:
            ax.set_yticklabels([])

    cb = fig.colorbar(pcm, cax=cax)
    cb.set_label(_SPL_LABEL, fontsize=16)

    if tag_auralization:
        filename = f"{tag_auralization}{tag_save}"
        export_figures(filename, save_mat_fig=False, save_png=True, save_pdf=True)

    show_figure()


def plot_spectrogram_difference(signal_mono, signal_binaural, fs, tag_auralization, tag_save):
    """
    Port of MATLAB PLOT_spectrogram_difference.
    Shows spectrogram difference between binaural (left+right) and mono signals.

    signal_mono : (N,) array
    signal_binaural : (N, 2) array — column 0 = left, column 1 = right
    """
    window_size = 1024
    overlap = 0.75
    pref = 20e-6

    signal_binaural = np.atleast_2d(signal_binaural)
    if signal_binaural.shape[0] < signal_binaural.shape[1]:
        signal_binaural = signal_binaural.T

    min_len = min(len(signal_mono), len(signal_binaural))

    P_mono, F, T = myspecgram(signal_mono[:min_len], fs, window_size, overlap)
    P_left, _, _ = myspecgram(signal_binaural[:min_len, 0], fs, window_size, overlap)
    P_right, _, _ = myspecgram(signal_binaural[:min_len, 1], fs, window_size, overlap)

    spl_mono = 20 * np.log10(np.abs(P_mono) / pref + 1e-12)
    spl_left = 20 * np.log10(np.abs(P_left) / pref + 1e-12)
    spl_right = 20 * np.log10(np.abs(P_right) / pref + 1e-12)

    _spectrogram_tiles([spl_left - spl_mono, spl_right - spl_mono], T, F,
                       "OUTPUT - Spectrogram (binaural - mono)", ["Left ear", "Right ear"],
                       "RdBu_r", -20, 20,
                       r'$L_{\mathrm{Z,stereo}} - L_{\mathrm{Z,mono}}$ (dB re 20$~\mu$Pa)')

    if tag_auralization:
        filename = f"{tag_auralization}{tag_save}"
        export_figures(filename, save_mat_fig=False, save_png=True, save_pdf=True)

    show_figure()


def plot_fir_comparison(ir_fir, tf_art, t_block, fs, tag_auralization):
    """
    Port of MATLAB PLOT_FIR.
    Compare FIR filter frequency response vs original ART transfer function at one time block.

    ir_fir : (nTaps, nTimeSteps) — truncated impulse response
    tf_art : (nFreqBins_single_sided, nTimeSteps) — single-sided ART transfer function
    t_block : int — time block index to plot
    """
    n_taps = ir_fir.shape[0]
    n_bins_fir = int(np.ceil((n_taps + 1) / 2))
    freq_fir = np.linspace(0, fs / 2, n_bins_fir)

    fft_fir = np.fft.fft(ir_fir[:, t_block])
    fft_fir_single = fft_fir[:n_bins_fir]
    # No epsilon inside the log, like MATLAB (10*log10(abs(x).^2)): an epsilon floors both curves at -300 dB and hides
    # that the FIR (numerical noise, ~ -380 dB) and the ART transfer function (far smaller) live at different levels.
    with np.errstate(divide="ignore"):
        mag_fir = 10 * np.log10(np.abs(fft_fir_single) ** 2)

    freq_art = np.linspace(0, fs / 2, tf_art.shape[0])
    with np.errstate(divide="ignore"):
        mag_art = 10 * np.log10(np.abs(tf_art[:, t_block]) ** 2)

    from matplotlib.ticker import MultipleLocator

    fig, ax1 = plt.subplots(figsize=(10, 5))
    _window_title(fig, "PROCESSING - Atmospheric transfer function (FIR filter)")
    # MATLAB plots the FIR first (1st colour) and the ART dashed, 1.5 pt (2nd colour)
    b, = ax1.semilogx(freq_fir, mag_fir, color=MATLAB_COLORS[0], linewidth=0.5)
    a, = ax1.semilogx(freq_art, mag_art, '--', color=MATLAB_COLORS[1], linewidth=1.5)

    ax1.set_xlabel("Frequency, $f$ (Hz)")
    ax1.set_ylabel(r'$10\cdot\log_{10}\left(|A_{\mathrm{atm}}|^2 \right)$')
    ax1.set_xlim([20, 25e3])
    ax1.set_ylim([-200, 0])
    ax1.set_yticks(np.arange(-200, 1, 20))
    ax1.yaxis.set_minor_locator(MultipleLocator(10))          # MATLAB: MinorTickValues = -200:10:0
    ax1.yaxis.set_tick_params(which="minor", left=True, right=False)

    if len(freq_art) == len(freq_fir):
        ax2 = ax1.twinx()
        delta = mag_fir[:len(freq_art)] - mag_art
        ax2.semilogx(freq_art, delta, '-', linewidth=0.5, color=MATLAB_COLORS[2])
        ax2.set_ylabel('FIR-ART')
        ax2.set_ylim([-20, 20])
        ax2.set_yticks(np.arange(-20, 21, 5))
        ax2.tick_params(axis="y", colors=MATLAB_COLORS[2])
        ax2.yaxis.label.set_color(MATLAB_COLORS[2])

    # (after the twin axis: it shares the x axis and would otherwise reset the tick labels)
    ax1.set_xticks([20, 100, 1000, 10000, 20000])
    ax1.set_xticklabels(['20', '100', '1k', '10k', '20k'])
    ax1.yaxis.set_minor_locator(MultipleLocator(10))
    ax1.legend([a, b], ['ART', f'FIR - {n_taps:.5g} Taps'], loc='lower left')
    ax1.grid(True, which='major')
    ax1.grid(True, which='minor', axis='x', linestyle=':')
    fig.tight_layout()

    if tag_auralization:
        filename = f"{tag_auralization}_atmospheric_transfer_function_FIR"
        export_figures(filename, save_mat_fig=False, save_png=True, save_pdf=True)

    show_figure()


def plot_fir_spectrogram(ir_fir, tf_art, fs, tag_auralization):
    """
    Port of MATLAB PLOT_FIR_spectrogram.
    Shows FIR frequency response over all time steps, and delta vs ART if sizes match.

    ir_fir : (nTaps, nTimeSteps) — truncated impulse response
    tf_art : (nFreqBins_single_sided, nTimeSteps) — single-sided ART transfer function
    """
    n_taps, n_steps = ir_fir.shape
    n_bins_fir = int(np.ceil((n_taps + 1) / 2))

    fft_fir = np.fft.fft(ir_fir, axis=0)
    fft_fir_single = fft_fir[:n_bins_fir, :]
    # No epsilon inside the log, like MATLAB's PLOT_FIR_spectrogram: where the ART transfer function is far below the FIR
    # noise floor the difference is huge (red) instead of being floored at -300 dB (blue). +-inf/NaN follow imagesc.
    with np.errstate(divide="ignore"):
        mag_fir = 10 * np.log10(np.abs(fft_fir_single) ** 2)

    freq_fir = np.linspace(0, fs / 2, n_bins_fir)
    with np.errstate(divide="ignore"):
        mag_art = 10 * np.log10(np.abs(tf_art) ** 2)
    freq_art = np.linspace(0, fs / 2, tf_art.shape[0])

    if mag_fir.shape[0] == mag_art.shape[0]:
        with np.errstate(invalid="ignore"):
            delta = mag_fir - mag_art

        fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
        _window_title(fig, "PROCESSING - Atmospheric transfer function spectrogram (FIR-ART)")
        im = ax.imshow(delta, extent=[0, n_steps, freq_fir[0], freq_fir[-1]],
                       aspect='auto', origin='lower', cmap='jet', vmin=0, vmax=50)
        ax.set_xlabel("Time bins")
        ax.set_ylabel("Frequency, $f$ (Hz)")
        from matplotlib.ticker import FuncFormatter        # MATLAB: exponent label x10^4 above the axis, ticks 0, 0.5, 1, ...
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: f"{v / 1e4:.10g}"))
        ax.yaxis._keep_formatter = True
        ax.text(0.0, 1.0, r"$\times10^{4}$", transform=ax.transAxes, ha="left", va="bottom")
        cb = fig.colorbar(im, ax=ax, location="right", fraction=0.05, pad=0.02, aspect=30)
        cb.set_label(r'$10\cdot\log_{10}\left(\frac{|A_{\mathrm{atm,FIR}}}{A_{\mathrm{atm,ART}}}|^2 \right)$')

        if tag_auralization:
            filename = f"{tag_auralization}_atmospheric_transfer_function_spectrogram_FIR_minus_ART"
            export_figures(filename, save_mat_fig=False, save_png=True, save_pdf=True)

        show_figure()


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