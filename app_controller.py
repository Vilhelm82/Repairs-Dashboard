#!/usr/bin/env python3
# app_controller.py

import sys
import os
import json
import logging
import threading
import time
import re
from datetime import datetime
import sqlite3

import tkinter as tk
import ttkbootstrap as ttk
from tkinter import messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText

import pytesseract
import pyautogui

# Local imports
from core import db
from core.db import DB_NAME
from ui_tabs.calendar_tab import CalendarTab
from services.aden_controller import add_job_line, save_and_close_job
from utils.automation_helpers import (
    find_and_click,
    find_and_right_click,
    find_label_and_click_offset,
    find_and_double_click_offset,
    find_and_move_to,
    wait_for_image,
    paste_from_clipboard,
    get_region,
    find_image_in_region
)

from utils.debug_ui_widgets import TextHandler
# --- Import stubs for our new Tab modules ---
# We will create these files in the next steps.
from ui_tabs.overview_tab import OverviewTab
from ui_tabs.batch_tasker_tab import BatchTaskerTab
from ui_tabs.importer_tab import ImporterTab
from ui_tabs.job_card_manager_tab import JobCardManagerTab
from ui_tabs.job_indexer_tab import JobIndexerTab
# from ui_tabs.tag_manager_tab import TagManagerTab
from ui_tabs.milwaukee_warranties_tab import MilwaukeeWarrantiesTab

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
# Constants
SEQ_REPO = resource_path("AutoSequenceRepo")
DEBUG_IMG_REPO = resource_path("debug_images")
JOB_CLASS_MAP = {
    'C': 'Cash Sale',
    'E': 'Workshop Job',
    'J': 'Jobs Completed',
    'Q': 'Quote',
    'F': 'Warranty Jobs'
}
TOOL_SUBJECT_KEYWORDS = [
    "Makita", "DeWalt", "Milwaukee", "Bosch", "Hikoki", "Bayer", "Gensafe", "Hush100",
    "Hush150", "Hush70", "Hush50", "EGO", "Paslode", "Battery"
]    

