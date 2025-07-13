#!/usr/bin/env python3
# ui_tabs/overview_tab.py

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

from core import db

class OverviewTab(ttk.Frame):
    """
    The OverviewTab class is responsible for displaying a dashboard of jobs
    categorized by their status.
    """

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # --- UI Initialization ---
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Add a top frame for the buttons ---
        top_bar = ttk.Frame(self)
        top_bar.grid(row=0, column=0, columnspan=5, pady=(5, 10))

        # Create a frame for the buttons
        button_frame = ttk.Frame(top_bar)
        button_frame.pack()

        refresh_button = ttk.Button(button_frame, text="🔄 Refresh Data", command=self.refresh_data)
        refresh_button.pack(side='left', padx=5)

        cleanup_button = ttk.Button(button_frame, text="🧹 Clean Database", command=self.cleanup_database)
        cleanup_button.pack(side='left', padx=5)

        delete_button = ttk.Button(button_frame, text="🗑️ Delete from Database", command=self.delete_job_from_ui)
        delete_button.pack(side='left', padx=5)

        # Create a notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, columnspan=5, sticky="nsew")

        # Create the main tab
        self.main_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="Main Overview")

        # Create the special tab
        self.special_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.special_tab, text="Special Categories")

        # Configure both tabs
        self.main_tab.grid_rowconfigure(0, weight=1)
        self.special_tab.grid_rowconfigure(0, weight=1)

        # --- The main content frame that holds the columns for the main tab ---
        content_frame = ttk.Frame(self.main_tab)
        content_frame.grid(row=0, column=0, columnspan=5, sticky="nsew")
        content_frame.grid_rowconfigure(0, weight=1)

        # --- The special content frame that holds the columns for the special tab ---
        special_content_frame = ttk.Frame(self.special_tab)
        special_content_frame.grid(row=0, column=0, columnspan=4, sticky="nsew")
        special_content_frame.grid_rowconfigure(0, weight=1)

        # Main tab columns
        columns = {
            "Open Warranties": "Open Warranties",
            "Open Quote To Repair": "Open Quote To Repair",
            "Waiting on Parts": "Waiting on Parts",  # Exact match needed
            "Waiting on Customer/Quote": "Waiting on Customer/Quote",
            "Jobs Completed": "Jobs Completed"
        }

        # Special tab columns
        special_columns = {
            "Batteries Under Eval": "Batteries Under Eval",
            "Outsourced Jobs": "Outsourced Jobs",
            "Milwaukee Warranty": "Milwaukee Warranty",
            "Miscellaneous": "Miscellaneous"
        }

        self.overview_trees = {}

        # Setup main tab columns
        for i, (title, status) in enumerate(columns.items()):
            content_frame.grid_columnconfigure(i, weight=1)
            self._create_column(content_frame, i, title, status)

        # Setup special tab columns
        for i, (title, status) in enumerate(special_columns.items()):
            special_content_frame.grid_columnconfigure(i, weight=1)
            self._create_column(special_content_frame, i, title, status)

    def _create_column(self, parent_frame, column_index, title, status):
        """Helper method to create a column with a treeview for a specific status."""
        col_frame = ttk.LabelFrame(parent_frame, text=title, padding=5)
        col_frame.grid(row=0, column=column_index, sticky="nsew", padx=5, pady=5)
        col_frame.grid_rowconfigure(0, weight=1)
        col_frame.grid_columnconfigure(0, weight=1)

        # For "Waiting on Parts", add a second date column
        if status == "Waiting on Parts":
            tree = ttk.Treeview(col_frame, columns=("ref", "date", "parts_date"), show="headings")
            tree.heading("ref", text="Job Reference")
            tree.heading("date", text="Created")
            tree.heading("parts_date", text="Parts Ordered")
            tree.column("ref", width=80, anchor="w")
            tree.column("date", width=80, anchor="center")
            tree.column("parts_date", width=80, anchor="center")
        else:
            tree = ttk.Treeview(col_frame, columns=("ref", "date"), show="headings")
            tree.heading("ref", text="Job Reference")
            tree.heading("date", text="Date")
            tree.column("ref", width=100, anchor="w")
            tree.column("date", width=80, anchor="center")

        tree.tag_configure('green', background='#90EE90', foreground='black')
        tree.tag_configure('yellow', background='#FFFFE0', foreground='black')
        tree.tag_configure('red', background='#FFC0CB', foreground='black')
        tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(col_frame, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)

        tree.bind("<Double-1>", self.on_double_click)

        self.overview_trees[status] = tree

    def refresh_data(self):
        """
        Clears and repopulates all the treeviews with the latest data from the database.
        """
        # Add debug inspection here
        db.inspect_job_status()

        for tree in self.overview_trees.values():
            tree.delete(*tree.get_children())

        all_jobs = db.get_all_jobs(full=True)

        def sort_key(job):
            try:
                job_date_str = job.get('job_date', '')
                if not job_date_str: return datetime.max
                for fmt in ("%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(job_date_str, fmt)
                    except ValueError:
                        continue
                return datetime.max
            except (ValueError, TypeError):
                return datetime.max

        all_jobs.sort(key=sort_key)

        for job in all_jobs:
            status = job.get("overview_status")
            if status in self.overview_trees:
                tree = self.overview_trees[status]
                color_tag = self._get_job_age_color(job.get("job_date"))

                # Insert data based on whether it's the special 'Waiting on Parts' column
                if status == "Waiting on Parts":
                    parts_color_tag = self._get_job_age_color(job.get("parts_ordered_date"))
                    final_color_tag = parts_color_tag if job.get("parts_ordered_date") else color_tag
                    tree.insert("", "end", values=(
                        job.get("job_ref", ""),
                        job.get("job_date", ""),
                        job.get("parts_ordered_date", "")),
                                tags=(final_color_tag,)
                                )
                else:
                    tree.insert("", "end", values=(
                        job.get("job_ref", ""),
                        job.get("job_date", "")),
                                tags=(color_tag,)
                                )


    def _get_job_age_color(self, job_date_str):
        """Helper method to determine the color tag based on the job's age."""
        if not job_date_str: return ""
        try:
            job_date = None
            # Extended date format parsing
            for fmt in ("%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
                try:
                    job_date = datetime.strptime(job_date_str, fmt)
                    break
                except ValueError:
                    continue

            if not job_date: return ""

            age = datetime.now() - job_date
            if age <= timedelta(days=14): return "green"
            elif age <= timedelta(days=28): return "yellow"
            else: return "red"
        except Exception:
            return ""
    def on_double_click(self, event):
        """Callback function to handle double-clicks on any of the treeviews."""
        # 'event.widget' refers to the specific treeview that was clicked
        tree = event.widget
        selected_item = tree.selection()
        if not selected_item:
            return

        # The job reference is the first value in the selected row
        job_ref = tree.item(selected_item[0], "values")[0]
        if job_ref:
            self.controller.switch_to_card_view(job_ref)
    def cleanup_database(self):
        """Runs the database cleanup function and refreshes the view."""
        if messagebox.askyesno("Confirm Database Cleanup", 
                              "This will standardize all status labels and clean up job references.\n"
                              "Do you want to continue?"):
            try:
                db.fix_database_records()
                messagebox.showinfo("Success", "Database cleanup completed successfully!")
                self.refresh_data()  # Refresh the view after cleanup
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clean up database: {str(e)}")

    def delete_job_from_ui(self):
        """Deletes the selected job from the database after confirmation."""
        # Check all treeviews for a selected item
        selected_job_ref = None
        selected_tree = None

        for status, tree in self.overview_trees.items():
            selected_items = tree.selection()
            if selected_items:
                # Get the job reference from the first column
                selected_job_ref = tree.item(selected_items[0], "values")[0]
                selected_tree = tree
                break

        if not selected_job_ref:
            messagebox.showinfo("No Selection", "Please select a job to delete.")
            return

        # Show confirmation dialog
        if messagebox.askyesno("Confirm Deletion", 
                              f"Are you sure you want to delete job {selected_job_ref} from the database?\n"
                              "This action cannot be undone."):
            try:
                # Call the database function to delete the job
                success = db.delete_job(selected_job_ref)

                if success:
                    # Remove the item from the treeview
                    selected_tree.delete(selected_items[0])
                    messagebox.showinfo("Success", f"Job {selected_job_ref} has been deleted from the database.")

                    # Refresh all views to ensure consistency
                    self.controller.refresh_all_views()
                else:
                    messagebox.showerror("Error", f"Failed to delete job {selected_job_ref}.")
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred while deleting the job: {str(e)}")
