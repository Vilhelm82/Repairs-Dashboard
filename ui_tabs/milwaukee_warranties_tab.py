#!/usr/bin/env python3
# ui_tabs/milwaukee_warranties_tab.py

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from core import db


class MilwaukeeWarrantiesTab(ttk.Frame):
    """
    A dedicated tab for managing and booking Milwaukee warranty jobs for courier collection.
    """

    def __init__(self, parent, controller):
        super().__init__(parent, padding="10")
        self.controller = controller

        self.is_batch_running = False
        self.is_paused = False
        self.skip_current_job = False
        self.current_automation_thread = None
        self.skip_event = threading.Event()
        self.pause_event = threading.Event()
        self.continue_event = threading.Event()

        # --- Main Layout (2 columns) ---
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # --- Left Panel: Available Milwaukee Warranties ---
        left_panel = ttk.LabelFrame(self, text="Available Milwaukee Warranties")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_panel.rowconfigure(0, weight=1)
        left_panel.columnconfigure(0, weight=1)

        self.available_list = tk.Listbox(left_panel)
        self.available_list.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        refresh_button = ttk.Button(left_panel, text="🔄 Refresh List", command=self.refresh_available_list)
        refresh_button.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        # --- Right Panel: Jobs to be Booked ---
        right_panel = ttk.LabelFrame(self, text="Book for Courier")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right_panel.rowconfigure(1, weight=1)
        right_panel.columnconfigure(0, weight=1)

        ttk.Label(right_panel, text="Scan Job Reference Here:").grid(row=0, column=0, sticky="w", padx=5, pady=(0, 5))
        self.scan_entry = ttk.Entry(right_panel)
        self.scan_entry.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 5))
        self.scan_entry.bind("<Return>", self.add_to_booking_list)

        self.booking_list = tk.Listbox(right_panel)
        self.booking_list.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        self.book_button = ttk.Button(right_panel, text="Date Jobs as Booked", command=self.start_booking_batch)
        self.book_button.grid(row=2, column=0, sticky="ew", padx=5, pady=5)

        # --- Control Buttons Frame ---
        control_frame = ttk.Frame(right_panel)
        control_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=5)
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        control_frame.columnconfigure(2, weight=1)
        control_frame.columnconfigure(3, weight=1)

        self.pause_button = ttk.Button(control_frame, text="⏸ Pause", command=self.pause_automation, state=tk.DISABLED)
        self.pause_button.grid(row=0, column=0, sticky="ew", padx=2)

        self.continue_button = ttk.Button(control_frame, text="▶ Continue", command=self.continue_automation, state=tk.DISABLED)
        self.continue_button.grid(row=0, column=1, sticky="ew", padx=2)

        self.skip_button = ttk.Button(control_frame, text="⏭ Skip", command=self.skip_automation, state=tk.DISABLED)
        self.skip_button.grid(row=0, column=2, sticky="ew", padx=2)

        self.stop_button = ttk.Button(control_frame, text="⏹ Stop", command=self.stop_automation, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=3, sticky="ew", padx=2)

        # --- Status Label ---
        self.status_label = ttk.Label(right_panel, text="Status: Ready", anchor="center")
        self.status_label.grid(row=4, column=0, sticky="ew", padx=5, pady=5)

        # Load the initial list of available jobs
        self.refresh_available_list()

    def refresh_available_list(self):
        """Fetches and displays all open Milwaukee warranty jobs."""
        self.available_list.delete(0, tk.END)

        # Use our advanced search function to find the specific jobs
        results = db.search_jobs(search_term="Milwaukee", filters=["Open Warranties"])

        for job in results:
            self.available_list.insert(tk.END, job['job_ref'])

        self.controller.logger.info(f"Found {len(results)} available Milwaukee warranty jobs.")

    def add_to_booking_list(self, event=None):
        """Adds a scanned job reference to the booking list."""
        job_ref = self.scan_entry.get().strip().upper()
        if job_ref and job_ref not in self.booking_list.get(0, tk.END):
            self.booking_list.insert(tk.END, job_ref)
        self.scan_entry.delete(0, tk.END)

    def start_booking_batch(self):
        """Starts the automation to date the jobs in the booking list."""
        jobs_to_book = self.booking_list.get(0, tk.END)
        if not jobs_to_book:
            messagebox.showwarning("Empty List", "No jobs in the booking list to process.")
            return

        self.is_batch_running = True
        self.is_paused = False
        self.skip_current_job = False
        self.skip_event.clear()
        self.pause_event.clear()
        self.continue_event.clear()

        # Update UI
        self.book_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.NORMAL)
        self.skip_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL)
        self.continue_button.config(state=tk.DISABLED)
        self.status_label.config(text="Status: Running")

        self.current_automation_thread = threading.Thread(
            target=self._run_booking_thread,
            args=(list(jobs_to_book),),
            daemon=True
        )
        self.current_automation_thread.start()

    def pause_automation(self):
        """Pauses the automation and backtracks one step."""
        if self.is_batch_running and not self.is_paused:
            self.is_paused = True
            self.pause_event.set()
            # Skip the current job to effectively backtrack
            self.skip_event.set()
            self.status_label.config(text="Status: Paused (backtracked)")
            self.pause_button.config(state=tk.DISABLED)
            self.continue_button.config(state=tk.NORMAL)
            self.controller.logger.info("Automation paused and backtracked one step.")

    def continue_automation(self):
        """Resumes the automation from the current step."""
        if self.is_batch_running and self.is_paused:
            self.is_paused = False
            self.continue_event.set()
            self.status_label.config(text="Status: Running")
            self.pause_button.config(state=tk.NORMAL)
            self.continue_button.config(state=tk.DISABLED)
            self.controller.logger.info("Automation resumed.")

    def skip_automation(self):
        """Skips the current job and waits for user to continue."""
        if self.is_batch_running:
            self.skip_current_job = True
            self.skip_event.set()
            self.status_label.config(text="Status: Skipped current job")
            self.controller.logger.info("Skipping current job.")

    def stop_automation(self):
        """Stops the automation completely."""
        if self.is_batch_running:
            self.is_batch_running = False
            self.skip_event.set()  # Signal to stop the current job
            self.status_label.config(text="Status: Stopped")
            self.book_button.config(state=tk.NORMAL)
            self.pause_button.config(state=tk.DISABLED)
            self.continue_button.config(state=tk.DISABLED)
            self.skip_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.DISABLED)
            self.controller.logger.info("Automation stopped.")

    def _run_booking_thread(self, job_queue):
        """
        Runs the 'update_milw_sent_date.json' sequence for each job,
        logs the event, and updates the UI lists.
        """
        self.controller.logger.info(f"Starting booking batch for {len(job_queue)} jobs.")

        for job_ref in job_queue:
            if not self.is_batch_running:  # Check if stop button was pressed
                self.controller.logger.info("Automation stopped by user.")
                break

            # Update status label with current job
            self.master.after(0, self.status_label.config, {'text': f"Status: Processing {job_ref}"})

            data_context = {"job_ref": job_ref}

            # Run the automation to update the date in ADEN
            completion_event, success_event = self.controller.run_automation_sequence(
                "BookingMilwaukee.json",
                data_context,
                self.skip_event  # Pass the skip event to allow for early termination
            )

            # Wait for completion or pause
            while not completion_event.is_set():
                if self.pause_event.is_set():
                    # Pause was requested, wait for continue
                    self.controller.logger.info(f"Automation paused during job {job_ref}.")
                    # Clear the skip event if it was set by the pause button
                    if self.skip_event.is_set():
                        self.skip_event.clear()
                        self.controller.logger.info(f"Backtracked from job {job_ref}.")
                        # Don't break here, wait for continue button to be pressed

                    self.continue_event.wait()  # Wait until continue is pressed
                    self.pause_event.clear()
                    self.controller.logger.info(f"Automation resumed for job {job_ref}.")
                    self.continue_event.clear()  # Clear the continue event after resuming

                if self.skip_current_job:
                    # Skip was requested, break out of the current job
                    self.skip_current_job = False
                    self.skip_event.set()  # Signal to skip the current job
                    self.controller.logger.info(f"Skipping job {job_ref}.")
                    break

                time.sleep(0.1)  # Small sleep to prevent CPU hogging

            # Clear the skip event for the next job
            self.skip_event.clear()

            if success_event.is_set():
                # If the automation was successful, log the event in the database
                db.add_job_event(job_ref, "Courier Booking", f"Job booked with Milwaukee for courier collection.")
                self.controller.logger.info(f"Successfully booked job {job_ref}.")
            else:
                # If it failed, log it and skip to the next job
                self.controller.logger.error(f"Automation failed for job {job_ref}. It will not be marked as booked.")

        # After the loop, refresh the UI on the main thread
        self.master.after(0, self.booking_list.delete, 0, tk.END)
        self.master.after(0, self.refresh_available_list)

        # Reset state and update UI
        self.is_batch_running = False
        self.master.after(0, lambda: self.book_button.config(state=tk.NORMAL))
        self.master.after(0, lambda: self.pause_button.config(state=tk.DISABLED))
        self.master.after(0, lambda: self.continue_button.config(state=tk.DISABLED))
        self.master.after(0, lambda: self.skip_button.config(state=tk.DISABLED))
        self.master.after(0, lambda: self.stop_button.config(state=tk.DISABLED))
        self.master.after(0, lambda: self.status_label.config(text="Status: Ready"))
        self.controller.logger.info("Booking batch finished.")
