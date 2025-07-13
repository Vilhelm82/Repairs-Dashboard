#!/usr/bin/env python3
# ui_tabs/tag_manager_tab.py

import tkinter as tk
from tkinter import ttk, messagebox
from core import db


class TagManagerTab(ttk.Frame):
    """
    The TagManagerTab provides a UI for users to add, view, and delete
    the keywords used for the Smart Tagging system.
    """

    def __init__(self, parent, controller):
        super().__init__(parent, padding="10")
        self.controller = controller

        # --- Main Layout (2 columns) ---
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # --- Left Panel: List of existing tags ---
        list_frame = ttk.LabelFrame(self, text="Current Keywords")
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.tags_listbox = tk.Listbox(list_frame, selectmode="extended")
        self.tags_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # --- Right Panel: Management controls ---
        controls_frame = ttk.Frame(self)
        controls_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        add_frame = ttk.LabelFrame(controls_frame, text="Add New Keyword")
        add_frame.pack(fill="x", pady=(0, 10))
        add_frame.columnconfigure(0, weight=1)

        self.new_tag_entry = ttk.Entry(add_frame)
        self.new_tag_entry.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.new_tag_entry.bind("<Return>", self.add_new_tag)

        ttk.Button(add_frame, text="Add Keyword", command=self.add_new_tag).grid(row=0, column=1, padx=5, pady=5)

        delete_frame = ttk.LabelFrame(controls_frame, text="Manage Selected")
        delete_frame.pack(fill="x")
        ttk.Button(delete_frame, text="Delete Selected Keyword(s)", command=self.delete_selected_tag).pack(fill="x",
                                                                                                           padx=5,
                                                                                                           pady=5)

        # Load initial data
        self.refresh_tags_list()

    def refresh_tags_list(self):
        """Clears and re-populates the listbox with all tags from the database."""
        self.tags_listbox.delete(0, tk.END)
        all_tags = db.get_all_tags()
        for tag in all_tags:
            self.tags_listbox.insert(tk.END, tag)
        self.controller.logger.info("Tag manager list refreshed.")

    def add_new_tag(self, event=None):
        """Adds a new tag from the entry box to the database."""
        new_tag = self.new_tag_entry.get().strip()
        if not new_tag:
            messagebox.showwarning("Empty Tag", "Cannot add an empty keyword.")
            return

        db.add_tag(new_tag)
        self.new_tag_entry.delete(0, tk.END)
        self.refresh_tags_list()

    def delete_selected_tag(self):
        """Deletes the selected tag(s) from the database."""
        selected_indices = self.tags_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select one or more keywords to delete.")
            return

        tags_to_delete = [self.tags_listbox.get(i) for i in selected_indices]

        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete the following {len(tags_to_delete)} keyword(s)?\n\n" + "\n".join(
                tags_to_delete)
        )

        if confirm:
            for tag in tags_to_delete:
                db.delete_tag(tag)
            self.refresh_tags_list()