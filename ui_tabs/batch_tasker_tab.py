#!/usr/bin/env python3
# ui_tabs/batch_tasker_tab.py

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from core import db
from utils.debug_ui_widgets import RightClickMenu

class BatchTaskerTab(ttk.Frame):
    """
    The BatchTaskerTab provides a UI for batch processing a list of jobs
    with a series of automation sequences.
    """
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.batch_job_refs = [] # List to hold jobs for processing
        self.is_batch_running = False
        self.skip_current_job_event = threading.Event()

        # --- UI Variable Initialization ---
        self.preset1_var = tk.StringVar()
        self.preset2_var = tk.StringVar()
        self.preset3_var = tk.StringVar()

        # --- Main Layout (2 columns) ---
        self.columnconfigure(0, weight=1, minsize=150)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)

        # --- Left Panel: Job Reference List ---
        left_panel = ttk.Frame(self)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        left_panel.rowconfigure(2, weight=1) # Make listbox expand
        left_panel.columnconfigure(0, weight=1)

        ttk.Label(left_panel, text="Add Job Reference(s):").grid(row=0, column=0, sticky="w", padx=5)
        self.job_entry = ttk.Entry(left_panel)
        self.job_entry.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        
        self.job_listbox = tk.Listbox(left_panel, selectmode="extended")
        self.job_listbox.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        
        ttk.Button(left_panel, text="Load All Jobs from DB", command=self.load_all_jobs).grid(row=3, column=0, sticky="ew", padx=5, pady=(5,0))
        
        # --- Right Panel: Controls and Results ---
        right_panel = ttk.Frame(self)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        right_panel.rowconfigure(2, weight=1) # Make the results lists expand
        right_panel.columnconfigure(0, weight=1)

        # Top control bar
        top_bar = ttk.Frame(right_panel)
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.run_button = ttk.Button(top_bar, text="▶ Run Batch", command=self.start_batch)
        self.run_button.pack(side="left")
        self.stop_button = ttk.Button(top_bar, text="🛑 STOP Batch", command=self.stop_batch, state=tk.DISABLED)
        self.stop_button.pack(side="left", padx=5)
        self.skip_button = ttk.Button(top_bar, text="⏭ Skip This Job", command=self.skip_job, state=tk.DISABLED)
        self.skip_button.pack(side="left", padx=5)

        # Sequence slots
        sequences_frame = ttk.Frame(right_panel)
        sequences_frame.grid(row=1, column=0, sticky="new")
        available_sequences = self.controller.load_sequences()
        self._create_sequence_slot(sequences_frame, "Primary Sequence", self.preset1_var, available_sequences)
        self._create_sequence_slot(sequences_frame, "Secondary Sequence", self.preset2_var, available_sequences)
        self._create_sequence_slot(sequences_frame, "Tertiary Sequence", self.preset3_var, available_sequences)
        
        # Results lists
        results_frame = ttk.Frame(right_panel)
        results_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        results_frame.rowconfigure(0, weight=1)
        results_frame.columnconfigure(0, weight=1)
        results_frame.columnconfigure(1, weight=1)

        success_frame = ttk.LabelFrame(results_frame, text="Successfully Updated")
        success_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        success_frame.rowconfigure(0, weight=1)
        success_frame.columnconfigure(0, weight=1)
        self.success_listbox = tk.Listbox(success_frame, bg="#e0ffe0")
        self.success_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        fail_frame = ttk.LabelFrame(results_frame, text="Unsuccessfully Updated")
        fail_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        fail_frame.rowconfigure(0, weight=1)
        fail_frame.columnconfigure(0, weight=1)
        self.fail_listbox = tk.Listbox(fail_frame, bg="#ffe0e0")
        self.fail_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # --- Create and configure the right-click menu ---
        self.listbox_menu = RightClickMenu(self)
        self.listbox_menu.add_command(label="Delete Selected", command=self.delete_selected_jobs)

        # --- Bind all events ---
        self.job_entry.bind("<Return>", self.add_job_to_queue)
        self.job_listbox.bind("<Button-3>", self.show_context_menu)  # Right-click
        self.job_listbox.bind("<Delete>", lambda e: self.delete_selected_jobs())  # Delete key
        self.job_listbox.bind("<Double-1>", self.on_double_click)
        self.success_listbox.bind("<Double-1>", self.on_double_click)
        self.fail_listbox.bind("<Double-1>", self.on_double_click)

    def _create_sequence_slot(self, parent, text, var, sequence_list):
        """Helper method to create a reusable sequence selection widget."""
        frame = ttk.Frame(parent, padding=5)
        frame.pack(fill="x", pady=2)
        
        ttk.Label(frame, text=text + ":").grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 10))
        
        combo = ttk.Combobox(frame, textvariable=var, values=sequence_list, state="readonly")
        combo.grid(row=0, column=1, columnspan=2, sticky="ew")
        
        ttk.Label(frame, text="Param 1:").grid(row=1, column=1, sticky="w", pady=(5,0))
        ttk.Entry(frame, width=15).grid(row=1, column=2, sticky="w", pady=(5,0))
        
        frame.columnconfigure(2, weight=1)
        return frame

    def show_context_menu(self, event):
        """Displays the right-click context menu at the cursor's location."""
        # Ensure the item under the cursor is selected before showing the menu
        self.job_listbox.selection_clear(0, tk.END)
        self.job_listbox.selection_set(self.job_listbox.nearest(event.y))
        self.job_listbox.activate(self.job_listbox.nearest(event.y))
        self.listbox_menu.show(event)

    def delete_selected_jobs(self):
        """Deletes all selected jobs from the batch queue listbox."""
        selected_indices = self.job_listbox.curselection()
        if not selected_indices:
            return

        # Iterate backwards through the selected indices to avoid shifting
        # the positions of the remaining items as we delete.
        for index in reversed(selected_indices):
            job_ref_to_delete = self.job_listbox.get(index)
            self.job_listbox.delete(index)
            # Also remove from our internal data list
            if job_ref_to_delete in self.batch_job_refs:
                self.batch_job_refs.remove(job_ref_to_delete)
        self.controller.logger.info(f"Removed {len(selected_indices)} jobs from the batch queue.")

    def load_all_jobs(self):
        self.controller.logger.info("Loading all jobs from database into batch queue...")
        self.job_listbox.delete(0, tk.END)
        self.batch_job_refs.clear()
        
        all_refs = db.get_all_jobs(full=False)
        for job_ref in all_refs:
            self.job_listbox.insert(tk.END, job_ref)
            self.batch_job_refs.append(job_ref)
        self.controller.logger.info(f"Loaded {len(all_refs)} jobs into the queue.")
    def add_job_to_queue(self, event=None):
        """Adds a job reference from the entry box to the queue list."""
        ref = self.job_entry.get().strip().upper()
        if ref and ref not in self.batch_job_refs:
            self.batch_job_refs.append(ref)
            self.job_listbox.insert(tk.END, ref)
        self.job_entry.delete(0, tk.END)
    def start_batch(self):
        if not self.batch_job_refs:
            messagebox.showwarning("Empty Queue", "Please load jobs into the queue first.")
            return
            
        selected_sequences = [var.get() for var in [self.preset1_var, self.preset2_var, self.preset3_var] if var.get()]
        if not selected_sequences:
            messagebox.showwarning("No Sequence", "Please select at least one sequence to run.")
            return

        self.is_batch_running = True
        self.skip_current_job_event.clear()  # Reset the skip event at the start of a batch
        self.run_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.skip_button.config(state=tk.NORMAL)  # Enable the skip button
        self.success_listbox.delete(0, tk.END)
        self.fail_listbox.delete(0, tk.END)
        
        threading.Thread(target=self._run_batch_thread, args=(selected_sequences,), daemon=True).start()

    def _run_batch_thread(self, sequences_to_run):
        job_queue = list(self.batch_job_refs)
        for i, job_ref in enumerate(job_queue):
            if not self.is_batch_running:
                self.controller.logger.warning("Batch process stopped by user.")
                break
            
            self.controller.logger.info(f"--- Processing Batch Job: {job_ref} ({i+1}/{len(job_queue)}) ---")
            job_overall_success = True

            self.skip_current_job_event.clear()
            
            for seq_file in sequences_to_run:
                self.controller.logger.info(f"-> Running sequence '{seq_file}' for {job_ref}")
                data_context = {"job_ref": job_ref}

                completion_event, success_event = self.controller.run_automation_sequence(
                    seq_file,
                    data_context,
                    skip_event=self.skip_current_job_event  # Pass the event here
                )
                completion_event.wait()
                
                if not success_event.is_set():
                    self.controller.logger.error(f"Sequence '{seq_file}' failed for job {job_ref}. Stopping batch for this job.")
                    job_overall_success = False
                    break # Stop processing further sequences for this failed job

            # Update UI based on the outcome for this job
            if job_overall_success:
                self.master.after(0, self.success_listbox.insert, tk.END, job_ref)
            else:
                self.master.after(0, self.fail_listbox.insert, tk.END, job_ref)
            
            # Remove from the main queue
            try:
                idx = self.batch_job_refs.index(job_ref)
                self.master.after(0, self.job_listbox.delete, idx)
                self.batch_job_refs.pop(idx)
            except ValueError:
                pass

        self.controller.logger.info("--- Batch Process Finished ---")
        self.is_batch_running = False
        self.master.after(0, self.run_button.config, {'state': tk.NORMAL})
        self.master.after(0, self.stop_button.config, {'state': tk.DISABLED})
        self.master.after(0, self.skip_button.config, {'state': tk.DISABLED})
        
    def stop_batch(self):
        """Sets the flag to gracefully stop the batch processing loop after the current job."""
        if self.is_batch_running:
            self.controller.logger.warning("STOP button pressed. The batch will halt after the current job finishes.")
            self.is_batch_running = False

    def on_double_click(self, event):
        listbox = event.widget
        selected_indices = listbox.curselection()
        if not selected_indices: return
        job_ref = listbox.get(selected_indices[0])
        if job_ref: self.controller.switch_to_card_view(job_ref)

    def skip_job(self):
        """Sets the event to signal the running automation to skip to the next job."""
        self.controller.logger.warning("SKIP button pressed. Attempting to interrupt current job.")
        self.skip_current_job_event.set()