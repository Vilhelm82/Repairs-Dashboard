#!/usr/bin/env python3
# ui_tabs/calendar_tab.py

from datetime import datetime
import tkinter as tk
from tkinter import ttk
from core import db

class CalendarTab(ttk.Frame):
    """
    A UI tab that displays a calendar with job-related events shown directly in the calendar cells.
    Each job reference is displayed with a color indicating its event type.
    """

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # --- Main Layout (single column) ---
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # --- Calendar Widget ---
        calendar_frame = ttk.Frame(self, padding="10")
        calendar_frame.grid(row=0, column=0, sticky="nsew")

        # Replace tkcalendar with a basic calendar implementation
        self.calendar_widget = BasicCalendar(calendar_frame)
        self.calendar_widget.controller = self.controller  # Pass the controller
        self.calendar_widget.on_date_selected_callback = self.on_date_selected  # Set callback
        self.calendar_widget.pack(fill="both", expand=True)

        # Add a refresh button
        refresh_button = ttk.Button(calendar_frame, text="🔄 Refresh Calendar", command=self.highlight_event_days)
        refresh_button.pack(pady=10)

        # Initial load
        self.highlight_event_days()

    def highlight_event_days(self):
        """Highlights days that have events in the calendar."""
        # Get all events from the database for the current month
        current_date = self.calendar_widget.current_date
        start_date = datetime(current_date.year, current_date.month, 1)
        if current_date.month == 12:
            end_date = datetime(current_date.year + 1, 1, 1)
        else:
            end_date = datetime(current_date.year, current_date.month + 1, 1)

        # Query the database for events between these dates
        events = db.get_events_between_dates(start_date, end_date)

        # Create a set of days that have events
        event_days = set()
        for event in events:
            try:
                # Parse the event_date string into a datetime object
                event_date = datetime.strptime(event['event_date'], "%Y-%m-%d")
                event_days.add(event_date.day)
            except (ValueError, KeyError):
                continue

        # Update the calendar display to highlight these days
        for widget in self.calendar_widget.calendar_frame.winfo_children()[7:]:  # Skip headers
            if isinstance(widget, ttk.Frame):  # Changed from Button to Frame
                try:
                    day_label = widget.winfo_children()[0]  # Get the date label
                    day = int(day_label['text'])
                    if day in event_days:
                        widget.has_events = True
                        widget.configure(style='Accent.TFrame')
                    else:
                        widget.has_events = False
                        # Only reset style if it's not the selected date
                        if not hasattr(widget, 'date') or (self.calendar_widget.selected_date and 
                                                          widget.date.day != self.calendar_widget.selected_date.day):
                            widget.configure(style='TFrame')

                    # Preserve bold font for selected date
                    if hasattr(widget, 'date') and self.calendar_widget.selected_date and widget.date.day == self.calendar_widget.selected_date.day:
                        day_label.configure(font=('Calibri', 10, 'bold'))
                    else:
                        day_label.configure(font=('Calibri', 10))
                except (ValueError, IndexError):
                    continue

        # No need to update events list as it has been removed

    def on_date_selected(self, date):
        """Handle date selection from the calendar widget"""
        # This method is kept as a callback for the calendar widget
        # but no longer needs to update an events list
        pass

    def refresh_calendar(self):
        """Public method to refresh the calendar view"""
        self.calendar_widget.update_calendar()
        self.highlight_event_days()