class JobScannerApp:
    def __init__(self):
        # Use ttkbootstrap Window with a default theme
        self.root = ttk.Window(themename="solar")
        # --- Set the default font for all widgets ---
        self.root.style.configure('.', font=('Calibri', 10))
        self.root.title("Repairs Dashboard")
        self.root.geometry("800x750+1000+100") 
        # Always on top will be controlled by the checkbox

        db.init_db()

        # Setup logging first before any logging calls
        self.setup_logging()

        # --- Shared Tkinter Variables ---
        # These are kept in the controller so different tabs can access them if needed.
        self.sequence_var = tk.StringVar(master=self.root)
        self.task_sequence_var = tk.StringVar(master=self.root)
        self.only_uncompleted_var = tk.BooleanVar(value=False)
        self.card_ref_var = tk.StringVar()
        self.theme_var = tk.StringVar(value="solar")
        self.load_sequences()

        self.notebook = ttk.Notebook(self.root)
        # --- NEW: Header frame for theme switcher and always on top checkbox ---
        header_frame = ttk.Frame(self.root, padding=(10, 5, 10, 0))
        header_frame.pack(fill="x")

        # Add always on top checkbox
        self.always_on_top_var = tk.BooleanVar(value=True)
        always_on_top_cb = ttk.Checkbutton(
            header_frame, 
            text="Always on top", 
            variable=self.always_on_top_var,
            command=self.toggle_always_on_top
        )
        always_on_top_cb.pack(side="left", padx=5)

        # Set initial state of the window based on checkbox
        self.toggle_always_on_top()

        ttk.Label(header_frame, text="Theme:").pack(side="right", padx=(0, 5))
        theme_combo = ttk.Combobox(
            header_frame,
            textvariable=self.theme_var,
            values=self.root.style.theme_names(),
            state="readonly"
        )
        theme_combo.pack(side="right")
        theme_combo.bind("<<ComboboxSelected>>", self.on_theme_change)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Add a tab selection event handler to refresh the calendar when selected
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        self.setup_logging()
        self.tab_card_view_index = None
        # --- Initialize Tabs by Instantiating Classes ---
        self.init_tab_overview()
        # self.init_tab_tag_manager()
        self.init_tab_batch_tasker()
        self.init_tab_importer()
        self.init_tab_job_card_manager()
        self.init_tab_milwaukee_warranties()
        self.init_tab_calendar()
        self.init_tab_job_indexer()

        self.refresh_overview_tab() # Initial data load
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.load_session()

    def on_theme_change(self, event=None):
        """Applies the selected theme from the combobox."""
        selected_theme = self.theme_var.get()
        self.logger.info(f"Changing theme to '{selected_theme}'")
        self.root.style.theme_use(selected_theme)

    def toggle_always_on_top(self):
        """Toggles the always-on-top property of the main window."""
        is_on_top = self.always_on_top_var.get()
        self.root.attributes("-topmost", is_on_top)
        self.logger.info(f"Always on top: {is_on_top}")

    def on_tab_changed(self, event=None):
        """Handle tab selection events"""
        selected_tab = self.notebook.select()
        tab_text = self.notebook.tab(selected_tab, "text")

        # If the calendar tab is selected, refresh it
        if tab_text == "📅 Calendar" and hasattr(self, 'calendar_tab'):
            self.logger.info("Calendar tab selected - refreshing calendar view")
            self.calendar_tab.refresh_calendar()

        # If the job indexer tab is selected, perform a search to refresh the results
        elif tab_text == "🔍 Job Indexer" and hasattr(self, 'job_indexer_tab'):
            self.logger.info("Job Indexer tab selected - refreshing search results")
            self.job_indexer_tab.perform_search()

    def init_tab_overview(self):
        self.overview_tab = OverviewTab(self.notebook, self)
        self.notebook.add(self.overview_tab, text="📊 Overview")

    # def init_tab_tag_manager(self):
    #     self.tag_manager_tab = TagManagerTab(self.notebook, self)
    #     self.notebook.add(self.tag_manager_tab, text="🏷️ Tag Manager")

    def init_tab_milwaukee_warranties(self):
        """Initializes the Milwaukee Warranties tab."""
        self.milwaukee_warranties_tab = MilwaukeeWarrantiesTab(self.notebook, self)
        self.notebook.add(self.milwaukee_warranties_tab, text="🔧 Milwaukee Warranties")

    def init_tab_batch_tasker(self):
        self.batch_tasker_tab = BatchTaskerTab(self.notebook, self)
        self.notebook.add(self.batch_tasker_tab, text="🚀 Batch Tasker")

    def init_tab_importer(self):
        self.importer_tab = ImporterTab(self.notebook, self)
        self.notebook.add(self.importer_tab, text="🧾 Job Importer")

    def init_tab_job_card_manager(self):
        """Initializes the main tab that will manage individual job card tabs."""
        self.job_card_manager = JobCardManagerTab(self.notebook, self)
        self.notebook.add(self.job_card_manager, text="📋 Job Cards")

    def init_tab_job_indexer(self):
        self.job_indexer_tab = JobIndexerTab(self.notebook, self)
        self.notebook.add(self.job_indexer_tab, text="🔍 Job Indexer")

    def init_tab_calendar(self):
        """Initializes the main Calendar tab."""
        self.calendar_tab = CalendarTab(self.notebook, self)
        self.notebook.add(self.calendar_tab, text="📅 Calendar")

    # --- AUTOMATION EXECUTION ENGINE ---

    def run_automation_sequence(self, sequence_filename, data_context, skip_event=None):
        """
        Loads and runs an automation sequence in a separate thread.
        Now accepts an optional skip_event to allow for early termination.
        Returns two threading.Event objects: one for completion, one for success.
        """
        self.logger.info(f"Attempting to run sequence '{sequence_filename}'...")
        completion_event = threading.Event()
        success_event = threading.Event()

        sequence_path = os.path.join(SEQ_REPO, sequence_filename)
        if not os.path.exists(sequence_path):
            self.logger.error(f"Sequence file not found: {sequence_path}")
            messagebox.showerror("Error", f"Sequence file not found:\n{sequence_filename}")
            completion_event.set()
            return completion_event, success_event

        try:
            with open(sequence_path, 'r', encoding='utf-8') as f:
                sequence_data = json.load(f)
            steps = sequence_data.get("steps", [])

            automation_thread = threading.Thread(
                target=self._execute_sequence_thread,
                args=(steps, data_context, completion_event, success_event, skip_event),
                # Pass skip_event to the thread
                daemon=True
            )
            automation_thread.start()
            return completion_event, success_event

        except Exception as e:
            self.logger.error(f"Failed to load or start sequence '{sequence_filename}': {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to run sequence:\n{e}")
            completion_event.set()
            return completion_event, success_event

    def _execute_sequence_thread(self, steps, data_context, completion_event, success_event, skip_event=None):
        """
        This method now logs a "Job Imported" event after successfully saving a new job.
        """
        job_ref = data_context.get("job_ref", "UNKNOWN")
        self.logger.info(f"Automation thread started for {job_ref}. Executing {len(steps)} steps.")

        sequence_success = True
        for i, step in enumerate(steps):
            if skip_event and skip_event.is_set():
                self.logger.warning(f"Skip signal received. Halting sequence for job {job_ref}.")
                sequence_success = False
                break

            action = step.get("action", "")
            target = step.get("target_image")
            params = step.get("parameters", {})
            self.logger.info(f"Executing step {i + 1}: {action} on target {target}")

            success = self._execute_single_step(action, target, params, data_context)

            if not success:
                self.logger.error(f"Stopping sequence for {job_ref} due to failure at step {i + 1} ({action}).")
                sequence_success = False
                break

            time.sleep(0.5)

        if sequence_success:
            self.logger.info("--- Data Scraped Report ---")
            for key, value in data_context.items():
                self.logger.info(f"  > {key}: {value!r}")
            self.logger.info("---------------------------")

            if self._is_data_valid(data_context):
                db.insert_job(data_context)
                self.logger.info(f"✅ Saved job: {job_ref}")
                try:
                    db.add_job_event(job_ref, "Job Imported", f"Successfully imported and saved job {job_ref}.")
                except Exception as e:
                    self.logger.error(f"Failed to log 'Job Imported' event for {job_ref}: {e}")
                success_event.set()
            else:
                self.logger.error(f"❌ Job {job_ref} failed validation. Flagging for review.")
                if hasattr(self, 'importer_tab'):
                    self.root.after(0, self.importer_tab.flagged_list.insert, tk.END, job_ref)

        self.root.after(0, self.refresh_all_views)
        self.logger.info(f"Automation thread for {job_ref} finished.")
        completion_event.set()

    def _execute_single_step(self, action, target, params, data_context):
        """
        Executes a single automation step. This is the core logic engine.
        Returns True on success, False on failure.
        """
        try:
            # --- Data-Driven Actions ---
            if action == "type_from_context":
                key = params.get("param1")
                if key in data_context:
                    pyautogui.write(str(data_context[key]), interval=0.05)
                    return True
                self.logger.error(f"Key '{key}' not found in data context.")
                return False

            elif action == "count_list_items":
                input_key, output_key = params.get("param1"), params.get("param2")
                input_list = data_context.get(input_key, [])
                if isinstance(input_list, list):
                    data_context[output_key] = len(input_list)
                    self.logger.info(f"Counted {len(input_list)} items in '{input_key}', stored in '{output_key}'.")
                    return True
                self.logger.error(f"Key '{input_key}' in context is not a list.")
                return False

            elif action == "press_key_context":
                key, count_key = params.get("param1"), params.get("param2")
                count = data_context.get(count_key, 0)
                if isinstance(count, int):
                    pyautogui.press(key, presses=count)
                    return True
                self.logger.error(f"Count variable '{count_key}' is not an integer.")
                return False

            # --- OCR and UI Interaction Actions ---
            elif action == "ocr_capture":
                absolute_region = get_region(target)
                self.logger.info(f"Performing OCR capture on region '{target}' at {absolute_region}")
                img = pyautogui.screenshot(region=absolute_region)

                # Ensure the debug images directory exists
                os.makedirs(DEBUG_IMG_REPO, exist_ok=True)
                debug_filename = os.path.join(DEBUG_IMG_REPO, f"ocr_debug_capture_{target}_{int(time.time())}.png")
                img.save(debug_filename)

                data_key = params.get("param1", "").strip()
                config = ''
                if data_key == 'Job_Class_Cond': 
                    config = r'--oem 3 --psm 10'
                elif data_key == 'job_ref': 
                    config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
                elif data_key == 'customer_no':
                    config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
                elif data_key == 'customer_name':
                    config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz '
                elif data_key == 'date': 
                    config = r'--oem 3 --psm 7'
                text = pytesseract.image_to_string(img, config=config)
                if data_key == 'job_ref':
                    data_context[data_key] = re.sub(r'[^A-Za-z0-9]', '', text).strip()
                elif data_key == 'descriptions':
                    lines = text.splitlines()
                    if 'descriptions' not in data_context: data_context['descriptions'] = []
                    data_context['descriptions'].extend(lines)
                    found_subject = False
                    for line in lines:
                        for keyword in TOOL_SUBJECT_KEYWORDS:
                            if keyword.lower() in line.lower():
                                data_context['tool_subject'] = keyword
                                self.logger.info(f"Found Tool Subject keyword: '{keyword}'")
                                found_subject = True
                                break # Stop after finding the first keyword
                        if found_subject:
                            break
                elif data_key == 'Job_Class_Cond':
                    data_context[data_key] = JOB_CLASS_MAP.get(text.strip().upper(), text.strip())
                elif data_key:
                    data_context[data_key] = text.strip()
                if data_key:
                    self.logger.info(f"Assigned captured text to data context key: '{data_key}'")
                else:
                    self.logger.warning(f"OCR step for target '{target}' is missing 'Parameter 1'.")
                return True

            elif action == "click_center": return find_and_click(target)
            elif action == "right_click_center": return find_and_right_click(target)
            elif action == "double_click_center": return find_and_click(target, clicks=2)
            elif action == "click_offset":
                x, y = int(params.get("param1", 0)), int(params.get("param2", 0))
                return find_label_and_click_offset(target, x_offset=x, y_offset=y)
            elif action == "double_click_offset":
                x, y = int(params.get("param1", 0)), int(params.get("param2", 0))
                return find_and_double_click_offset(target, x_offset=x, y_offset=y)
            elif action == "move_to_target": return find_and_move_to(target)
            elif action == "type_text":
                pyautogui.write(params.get("param1", ""), interval=0.05)
                return True
            elif action == "type_current_date":
                # Parameter 1 can optionally specify a format (e.g., %d-%m-%Y)
                date_format = params.get("param1", "%d/%m/%Y")
                date_string = datetime.now().strftime(date_format)
                self.logger.info(f"Typing current date: {date_string}")
                pyautogui.write(date_string, interval=0.05)
                return True
            elif action == "press_key":
                pyautogui.press(params.get("param1", "enter"))
                return True
            elif action == "sleep":
                time.sleep(float(params.get("param1", 1.0)))
                return True

            elif action == "wait_for_target":
                timeout = int(params.get("param1", 10))
                return wait_for_image(target, timeout)

            elif action == "find_image_in_region":
                secondary_action = params.get("param1", "click")

                if not target:
                    self.logger.error("Action 'find_image_in_region' requires a target to be selected from the 'Select Target' combobox.")
                    return False

                self.logger.info(f"Finding image '{target}' in ADEN window region and performing '{secondary_action}'")
                result = find_image_in_region(target, target, secondary_action)

                # If the secondary action is "get_text" and text was found, store it in the context
                if secondary_action == "get_text" and result and isinstance(result, str):
                    output_key = f"{target}_text"
                    data_context[output_key] = result
                    self.logger.info(f"Stored extracted text in context variable '{output_key}'")

                return result if isinstance(result, bool) else bool(result)

            else:
                self.logger.warning(f"Action '{action}' is not implemented.")
                return False

        except Exception as e:
            self.logger.error(f"Error during step '{action}': {e}", exc_info=True)
            return False

    def _is_data_valid(self, data):
        """Validates the scraped data dictionary before database insertion."""
        errors = []
        job_ref = data.get("job_ref", "")

        if not data.get("customer_name"): errors.append("Customer Name is empty.")
        if not data.get("customer_no"): errors.append("Customer No is empty.")
        if not (len(job_ref) >= 7): errors.append(f"Job Reference '{job_ref}' seems too short.")

        date_str = data.get("date", "")
        if not re.match(r"^\d{1,2}\s[A-Za-z]+\s\d{4}$", date_str):
            errors.append(f"Date format '{date_str}' is incorrect.")

        job_cond = data.get("Job_Class_Cond", "")
        if not job_cond or job_cond not in JOB_CLASS_MAP.values():
            errors.append(f"Job Condition '{job_cond}' is not a valid type.")

        if errors:
            self.logger.warning(f"Validation failed for job {job_ref}: {'; '.join(errors)}")
            return False

        self.logger.info(f"Validation passed for job {job_ref}.")
        return True
    def setup_logging(self, console_widget=None):
        """
        Configures logging. Can direct logs to a UI text widget if one is provided.
        Otherwise, logs to the standard command line console.
        """
        self.logger = logging.getLogger()
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        self.logger.setLevel(logging.DEBUG)

        if console_widget:
            # If a UI widget is provided, use the TextHandler
            handler = TextHandler(console_widget) # TextHandler class needs to be defined/imported
        else:
            # Otherwise, log to the command line
            handler = logging.StreamHandler()

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.info("Job Repair Caddy initialized.")

    def load_sequences(self):
        """Finds all .json sequence files in the repo and returns them as a list."""
        os.makedirs(SEQ_REPO, exist_ok=True)
        files = [f for f in os.listdir(SEQ_REPO) if f.lower().endswith(".json")]
        if files:
            # Set the default value for the shared variable
            self.sequence_var.set(files[0])
        return files

    def clear_debug_images(self):
        self.logger.info(f"Clearing old debug images from: {DEBUG_IMG_REPO}")
        try:
            # Ensure the directory exists
            os.makedirs(DEBUG_IMG_REPO, exist_ok=True)
            for filename in os.listdir(DEBUG_IMG_REPO):
                if filename.lower().endswith(".png"): os.remove(os.path.join(DEBUG_IMG_REPO, filename))
        except Exception as e: self.logger.error(f"Failed to clear debug images: {e}")

    def refresh_overview_tab(self):
        # A controller method to tell the overview tab to refresh itself
        self.overview_tab.refresh_data()

    def switch_to_card_view(self, job_ref: str):
        """
        Switches to the Job Card Manager main tab and instructs it
        to add a new tab for the given job_ref, or focus it if already open.
        """
        # Directly select the job card manager tab itself
        self.notebook.select(self.job_card_manager)

        # Now, tell the manager to open or focus the specific job tab
        if hasattr(self, 'job_card_manager'):
            self.job_card_manager.add_or_focus_tab(job_ref)

    def on_close(self):
        # --- Save Session ---
        try:
            if hasattr(self, 'job_card_manager'):
                open_tabs = list(self.job_card_manager.open_tabs.keys())
                with open("session.json", "w") as f:
                    json.dump({"open_tabs": open_tabs}, f)
                self.logger.info("Session saved.")
        except Exception as e:
            self.logger.error(f"Failed to save session: {e}")

        # --- Stop any running processes ---
        if hasattr(self, 'importer_tab') and self.importer_tab.importing:
            self.importer_tab.stop_import()
        if hasattr(self, 'batch_tasker_tab') and self.batch_tasker_tab.is_batch_running:
            self.batch_tasker_tab.stop_batch()

        self.root.destroy()

    def load_session(self):
        """Checks for a session file and restores open tabs if found."""
        try:
            if os.path.exists("session.json"):
                with open("session.json", "r") as f:
                    session_data = json.load(f)
                open_tabs = session_data.get("open_tabs", [])

                if open_tabs:
                    self.logger.info(f"Restoring {len(open_tabs)} tabs from previous session.")
                    for job_ref in open_tabs:
                        self.switch_to_card_view(job_ref)
                # Clean up the session file after use
                os.remove("session.json")
        except Exception as e:
            self.logger.error(f"Failed to load session: {e}")

    def run(self):
        self.root.mainloop()
    def refresh_all_views(self):
        """Refresh all dynamic views in the application"""
        self.refresh_overview_tab()
        if hasattr(self, 'calendar_tab'):
            self.calendar_tab.refresh_calendar()

    def refresh_calendar(self):
        """Public method to refresh the calendar - can be called from anywhere"""
        if hasattr(self, 'calendar_tab'):
            self.calendar_tab.refresh_calendar()
