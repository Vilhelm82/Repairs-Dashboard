#!/usr/bin/env python3
# ui_tabs/job_indexer_tab.py

import tkinter as tk
from tkinter import ttk, messagebox
from core import db

class JobIndexerTab(ttk.Frame):
    """
    The JobIndexerTab provides a UI for searching and filtering all jobs
    in the database.
    """
    def __init__(self, parent, controller):
        super().__init__(parent, padding="10")
        self.controller = controller

        # --- UI Variable Initialization ---
        self.search_var = tk.StringVar()
        self.filter_completed_var = tk.BooleanVar()
        self.filter_warranty_var = tk.BooleanVar()
        self.filter_quotes_var = tk.BooleanVar()
        self.filter_parts_var = tk.BooleanVar()

        # --- Main Layout ---
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        # --- Search and Filter Frame ---
        controls_frame = ttk.Frame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        controls_frame.columnconfigure(1, weight=1)

        # Search Input
        ttk.Label(controls_frame, text="Search Input Field:").grid(row=0, column=0, padx=(0, 5), sticky="w")
        search_entry = ttk.Entry(controls_frame, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, sticky="ew")
        search_entry.bind("<Return>", lambda event: self.perform_search()) # Bind Enter key
        search_button = ttk.Button(controls_frame, text="SEARCH", command=self.perform_search)
        search_button.grid(row=0, column=2, sticky="e", padx=(5, 0))

        # Filter Checkboxes
        filter_frame = ttk.LabelFrame(self, text="Filter By:")
        filter_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10), padx=5)

        ttk.Checkbutton(filter_frame, text="Jobs Completed", variable=self.filter_completed_var).pack(side="left", padx=5)
        ttk.Checkbutton(filter_frame, text="Open Warranty", variable=self.filter_warranty_var).pack(side="left", padx=5)
        ttk.Checkbutton(filter_frame, text="Quotes", variable=self.filter_quotes_var).pack(side="left", padx=5)
        ttk.Checkbutton(filter_frame, text="Parts On Order", variable=self.filter_parts_var).pack(side="left", padx=5)

        # --- Results Table (Treeview) ---
        tree_frame = ttk.Frame(self)
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        columns = ("job_ref", "cust_no", "cust_name", "subject", "date")
        self.results_tree = ttk.Treeview(tree_frame, columns=columns, show="headings")

        self.results_tree.heading("job_ref", text="Job Reference")
        self.results_tree.heading("cust_no", text="Customer No.")
        self.results_tree.heading("cust_name", text="Customer Name")
        self.results_tree.heading("subject", text="Tool Subject")
        self.results_tree.heading("date", text="Date")

        self.results_tree.column("job_ref", width=100)
        self.results_tree.column("cust_no", width=100)
        self.results_tree.column("cust_name", width=200)
        self.results_tree.column("subject", width=150)
        self.results_tree.column("date", width=100)

        self.results_tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.results_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.results_tree.configure(yscrollcommand=scrollbar.set)

        self.results_tree.bind("<Double-1>", self.on_double_click)
        self.filter_completed_var.trace_add("write", lambda *args: self.perform_search())
        self.filter_warranty_var.trace_add("write", lambda *args: self.perform_search())
        self.filter_quotes_var.trace_add("write", lambda *args: self.perform_search())
        self.filter_parts_var.trace_add("write", lambda *args: self.perform_search())

    def perform_search(self):
        """
        Gathers search criteria from the UI, calls the database search function,
        and populates the results table.
        """
        search_term = self.search_var.get().strip()

        # Build the list of active status filters from the UI variables
        active_filters = []
        if self.filter_completed_var.get():
            active_filters.append("Jobs Completed")
        if self.filter_warranty_var.get():
            active_filters.append("Open Warranties")
        if self.filter_quotes_var.get():
            active_filters.append("Open Quote To Repair")
        if self.filter_parts_var.get():
            active_filters.append("Waiting on Parts")

        # Call the database function with the gathered criteria
        results = db.search_jobs(search_term, active_filters)

        # Clear the existing results from the tree before adding new ones
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        # Populate the tree with the new results
        for job in results:
            self.results_tree.insert("", "end", values=(
                job.get("job_ref", ""),
                job.get("customer_no", ""),
                job.get("customer_name", ""),
                job.get("tool_subject", ""),
                job.get("job_date", "")
            ))
    def on_double_click(self, event):
        """Callback function to handle double-clicks on the results table."""
        selected_item = self.results_tree.selection()
        if not selected_item:
            return

        job_ref = self.results_tree.item(selected_item[0], "values")[0]
        if job_ref:
            self.controller.switch_to_card_view(job_ref)