class BasicCalendar(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.current_date = datetime.now()
        self.selected_date = None
        self.controller = None
        self.on_date_selected_callback = None  # Callback for date selection

        # Define status colors
        self.status_colors = {
            "Job Imported": "#0000FF",  # Blue
            "Waiting on Parts": "#FFA500",  # Orange
            "Waiting on Customer/Quote": "#800080",  # Purple
            "Jobs Completed": "#008000",  # Green
            "Open Quote To Repair": "#FFD700",  # Yellow
            "Open Warranties": "#FF69B4",  # Hot Pink
            "Batteries Under Eval": "#8A2BE2",  # Blue Violet
            "Outsourced Jobs": "#20B2AA",  # Light Sea Green
            "Milwaukee Warranty": "#FF0000",  # Red
            "Miscellaneous": "#708090",  # Slate Gray
            "Status Change": "#A9A9A9"  # Dark Gray (fallback for any status changes)
        }

        # Navigation frame
        nav_frame = ttk.Frame(self)
        nav_frame.pack(fill="x", pady=5)

        ttk.Button(nav_frame, text="<", command=self.prev_month).pack(side="left")
        self.month_label = ttk.Label(nav_frame, text="")
        self.month_label.pack(side="left", padx=10)
        ttk.Button(nav_frame, text=">", command=self.next_month).pack(side="left")

        # Calendar frame with grid
        self.calendar_frame = ttk.Frame(self)
        self.calendar_frame.pack(fill="both", expand=True)

        # Configure grid
        for i in range(7):
            self.calendar_frame.columnconfigure(i, weight=1, uniform="col")

        # Weekday headers
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(weekdays):
            lbl = ttk.Label(self.calendar_frame, text=day, anchor="center")
            lbl.grid(row=0, column=i, sticky="nsew")

        self.update_calendar()

    def update_calendar(self):
        # Clear previous calendar cells (except headers)
        for widget in self.calendar_frame.grid_slaves():
            if int(widget.grid_info()["row"]) > 0:
                widget.destroy()

        # Update month label
        self.month_label.config(text=self.current_date.strftime("%B %Y"))

        # Calculate calendar dates
        first_day = datetime(self.current_date.year, self.current_date.month, 1)
        if self.current_date.month == 12:
            next_month = datetime(self.current_date.year + 1, 1, 1)
        else:
            next_month = datetime(self.current_date.year, self.current_date.month + 1, 1)
        days_in_month = (next_month - first_day).days
        start_weekday = first_day.weekday()

        # Calculate number of rows needed for the calendar
        num_rows = (start_weekday + days_in_month + 6) // 7

        # Configure rows with uniform weight
        for i in range(1, num_rows + 1):
            self.calendar_frame.rowconfigure(i, weight=1, uniform="row")

        # Create calendar grid
        for i in range(days_in_month):
            day = i + 1
            row = (start_weekday + i) // 7 + 1
            col = (start_weekday + i) % 7

            # Create day frame
            day_frame = ttk.Frame(self.calendar_frame, relief="solid", borderwidth=1)
            day_frame.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)
            day_frame.rowconfigure(1, weight=1)
            day_frame.columnconfigure(0, weight=1)

            # Set minimum size for consistent appearance
            day_frame.grid_propagate(False)  # Prevent frame from shrinking to fit contents
            day_frame.configure(width=80, height=80)  # Set minimum dimensions

            # Store the date in the frame for later use
            day_date = datetime(self.current_date.year, self.current_date.month, day)
            day_frame.date = day_date

            # Date label
            day_label = ttk.Label(day_frame, text=str(day))
            day_label.grid(row=0, column=0, sticky="nw", padx=2)

            # Bind click events to select the date
            day_frame.bind("<Button-1>", lambda e, df=day_frame: self.select_date(df))
            day_label.bind("<Button-1>", lambda e, df=day_frame: self.select_date(df))

            # Event display area (Text widget for colored text)
            event_text = tk.Text(day_frame, wrap="word", height=3)  # Fixed height for uniform appearance
            event_text.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 2))

            # Get and display events
            date = datetime(self.current_date.year, self.current_date.month, day)
            events = db.get_events_for_date(date.strftime("%Y-%m-%d"))

            # Process events and add colored job references
            for event in events:
                job_ref = event['job_ref']
                event_type = event['event_type']
                # Use the color from status_colors if available, otherwise use a default color
                color = self.status_colors.get(event_type, "#000000")  # Default to black if no color defined
                event_text.tag_configure(f"color_{job_ref}", foreground=color)
                event_text.insert("end", f"{job_ref}\n", f"color_{job_ref}")
                # Create a new function that captures the current value of job_ref
                def create_callback(ref):
                    return lambda e, job_ref=ref: self.on_double_click(job_ref)
                # Bind the event with the created callback
                event_text.tag_bind(f"color_{job_ref}", "<Double-Button-1>", create_callback(job_ref))

            # Configure text widget
            event_text.configure(state="disabled")  # Keep fixed height set earlier

    def prev_month(self):
        if self.current_date.month == 1:
            self.current_date = self.current_date.replace(year=self.current_date.year-1, month=12)
        else:
            self.current_date = self.current_date.replace(month=self.current_date.month-1)
        self.update_calendar()

    def next_month(self):
        if self.current_date.month == 12:
            self.current_date = self.current_date.replace(year=self.current_date.year+1, month=1)
        else:
            self.current_date = self.current_date.replace(month=self.current_date.month+1)
        self.update_calendar()

    def on_double_click(self, job_ref):
        """Handle double-click on job reference"""
        if hasattr(self, "controller"):
            self.controller.switch_to_card_view(job_ref)

    def select_date(self, day_frame):
        """Handle date selection in the calendar"""
        # Update the selected date
        self.selected_date = day_frame.date

        # Highlight the selected day
        for widget in self.calendar_frame.winfo_children()[7:]:  # Skip headers
            if isinstance(widget, ttk.Frame):
                if widget == day_frame:
                    # Always highlight the selected day with a different style
                    widget.configure(style='Accent.TFrame')
                    # Add a visual indicator for the selected date
                    if len(widget.winfo_children()) > 0:
                        day_label = widget.winfo_children()[0]
                        day_label.configure(font=('Calibri', 10, 'bold'))
                elif hasattr(widget, 'has_events') and widget.has_events:
                    # Keep the highlight for days with events
                    widget.configure(style='Accent.TFrame')
                    # Reset font for non-selected days
                    if len(widget.winfo_children()) > 0:
                        day_label = widget.winfo_children()[0]
                        day_label.configure(font=('Calibri', 10))
                else:
                    # Remove highlight from days without events
                    widget.configure(style='TFrame')
                    # Reset font for non-selected days
                    if len(widget.winfo_children()) > 0:
                        day_label = widget.winfo_children()[0]
                        day_label.configure(font=('Calibri', 10))

        # Call the callback if it exists
        if self.on_date_selected_callback:
            self.on_date_selected_callback(self.selected_date)

    def refresh_calendar(self):
        """Refresh the calendar display"""
        # Completely rebuild the calendar to ensure all events have the correct colors
        self.update_calendar()
