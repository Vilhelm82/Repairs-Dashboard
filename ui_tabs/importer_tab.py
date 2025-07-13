#!/usr/bin/env python3
# ui_tabs/importer_tab.py

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
import threading
import subprocess
import sys
import os
from core import db


class ImporterTab(ttk.Frame):
    """
    The ImporterTab provides the UI to queue up job references and
    run an automation sequence to scrape and import their data from ADEN.
    """

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.importer_job_refs = []
        self.importing = False

        # --- UI Initialization ---
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(top_frame, text="Select Import Sequence:").pack(anchor="w")

        # --- NEW: Frame to hold the combobox and refresh button ---
        seq_frame = ttk.Frame(top_frame)
        seq_frame.pack(fill="x", pady=(0, 5))

        self.seq_combo = ttk.Combobox(seq_frame, textvariable=self.controller.sequence_var, state="readonly")
        # --- MODIFIED: Pack the combobox to the left ---
        self.seq_combo.pack(side="left", fill="x", expand=True)

        # --- NEW: Refresh button to update the sequence list ---
        self.refresh_btn = ttk.Button(seq_frame, text="🔄", command=self.refresh_sequences, width=3)
        self.refresh_btn.pack(side="left", padx=(5, 0))

        # Initial population of the combobox
        self.refresh_sequences(log=False)  # Use the new refresh method to populate initially

        self.importer_input_box = ttk.Entry(top_frame, font=("Segoe UI", 14))
        self.importer_input_box.pack(pady=5, fill="x")
        self.importer_input_box.bind("<Return>", self.add_job_to_importer_queue)

        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=10)
        importer_queue_frame = ttk.LabelFrame(list_frame, text="Import Queue")
        importer_queue_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.importer_job_list = tk.Listbox(importer_queue_frame, font=("Segoe UI", 12))
        self.importer_job_list.pack(fill="both", expand=True)
        self.importer_job_list.bind("<Double-1>", self.on_double_click)
        self.importer_job_list.bind("<Delete>", self.delete_importer_job)

        flagged_frame = ttk.LabelFrame(list_frame, text="Flagged for Review")
        flagged_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        self.flagged_list = tk.Listbox(flagged_frame, font=("Segoe UI", 12), bg="#FFFACD")
        self.flagged_list.bind("<Double-1>", self.on_double_click)
        self.flagged_list.pack(fill="both", expand=True)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=5)
        self.import_btn = ttk.Button(btn_frame, text="📥 Import from ADEN", command=self.start_import)
        self.import_btn.pack(side="left", padx=5)
        self.stop_btn = ttk.Button(btn_frame, text="🛑 Stop Process", command=self.stop_import, state=tk.DISABLED)
        self.stop_btn.pack(side="left", padx=5)
        self.debug_btn = ttk.Button(btn_frame, text="🔧 Debug Utility", command=self.launch_debug_utility)
        self.debug_btn.pack(side="left", padx=5)

        console_frame = ttk.LabelFrame(self, text="Logs")
        console_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.console = ScrolledText(console_frame, font=("Consolas", 10), state='disabled', height=8, wrap='word')
        self.console.pack(fill="both", expand=True, padx=5, pady=5)

        # Connect this console to the central logger
        self.controller.setup_logging(console_widget=self.console)

    # --- NEW: Method to refresh the sequence list ---
    def refresh_sequences(self, log=True):
        """
        Reloads the sequence files from the directory and updates the combobox.
        """
        if log:
            self.controller.logger.info("Refreshing automation sequences...")

        current_selection = self.controller.sequence_var.get()
        sequence_files = self.controller.load_sequences()

        if sequence_files:
            self.seq_combo['values'] = sequence_files
            # If the old selection is still a valid file, restore it
            if current_selection in sequence_files:
                self.seq_combo.set(current_selection)
            else:
                self.controller.sequence_var.set('')  # Clear if the file was deleted
        else:
            # No files found, clear the combobox
            self.seq_combo['values'] = []
            self.controller.sequence_var.set('')

        if log:
            self.controller.logger.info(f"Found {len(sequence_files)} sequences.")

    def add_job_to_importer_queue(self, event=None):
        ref = self.importer_input_box.get().strip().upper()
        if ref and ref not in self.importer_job_refs:
            self.importer_job_refs.append(ref)
            self.importer_job_list.insert(tk.END, ref)
        self.importer_input_box.delete(0, tk.END)

    def delete_importer_job(self, event=None):
        selected_indices = self.importer_job_list.curselection()
        if not selected_indices: return

        # Iterate backwards to avoid index shifting issues when deleting
        for index in reversed(selected_indices):
            ref_to_delete = self.importer_job_list.get(index)
            self.importer_job_list.delete(index)
            if ref_to_delete in self.importer_job_refs:
                self.importer_job_refs.remove(ref_to_delete)

    def start_import(self):
        if not self.importer_job_refs:
            messagebox.showwarning("No Jobs", "No job references in the queue to process.")
            return
        if not self.controller.sequence_var.get():
            messagebox.showerror("Error", "No import sequence selected.")
            return

        self.flagged_list.delete(0, tk.END)
        self.importing = True
        self._update_import_buttons(True)

        # The thread now runs a method that calls the controller
        threading.Thread(target=self._run_import_thread, daemon=True).start()

    def stop_import(self):
        self.importing = False
        self._update_import_buttons(False)

    def _update_import_buttons(self, is_running):
        self.import_btn.config(state=tk.DISABLED if is_running else tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL if is_running else tk.DISABLED)

    def _run_import_thread(self):
        """
        Manages the import queue, calling the central automation engine for each job.
        """
        self.controller.clear_debug_images()
        job_queue = list(self.importer_job_refs)  # Make a copy to iterate over

        for i, job_ref in enumerate(job_queue):
            if not self.importing:
                self.controller.logger.warning("Import process stopped by user.")
                break

            # This is the Data Context that will be passed to the automation engine
            data_context = {"job_ref": job_ref}

            self.controller.logger.info(f"--- Starting import for: {job_ref} ({i + 1}/{len(job_queue)}) ---")
            completion_event, success_event = self.controller.run_automation_sequence(
                self.controller.sequence_var.get(),
                data_context
            )
            completion_event.wait()

            # Update UI on the main thread
            self.master.after(0, self.importer_job_list.delete, 0)
            if job_ref in self.importer_job_refs:
                self.importer_job_refs.remove(job_ref)

        self.importing = False
        self.master.after(0, self._update_import_buttons, False)
        self.controller.logger.info("--- Import sequence finished ---")

    def launch_debug_utility(self):
        """Launch the debug utility as a separate process."""
        try:
            debug_script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                             "debug_utility.py")
            self.controller.logger.info(f"Launching debug utility from: {debug_script_path}")

            # Use Python executable to run the script
            python_exe = sys.executable
            subprocess.Popen([python_exe, debug_script_path],
                             creationflags=subprocess.CREATE_NEW_CONSOLE)

            self.controller.logger.info("Debug utility launched successfully")
        except Exception as e:
            self.controller.logger.error(f"Failed to launch debug utility: {e}")
            messagebox.showerror("Error", f"Failed to launch debug utility:\n{e}")

    def on_double_click(self, event):
        """Callback function to handle double-clicks on either listbox."""
        listbox = event.widget
        selected_indices = listbox.curselection()
        if not selected_indices:
            return

        job_ref = listbox.get(selected_indices[0])
        if job_ref:
            self.controller.switch_to_card_view(job_ref)
