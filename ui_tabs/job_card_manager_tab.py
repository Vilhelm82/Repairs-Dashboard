#!/usr/bin/env python3
# ui_tabs/job_card_manager_tab.py

import tkinter as tk
from tkinter import ttk
from .job_card_instance import JobCardInstance
from utils.debug_ui_widgets import RightClickMenu


class JobCardManagerTab(ttk.Frame):
    """
    Manages a dynamic notebook of closable job card tabs.
    """

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Dictionary to track open tabs: {job_ref: tab_widget}
        self.open_tabs = {}

        # The inner notebook that will hold individual job cards
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # --- Right-Click Menu for Closing Tabs ---
        self.tab_menu = RightClickMenu(self)
        self.tab_menu.add_command(label="Close Tab", command=self.close_current_tab)
        self.notebook.bind("<Button-3>", self.show_tab_context_menu)

    def add_or_focus_tab(self, job_ref: str):
        """
        Adds a new job card tab if it's not already open,
        otherwise focuses the existing tab.
        """
        # If tab is already open, just select it
        if job_ref in self.open_tabs:
            tab_widget = self.open_tabs[job_ref]
            self.notebook.select(tab_widget)
            return

        # If tab is not open, create a new one
        self.controller.logger.info(f"Opening new job card tab for {job_ref}")

        # Create the content of the tab using our JobCardInstance class
        # Pass a command to the instance so it can call back to close itself
        content_frame = JobCardInstance(
            self.notebook,
            self.controller,
            job_ref,
            close_command=lambda: self.close_tab_by_ref(job_ref)
        )

        # Add the new frame to the notebook with the job_ref as its title
        self.notebook.add(content_frame, text=job_ref)
        self.notebook.select(content_frame)  # Select the newly created tab

        # Store a reference to the new tab
        self.open_tabs[job_ref] = content_frame

    def close_current_tab(self):
        """Closes the currently selected tab in the notebook."""
        try:
            selected_tab_widget = self.notebook.nametowidget(self.notebook.select())

            # Find the job_ref associated with this widget
            job_ref_to_close = None
            for ref, widget in self.open_tabs.items():
                if widget == selected_tab_widget:
                    job_ref_to_close = ref
                    break

            if job_ref_to_close:
                self.close_tab_by_ref(job_ref_to_close)

        except tk.TclError:
            # This can happen if no tabs are open
            pass

    def close_tab_by_ref(self, job_ref: str):
        """Closes a specific tab using its job reference."""
        if job_ref in self.open_tabs:
            self.controller.logger.info(f"Closing job card tab for {job_ref}")
            tab_widget = self.open_tabs[job_ref]
            self.notebook.forget(tab_widget)  # Remove tab from view
            del self.open_tabs[job_ref]  # Remove from our tracking dictionary

    def show_tab_context_menu(self, event):
        """Identifies which tab was right-clicked and shows the context menu."""
        try:
            # Identify the tab index under the cursor
            tab_id = self.notebook.identify(event.x, event.y)
            if tab_id is not None and "tab" in tab_id:
                # Select the tab that was right-clicked
                tab_index = self.notebook.index(f"@{event.x},{event.y}")
                self.notebook.select(tab_index)
                self.tab_menu.show(event)
        except tk.TclError:
            # This can happen if the click is not on a tab
            pass