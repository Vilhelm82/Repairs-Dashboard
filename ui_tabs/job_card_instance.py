#!/usr/bin/env python3
# ui_tabs/job_card_instance.py

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from datetime import datetime
from core import db


class JobCardInstance(ttk.Frame):
    """
    Represents the content of a single, dynamic job card tab.
    Contains all UI elements and logic for one job.
    """

    def __init__(self, parent, controller, job_ref: str, close_command):
        super().__init__(parent)
        self.controller = controller
        self.job_ref = job_ref
        self.current_customer_id = None

        # --- UI Variable Initialization ---
        self.job_ref_var = tk.StringVar(value=job_ref)
        self.job_class_var = tk.StringVar()
        self.customer_no_var = tk.StringVar()
        self.customer_name_var = tk.StringVar()
        self.dop_var = tk.StringVar()
        self.tool_subject_var = tk.StringVar()
        self.total_jobs_var = tk.StringVar(value="Total Jobs to date: 0")

        # --- Main Layout (2 columns) ---
        self.columnconfigure(0, weight=1, minsize=300)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)
        # --- Add the 'x' close button to the top-right corner ---
        close_button = ttk.Button(
            self,
            text="✕",
            command=close_command,
            style="Toolbutton"
        )
        close_button.place(relx=1.0, rely=0, anchor="ne")  # Place in top-right corner

        # --- Left Side ---
        left_panel = ttk.Frame(self)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        left_panel.rowconfigure(1, weight=1)
        left_panel.columnconfigure(0, weight=1)

        info_frame = ttk.LabelFrame(left_panel, text="Job Card Information")
        info_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        info_frame.columnconfigure(1, weight=1)

        ttk.Label(info_frame, text="Job Reference:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(info_frame, textvariable=self.job_ref_var, state="readonly").grid(row=0, column=1, sticky="ew",
                                                                                    padx=5, pady=2)
        ttk.Label(info_frame, text="Job Class:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(info_frame, textvariable=self.job_class_var).grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(info_frame, text="Customer Number:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(info_frame, textvariable=self.customer_no_var).grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(info_frame, text="Customer Name:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(info_frame, textvariable=self.customer_name_var).grid(row=3, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(info_frame, text="Date Job Created:").grid(row=4, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(info_frame, textvariable=self.dop_var).grid(row=4, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(info_frame, text="Tool Subject:").grid(row=5, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(info_frame, textvariable=self.tool_subject_var).grid(row=5, column=1, sticky="ew", padx=5, pady=2)
        ttk.Button(info_frame, text="Update DB", command=self.update_job_details).grid(row=6, column=1, sticky="e",
                                                                                       pady=5, padx=5)

        notes_frame = ttk.LabelFrame(left_panel, text="Job Notes")
        notes_frame.grid(row=1, column=0, sticky="nsew")
        notes_frame.rowconfigure(0, weight=1)
        notes_frame.columnconfigure(0, weight=1)
        self.notes_text = ScrolledText(notes_frame, wrap="word", font=("Segoe UI", 10))
        self.notes_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # --- Right Side ---
        right_panel = ttk.Frame(self)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        right_panel.rowconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=0)
        right_panel.columnconfigure(0, weight=1)

        index_frame = ttk.LabelFrame(right_panel, text="Information Index")
        index_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        index_frame.rowconfigure(0, weight=1)
        index_frame.columnconfigure(0, weight=1)

        self.info_notebook = ttk.Notebook(index_frame)
        self.info_notebook.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        stats_tab = ttk.Frame(self.info_notebook)
        self.info_notebook.add(stats_tab, text="Customer Stats")
        stats_tab.columnconfigure(0, weight=1)
        stats_tab.rowconfigure(1, weight=1)
        ttk.Label(stats_tab, textvariable=self.total_jobs_var).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.customer_jobs_tree = ttk.Treeview(stats_tab, columns=("ref", "date", "status"), show="headings")
        self.customer_jobs_tree.heading("ref", text="Job Ref")
        self.customer_jobs_tree.heading("date", text="Date")
        self.customer_jobs_tree.heading("status", text="Status")
        self.customer_jobs_tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.customer_jobs_tree.bind("<Double-1>", self.on_double_click)

        # Invoice History Tab
        invoice_tab = ttk.Frame(self.info_notebook)
        self.info_notebook.add(invoice_tab, text="Invoice History")
        ttk.Label(invoice_tab, text="Invoice history will be implemented here.").pack(padx=5, pady=5)

        # General Notes Tab
        notes_tab = ttk.Frame(self.info_notebook)
        self.info_notebook.add(notes_tab, text="Notes")
        notes_tab.rowconfigure(0, weight=1)
        notes_tab.columnconfigure(0, weight=1)
        self.customer_notes_text = ScrolledText(notes_tab, wrap="word", font=("Segoe UI", 10))
        self.customer_notes_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Add a button to save the notes
        notes_button_frame = ttk.Frame(notes_tab)
        notes_button_frame.grid(row=1, column=0, pady=(5, 0), sticky="ew")
        ttk.Button(notes_button_frame, text="Save Notes", command=self.save_customer_notes).pack(side="right", padx=5, pady=5)

        # --- Bottom-Right: Move Job Panel ---
        move_frame = ttk.LabelFrame(right_panel, text="Move Job To...")
        move_frame.grid(row=1, column=0, sticky="sew")
        move_frame.columnconfigure(0, weight=1)
        status_options = ["Waiting on parts", "Open Quote To Repair", "Waiting on customer/quote", "Jobs Completed", "Open Warranties", "Batteries Under Eval", "Outsourced Jobs", "Milwaukee Warranty", "Miscellaneous"]
        self.status_combobox = ttk.Combobox(move_frame, values=status_options, state="readonly")
        self.status_combobox.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.status_combobox.bind("<<ComboboxSelected>>", self.on_status_change)

        # Load this instance's data
        self.load_card_data()

    def load_card_data(self):
        """Loads and populates the data for this specific job instance."""
        data = db.get_job_by_ref(self.job_ref)
        if not data:
            # This might happen if the job was deleted elsewhere
            self.controller.logger.error(f"Could not load data for job {self.job_ref}")
            return

        self.job_class_var.set(data.get('job_class_cond', ''))
        self.customer_no_var.set(data.get('customer_no', ''))
        self.customer_name_var.set(data.get('customer_name', ''))
        self.dop_var.set(data.get('job_date', ''))
        self.tool_subject_var.set(data.get('tool_subject', ''))
        self.notes_text.delete("1.0", tk.END)
        self.notes_text.insert("1.0", data.get("description", ""))

        self.current_customer_id = data.get('customer_id')
        if self.current_customer_id:
            self.populate_customer_info()

            # Load customer notes if available
            customer_data = db.get_customer_by_job_ref(self.job_ref)
            if customer_data and 'general_notes' in customer_data:
                try:
                    if hasattr(self, 'customer_notes_text'):
                        self.customer_notes_text.delete("1.0", tk.END)
                        self.customer_notes_text.insert("1.0", customer_data.get("general_notes", ""))
                except tk.TclError:
                    self.controller.logger.error("Failed to update customer notes text widget")

    def populate_customer_info(self):
        """Fills the right-side panel with data for the current customer."""
        if not self.current_customer_id: return

        # Stats tab
        customer_jobs = db.get_jobs_by_customer_id(self.current_customer_id)
        self.total_jobs_var.set(f"Total Jobs to date: {len(customer_jobs)}")

        # Clear previous entries
        for item in self.customer_jobs_tree.get_children():
            self.customer_jobs_tree.delete(item)

        for job in customer_jobs:
            self.customer_jobs_tree.insert("", "end", values=(job['job_ref'], job['job_date'], job['overview_status']))

    def update_job_details(self):
        """Gathers data from the UI and calls the database update function."""
        job_ref = self.job_ref_var.get()
        if not job_ref or job_ref == "N/A":
            messagebox.showerror("Error", "No job loaded to update.")
            return

        # We need to get the current overview_status to avoid overwriting it
        original_data = db.get_job_by_ref(job_ref)
        overview_status = original_data.get('overview_status', '')

        # Gather all the data from the entry fields
        updated_data = {
            "customer_no": self.customer_no_var.get(),
            "customer_name": self.customer_name_var.get(),
            "job_date": self.dop_var.get(),
            "description": self.notes_text.get("1.0", tk.END).strip(),
            "job_class_cond": self.job_class_var.get(),
            "tool_subject": self.tool_subject_var.get(),
            "overview_status": overview_status  # Preserve the existing status
        }

        # Call the new database function
        db.update_job_record(job_ref, updated_data)

        messagebox.showinfo("Success", f"Job {job_ref} has been updated in the database.")

        # Refresh other parts of the UI to reflect the changes
        self.controller.refresh_all_views()
        self.populate_customer_info()  # Re-populate the customer job list

    def ask_for_date(self, title, prompt, initial_value):
        """Custom dialog for date selection that appears in front of the main window."""
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self.controller.root)  # Set to be on top of the main window
        dialog.grab_set()  # Make the dialog modal

        # Position the dialog in the center of the main window
        x = self.controller.root.winfo_x() + (self.controller.root.winfo_width() // 2) - 150
        y = self.controller.root.winfo_y() + (self.controller.root.winfo_height() // 2) - 50
        dialog.geometry(f"300x100+{x}+{y}")

        # Create the dialog content
        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=prompt).pack(pady=(0, 5))

        date_var = tk.StringVar(value=initial_value)
        date_entry = ttk.Entry(frame, textvariable=date_var, width=20)
        date_entry.pack(pady=5)
        date_entry.select_range(0, 'end')
        date_entry.focus_set()

        result = [None]  # Use a list to store the result

        def on_ok():
            result[0] = date_var.get()
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill="x", pady=(5, 0))

        ttk.Button(button_frame, text="OK", command=on_ok).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side="right")

        # Make the dialog appear in front of everything
        dialog.lift()
        dialog.attributes("-topmost", True)

        # Wait for the dialog to be closed
        self.wait_window(dialog)

        return result[0]

    def on_status_change(self, event):
        """Called when a new status is selected from the combobox."""
        new_status = self.status_combobox.get()
        job_ref = self.job_ref_var.get()
        if not job_ref or job_ref == "N/A":
            messagebox.showerror("Error", "No job loaded.")
            self.status_combobox.set('')
            return

        parts_date = None
        if new_status == "Waiting on parts":
            today_date = datetime.now().strftime("%d/%m/%Y")
            parts_date = self.ask_for_date("Parts Ordered", "Enter date parts were ordered:", today_date)
            if not parts_date:  # User cancelled
                self.status_combobox.set('')
                return

        db.update_job_status(job_ref, new_status, parts_ordered_date=parts_date)
        messagebox.showinfo("Status Updated", f"Job {job_ref} has been moved to '{new_status}'.")
        self.controller.refresh_all_views()
        self.status_combobox.set('')  # Reset combobox

    def on_double_click(self, event):
        """Callback function to handle double-clicks on the customer job list."""
        selected_item = self.customer_jobs_tree.selection()
        if not selected_item:
            return

        job_ref = self.customer_jobs_tree.item(selected_item[0], "values")[0]
        if job_ref:
            # We are already on the card view, so just load the new card
            self.controller.card_ref_var.set(job_ref)
            self.controller.load_card_by_ref()

    def save_customer_notes(self):
        """Saves the customer notes from the Notes tab to the database."""
        if not self.current_customer_id:
            messagebox.showerror("Error", "No customer associated with this job.")
            return

        notes_text = self.customer_notes_text.get("1.0", tk.END).strip()

        # Save the notes to the database
        success = db.update_customer_notes(self.current_customer_id, notes_text)

        if success:
            messagebox.showinfo("Success", "Customer notes have been saved.")
        else:
            messagebox.showerror("Error", "Failed to save customer notes.")

