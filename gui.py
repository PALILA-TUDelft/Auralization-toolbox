# gui.py
#
# Graphical front-end for the auralization toolbox (main.py).
# The pipeline runs as a subprocess so the GUI stays responsive and
# matplotlib figure windows behave exactly as when running main.py directly.

import os
import queue
import subprocess
import sys
import threading
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from pathlib import Path

import customtkinter as ctk

REPO_ROOT = Path(__file__).resolve().parent
BACKUP_INI = REPO_ROOT / "input_data" / "input_file_auralization.ini"
BACKUP_SOURCE_FILE = REPO_ROOT / "input_data" / "auralization_input.dat"
BACKUP_FLIGHT_PROFILE_FILE = REPO_ROOT / "input_data" / "geschw_hoehe_verlauf.dat"

# (figure key used by main.py, label shown in the GUI)
FIGURE_OPTIONS = [
    ("flight_profile", "Flight profile"),
    ("trim_data", "Trim data (SPL + flight profile trim windows)"),
    ("tonal_fan", "Tonal fan harmonics (PANAM input + spectrogram)"),
    ("tonal_buzzsaw", "Tonal buzzsaw (PANAM input + spectrogram)"),
    ("broadband_engine", "Broadband spectrogram: engine"),
    ("broadband_airframe", "Broadband spectrogram: airframe"),
    ("engine_spectrogram", "Engine signal spectrogram"),
    ("overall_spectrogram", "Overall signal spectrogram"),
    ("propagation_rays", "Propagation: ray-tracing angles & distances"),
    ("propagation_tf", "Propagation: atmospheric transfer function (ART / FIR)"),
    ("propagated_spectrogram", "Propagated signal spectrogram (at receiver)"),
    ("binaural", "Binaural diagnostics (HRIR, binaural vs mono) *"),
]


class AuralizationGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Auralization Toolbox")
        self.geometry("820x1040")
        self.minsize(700, 720)

        self.process = None
        self.log_queue = queue.Queue()
        self.last_results_dir = REPO_ROOT / "results_auralization"

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)  # log box expands

        self._build_input_section()
        self._build_figures_section()
        self._build_run_section()
        self._build_log_section()

        self.after(100, self._poll_log_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI

    def _add_file_choice(self, frame, row, title, backup_path, filetypes):
        """Builds a 'backup file' / 'custom file' radio choice starting at `row`.
        Returns (mode_var, custom_path_var, next_free_row).
        """
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 2))

        mode_var = ctk.StringVar(value="backup")

        ctk.CTkRadioButton(
            frame, text=f"Backup file  ({backup_path.relative_to(REPO_ROOT)})",
            variable=mode_var, value="backup"
        ).grid(row=row + 1, column=0, columnspan=3, sticky="w", padx=12, pady=2)

        ctk.CTkRadioButton(
            frame, text="Custom file:",
            variable=mode_var, value="custom"
        ).grid(row=row + 2, column=0, sticky="w", padx=12, pady=(2, 8))

        custom_path_var = ctk.StringVar(value="")
        entry = ctk.CTkEntry(frame, textvariable=custom_path_var, placeholder_text="No file selected")
        entry.grid(row=row + 2, column=1, sticky="ew", padx=(4, 6), pady=(2, 8))

        browse_button = ctk.CTkButton(
            frame, text="Browse…", width=90,
            command=lambda: self._browse_file(custom_path_var, filetypes))
        browse_button.grid(row=row + 2, column=2, sticky="e", padx=(0, 12), pady=(2, 8))

        def _update_state(*_):
            state = "normal" if mode_var.get() == "custom" else "disabled"
            entry.configure(state=state)
            browse_button.configure(state=state)

        mode_var.trace_add("write", _update_state)
        _update_state()

        return mode_var, custom_path_var, row + 3

    def _build_input_section(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        frame.grid_columnconfigure(1, weight=1)

        row = 0
        self.ini_mode, self.ini_custom_path_var, row = self._add_file_choice(
            frame, row, "Input file (.ini)", BACKUP_INI,
            [("INI files", "*.ini"), ("All files", "*.*")])

        self.source_mode, self.source_custom_path_var, row = self._add_file_choice(
            frame, row, "Sound source file (.dat)", BACKUP_SOURCE_FILE,
            [("DAT files", "*.dat"), ("All files", "*.*")])

        self.flight_mode, self.flight_custom_path_var, row = self._add_file_choice(
            frame, row, "Flight profile file (.dat)", BACKUP_FLIGHT_PROFILE_FILE,
            [("DAT files", "*.dat"), ("All files", "*.*")])

        ctk.CTkLabel(frame, text="Save results to:", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=row, column=0, sticky="w", padx=12, pady=(10, 4))
        row += 1

        self.results_path_var = ctk.StringVar(value="")
        self.results_entry = ctk.CTkEntry(
            frame, textvariable=self.results_path_var,
            placeholder_text="Default: same folder as the input file")
        self.results_entry.grid(row=row, column=1, sticky="ew", padx=(4, 6), pady=(0, 12))

        ctk.CTkButton(frame, text="Browse…", width=90, command=self._browse_results_folder).grid(
            row=row, column=2, sticky="e", padx=(0, 12), pady=(0, 12))

    def _build_figures_section(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(frame, text="Figures to plot", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.grid(row=0, column=1, sticky="e", padx=12, pady=(10, 4))
        ctk.CTkButton(buttons, text="Select all", width=90,
                      command=lambda: self._set_all_figures(True)).pack(side="left", padx=4)
        ctk.CTkButton(buttons, text="Select none", width=90,
                      command=lambda: self._set_all_figures(False)).pack(side="left", padx=4)

        self.figure_vars = {}
        for i, (key, label) in enumerate(FIGURE_OPTIONS):
            var = ctk.BooleanVar(value=True)
            self.figure_vars[key] = var
            ctk.CTkCheckBox(frame, text=label, variable=var).grid(
                row=1 + i // 2, column=i % 2, sticky="w", padx=16, pady=4)

        n_rows = 1 + (len(FIGURE_OPTIONS) + 1) // 2
        ctk.CTkLabel(
            frame, text="* binaural figures only appear when binaural_signal = 1 in the .ini file",
            text_color="gray60", font=ctk.CTkFont(size=11)
        ).grid(row=n_rows, column=0, columnspan=2, sticky="w", padx=16, pady=(4, 0))
        n_rows += 1

        self.save_figs_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(frame, text="Save figures to disk", variable=self.save_figs_var,
                        command=self._update_format_state).grid(
            row=n_rows, column=0, sticky="w", padx=16, pady=(10, 4))

        self.display_figs_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(frame, text="Open figure windows (close each window to continue the run)",
                        variable=self.display_figs_var).grid(
            row=n_rows, column=1, sticky="w", padx=16, pady=(10, 4))
        n_rows += 1

        format_frame = ctk.CTkFrame(frame, fg_color="transparent")
        format_frame.grid(row=n_rows, column=0, columnspan=2, sticky="w", padx=32, pady=(0, 12))
        ctk.CTkLabel(format_frame, text="Format:").pack(side="left", padx=(0, 8))
        self.save_png_var = ctk.BooleanVar(value=True)
        self.png_checkbox = ctk.CTkCheckBox(format_frame, text="PNG", variable=self.save_png_var)
        self.png_checkbox.pack(side="left", padx=(0, 12))
        self.save_pdf_var = ctk.BooleanVar(value=True)
        self.pdf_checkbox = ctk.CTkCheckBox(format_frame, text="PDF", variable=self.save_pdf_var)
        self.pdf_checkbox.pack(side="left")

    def _build_run_section(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=2, column=0, sticky="ew", padx=12, pady=6)
        frame.grid_columnconfigure(2, weight=1)

        self.run_button = ctk.CTkButton(frame, text="Run auralization", height=36,
                                        font=ctk.CTkFont(size=14, weight="bold"),
                                        command=self._run)
        self.run_button.grid(row=0, column=0, padx=(0, 8))

        self.stop_button = ctk.CTkButton(frame, text="Stop", height=36, width=80,
                                         fg_color="#8a2f2f", hover_color="#6e2424",
                                         command=self._stop, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=(0, 12))

        self.status_var = ctk.StringVar(value="Ready.")
        ctk.CTkLabel(frame, textvariable=self.status_var, anchor="w").grid(
            row=0, column=2, sticky="ew")

    def _build_log_section(self):
        self.log_box = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.grid(row=3, column=0, sticky="nsew", padx=12, pady=(6, 12))
        self.log_box.configure(state="disabled")

    # ------------------------------------------------------------- helpers

    def _browse_file(self, target_var, filetypes):
        path = filedialog.askopenfilename(
            title="Select file", filetypes=filetypes, initialdir=str(REPO_ROOT))
        if path:
            target_var.set(path)

    def _browse_results_folder(self):
        path = filedialog.askdirectory(title="Select folder for results", initialdir=str(REPO_ROOT))
        if path:
            self.results_path_var.set(path)

    def _set_all_figures(self, value):
        for var in self.figure_vars.values():
            var.set(value)

    def _update_format_state(self):
        state = "normal" if self.save_figs_var.get() else "disabled"
        self.png_checkbox.configure(state=state)
        self.pdf_checkbox.configure(state=state)

    def _append_log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _resolve_file_choice(self, mode_var, custom_path_var, backup_path, label):
        if mode_var.get() == "backup":
            path = backup_path
        else:
            raw = custom_path_var.get().strip()
            if not raw:
                messagebox.showerror(label, f"Please select a custom {label.lower()} or use the backup file.")
                return None
            path = Path(raw)

        if not path.is_file():
            messagebox.showerror(label, f"File not found:\n{path}")
            return None
        return path

    def _resolve_input(self):
        """Return (input_dir, ini_path, source_path, flight_profile_path) or None if invalid."""
        ini_path = self._resolve_file_choice(self.ini_mode, self.ini_custom_path_var, BACKUP_INI, "Input file (.ini)")
        if ini_path is None:
            return None

        source_path = self._resolve_file_choice(
            self.source_mode, self.source_custom_path_var, BACKUP_SOURCE_FILE, "Sound source file (.dat)")
        if source_path is None:
            return None

        flight_path = self._resolve_file_choice(
            self.flight_mode, self.flight_custom_path_var, BACKUP_FLIGHT_PROFILE_FILE, "Flight profile file (.dat)")
        if flight_path is None:
            return None

        return ini_path.parent, ini_path, source_path, flight_path

    # ----------------------------------------------------------------- run

    def _run(self):
        resolved = self._resolve_input()
        if resolved is None:
            return
        input_dir, ini_path, source_path, flight_path = resolved

        selected = [key for key, var in self.figure_vars.items() if var.get()]
        figures_arg = ",".join(selected) if selected else "none"

        cmd = [
            sys.executable, "-u", str(REPO_ROOT / "main.py"),
            "--input-dir", str(input_dir),
            "--ini", str(ini_path),
            "--source-file", str(source_path),
            "--flight-profile-file", str(flight_path),
            "--figures", figures_arg,
        ]
        if not self.save_figs_var.get():
            cmd.append("--no-save-figs")
        else:
            formats = []
            if self.save_png_var.get():
                formats.append("png")
            if self.save_pdf_var.get():
                formats.append("pdf")
            if not formats:
                messagebox.showerror("Figure format", "Select at least one figure format (PNG and/or PDF).")
                return
            cmd.extend(["--figure-formats", ",".join(formats)])

        results_raw = self.results_path_var.get().strip()
        if results_raw:
            results_path = Path(results_raw)
            if not results_path.is_dir():
                messagebox.showerror("Results folder", f"Folder not found:\n{results_path}")
                return
            cmd.extend(["--results", str(results_path)])
        else:
            results_path = input_dir
        self.last_results_dir = results_path / "results_auralization"

        env = os.environ.copy()
        if not self.display_figs_var.get():
            # Headless matplotlib: figures are still saved but no windows open
            env["MPLBACKEND"] = "Agg"

        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self._append_log("Running: " + " ".join(cmd) + "\n\n")

        try:
            self.process = subprocess.Popen(
                cmd, cwd=str(REPO_ROOT), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
        except OSError as exc:
            messagebox.showerror("Run failed", f"Could not start the pipeline:\n{exc}")
            self.process = None
            return

        self.run_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("Running…")

        threading.Thread(target=self._reader_thread, daemon=True).start()

    def _reader_thread(self):
        proc = self.process
        for line in proc.stdout:
            self.log_queue.put(line)
        returncode = proc.wait()
        self.log_queue.put(("__DONE__", returncode))

    def _poll_log_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple) and item[0] == "__DONE__":
                    self._on_finished(item[1])
                else:
                    self._append_log(item)
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    def _on_finished(self, returncode):
        self.process = None
        self.run_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        if returncode == 0:
            self.status_var.set(f"Finished successfully. Results in {self.last_results_dir}")
            self._append_log("\n=== Finished successfully ===\n")
        else:
            self.status_var.set(f"Failed (exit code {returncode}). See log above.")
            self._append_log(f"\n=== Failed with exit code {returncode} ===\n")

    def _stop(self):
        if self.process and self.process.poll() is None:
            self.process.kill()
            self.status_var.set("Stopped by user.")
            self._append_log("\n=== Stopped by user ===\n")

    def _on_close(self):
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("Quit", "A run is still in progress. Stop it and quit?"):
                return
            self.process.kill()
        self.destroy()


if __name__ == "__main__":
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    app = AuralizationGUI()
    app.mainloop()