def update_job_status(job_ref: str, new_status: str, parts_ordered_date: str = None):
    """Updates the overview_status and optionally the parts_ordered_date for a job."""
    # Standardize status strings
    status_map = {
        "waiting on parts": "Waiting on Parts",
        "waiting on customer": "Waiting on Customer/Quote",
        "open warranties": "Open Warranties",
        "open quote to repair": "Open Quote To Repair",
        "jobs completed": "Jobs Completed"
    }

    standardized_status = status_map.get(new_status.lower(), new_status)

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        if parts_ordered_date:
            cur.execute("""
                UPDATE jobs 
                SET overview_status = ?, 
                    parts_ordered_date = ? 
                WHERE job_ref = ?
            """, (standardized_status, parts_ordered_date, job_ref))
        else:
            cur.execute("""
                UPDATE jobs 
                SET overview_status = ? 
                WHERE job_ref = ?
            """, (standardized_status, job_ref))
        conn.commit()

        # Add an event for the status change
        current_date = datetime.now().strftime("%Y-%m-%d")
        cur.execute("""
            INSERT INTO events (job_ref, event_date, event_type, event_description)
            VALUES (?, ?, ?, ?)
        """, (job_ref, current_date, "Status Change", f"Status changed to: {standardized_status}"))
        conn.commit()

    logger.info(f"[DB] Updated status for job {job_ref} to '{standardized_status}'")

    # Refresh the calendar if it exists
    try:
        # Get the app instance from the registry
        import app_registry
        app = app_registry.get_app()
        if app and hasattr(app, 'refresh_calendar'):
            app.refresh_calendar()
            logger.info(f"[DB] Refreshed calendar after status change for {job_ref}.")
    except Exception as e:
        logger.debug(f"[DB] Could not refresh calendar: {e}")
