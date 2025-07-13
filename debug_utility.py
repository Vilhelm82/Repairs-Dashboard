# image_debug_ui.py
import os
import json
import time
import re
import threading
import logging
import tkinter as tk
import datetime
from tkinter import ttk, messagebox, simpledialog
from tkinter.filedialog import askopenfilename
from tkinter.scrolledtext import ScrolledText
import pyautogui
from PIL import Image, ImageTk, ImageOps
import numpy as np
import pytesseract
from skimage.metrics import structural_similarity as ssim

from utils.automation_helpers import (
    find_and_click, find_label_and_click_offset, find_and_right_click, find_and_double_click_offset, find_and_move_to, wait_for_image,
    find_aden_window, paste_from_clipboard, get_region, find_image_in_region
)
# Import the custom widgets from the new module
from utils.debug_ui_widgets import TextHandler, ScreenOverlay, CustomSpinbox

SEQ_REPO = os.path.join(os.path.dirname(__file__), "AutoSequenceRepo")
os.makedirs(SEQ_REPO, exist_ok=True)

# --- Configuration and Asset Loading ---
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "search_regions.json")
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f: SEARCH_REGIONS = json.load(f)
except FileNotFoundError: SEARCH_REGIONS = {}

IMAGE_FOLDER = os.path.join(os.path.dirname(__file__), 'images')
_SYSTEM_ASSETS = {
    "ADEN_WINDOW_ANCHOR_IMG": os.path.join(IMAGE_FOLDER, "aden_window_anchor.png"),
    "REF_FIELD_LABEL_IMG": os.path.join(IMAGE_FOLDER, "ref_field_label.png"),
    "SAVE_BUTTON_IMG": os.path.join(IMAGE_FOLDER, "button_save.png"),
    "JOB_CLASS_EMPTY_IMG": os.path.join(IMAGE_FOLDER, "job_class_empty.png"),
    "JOB_CLASS_WARRANTY_IMG": os.path.join(IMAGE_FOLDER, "job_class_warranty.png"),
    "NO_PRINT_LABEL_IMG": os.path.join(IMAGE_FOLDER, "no_print_label.png"),
    "NO_BUTTON_IMG": os.path.join(IMAGE_FOLDER, "no_button.png"),
    "NEUTRAL_AREA_IMG": os.path.join(IMAGE_FOLDER, "neutral_area.png"),
    "HEADER_ITEM_DESC_IMG": os.path.join(IMAGE_FOLDER, "header_item_desc.png"),
    "TITLE_ADD_QUOTES_IMG": os.path.join(IMAGE_FOLDER, "title_add_quotes.png"),
    "LABEL_POPUP_ITEM_DESC_IMG": os.path.join(IMAGE_FOLDER, "label_popup_item_desc.png"),
    "BUTTON_POPUP_SAVE_IMG": os.path.join(IMAGE_FOLDER, "button_popup_save.png"),
    "JOB_CARD_LOADED_CUE_IMG": os.path.join(IMAGE_FOLDER,"job_card_loaded_cue.png"),
}
USER_ASSETS_PATH = os.path.join(os.path.dirname(__file__), "user_assets.json")
try:
    with open(USER_ASSETS_PATH, "r", encoding="utf-8") as f: _USER_ASSETS = json.load(f)
except FileNotFoundError: _USER_ASSETS = {}
IMAGE_ASSETS = {**_SYSTEM_ASSETS, **_USER_ASSETS}

def write_region(key, left, top, width, height):
    """Saves a region's coordinates to the JSON configuration file."""
    SEARCH_REGIONS[key] = {"left": left, "top": top, "width": width, "height": height}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(SEARCH_REGIONS, f, indent=2, sort_keys=True)

class NoStreamFilter(logging.Filter):
    """A logging filter that blocks messages containing 'STREAM'."""
    def filter(self, record):
        return "STREAM" not in record.getMessage()

class AutomationDesignerUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Debug Utility")
        self.root.geometry("475x831+14+114")
        self.root.attributes("-topmost", True)
        self.root.after(100, lambda: self.root.attributes("-topmost", True))

        # State variables
        self.aden_window_region = None
        self.overlay_window = None
        self._overlay_job = None
        self._pov_job = None
        self.automation_steps = []
        self.is_test_running = False
        self.stop_test_event = threading.Event()

        # Tkinter variables
        self.active_target_var = tk.StringVar(value=None)
        self.left_var = tk.IntVar(value=0)
        self.top_var = tk.IntVar(value=0)
        self.width_var = tk.IntVar(value=100)
        self.height_var = tk.IntVar(value=30)
        self.overlay_var = tk.BooleanVar(value=True)
        self.confidence_var = tk.StringVar(value="Confidence: N/A")
        self.action_var = tk.StringVar()
        self.param1_var = tk.StringVar()
        self.param2_var = tk.StringVar()
        self.show_console_var = tk.BooleanVar(value=False)

        # Bindings
        self.active_target_var.trace_add("write", self.on_target_change)

        # Initialization
        self.setup_ui()
        self.setup_logging()
        self.update_coords()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        self.stop_test_event.set()
        self.root.destroy()

    def setup_ui(self):
        status_frame = ttk.Frame(self.root, padding=(10, 5))
        status_frame.pack(fill="x")
        self.window_status_label = ttk.Label(status_frame, text="ADEN Window: NOT FOUND", background="lightcoral", foreground="black", padding=5, anchor="center", font=("Segoe UI", 9, "bold"))
        self.window_status_label.pack(side="left", fill="x", expand=True)
        ttk.Button(status_frame, text="Find ADEN Window", command=self.test_find_aden_window).pack(side="left", padx=10)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0,5))
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.update_debugger_for_target(self.active_target_var.get()))

        debugger_tab = ttk.Frame(self.notebook)
        sequencer_tab = ttk.Frame(self.notebook)
        self.notebook.add(debugger_tab, text="Region Debugger")
        self.notebook.add(sequencer_tab, text="Automation Sequencer")

        self.build_debugger_tab(debugger_tab)
        self.build_sequencer_tab(sequencer_tab)

        # Console setup (initially hidden)
        self.console_frame = ttk.LabelFrame(self.root, text="Debug Console", padding=5)
        self.console = ScrolledText(self.console_frame, state='disabled', height=8, wrap=tk.WORD, font=("Consolas", 9))
        self.console.pack(fill="both", expand=True, padx=5, pady=5)

        # Corrected: Make bottom_bar an instance variable for stable reference
        self.bottom_bar = ttk.Frame(self.root, relief="sunken")
        self.bottom_bar.pack(side="bottom", fill="x")
        self.coord_label = ttk.Label(self.bottom_bar, text="Mouse Position: X=0, Y=0")
        self.coord_label.pack(side="left", padx=5)
        ttk.Checkbutton(self.bottom_bar, text="Show Debug Console", variable=self.show_console_var, command=self.toggle_console).pack(side="right", padx=5)

    def toggle_console(self):
        if self.show_console_var.get():
            # Corrected: Pack the console specifically before the bottom_bar
            self.console_frame.pack(side="bottom", fill="x", expand=False, padx=10, pady=(0, 5), before=self.bottom_bar)
        else:
            self.console_frame.pack_forget()

    def build_sequencer_tab(self, parent):
        main = ttk.Frame(parent, padding=10)
        main.pack(fill="both", expand=True)

        config_panel = ttk.LabelFrame(main, text="Step Configuration")
        config_panel.pack(side="left", fill="y", padx=(0, 10), anchor="n")

        self.setup_selection_ui(config_panel, title="1. Select Target (Optional)")

        action_frame = ttk.LabelFrame(config_panel, text="2. Define Action")
        action_frame.pack(fill="x", pady=10, padx=5)
        ttk.Label(action_frame, text="Action:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        action_menu = ttk.Combobox(action_frame, textvariable=self.action_var, state="readonly", values=[
            "click_center", "right_click_center", "double_click_center", "click_offset", "double_click_offset", 
            "move_to_target", "type_text", "type_from_context", "type_current_date", "press_key", "hotkey", "paste_from_clipboard", "sleep",
            "wait_for_target", "scroll_mouse", "ocr_capture", "count_list_items", "press_key_context", "find_image_in_region"
        ])
        action_menu.grid(row=0, column=1, padx=5, pady=5)
        action_menu.set("click_center")

        ttk.Label(action_frame, text="Parameter 1:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(action_frame, textvariable=self.param1_var).grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(action_frame, text="Parameter 2:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(action_frame, textvariable=self.param2_var).grid(row=2, column=1, padx=5, pady=5)

        step_mod_frame = ttk.Frame(config_panel)
        step_mod_frame.pack(pady=10, padx=5)
        ttk.Button(step_mod_frame, text="Insert Step Above", command=self.insert_step_above).pack(fill='x', pady=2)
        ttk.Button(step_mod_frame, text="Add Step Below", command=self.add_step_to_sequence).pack(fill='x', pady=2)
        ttk.Button(step_mod_frame, text="Update Selected Step", command=self.update_selected_step).pack(fill='x', pady=2)

        file_ops_frame = ttk.LabelFrame(config_panel, text="File Operations")
        file_ops_frame.pack(pady=20, padx=5, side="bottom", fill="x")
        ttk.Button(file_ops_frame, text="Load Sequence...", command=self.load_sequence_from_json).pack(fill='x', pady=2)
        ttk.Button(file_ops_frame, text="Save Sequence...", command=self.save_sequence_to_json).pack(fill='x', pady=2)
        ttk.Button(file_ops_frame, text="Remove Selected", command=self.remove_selected_step).pack(fill='x', pady=2)

        timeline_panel = ttk.LabelFrame(main, text="Automation Sequence")
        timeline_panel.pack(side="right", fill="both", expand=True)

        runner_frame = ttk.Frame(timeline_panel)
        runner_frame.pack(fill="x", pady=5, padx=5)
        self.run_full_btn = ttk.Button(runner_frame, text="▶ Run Full Sequence", command=self.start_test_thread)
        self.run_full_btn.pack(side="left", padx=2)
        self.run_selected_btn = ttk.Button(runner_frame, text="➡ Run from Selected", command=lambda: self.start_test_thread(from_selected=True))
        self.run_selected_btn.pack(side="left", padx=2)
        self.stop_btn = ttk.Button(runner_frame, text="⏹ Stop Test", command=self.stop_test, state=tk.DISABLED)
        self.stop_btn.pack(side="left", padx=2)

        tree_frame = ttk.Frame(timeline_panel)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        cols = ("#", "Action", "Target", "Parameters")
        self.sequencer_tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
        for col in cols:
            self.sequencer_tree.heading(col, text=col)
            self.sequencer_tree.column(col, width=100, anchor="w")
        self.sequencer_tree.column("#", width=30, anchor="center")
        self.sequencer_tree.pack(side="left", fill="both", expand=True)
        self.sequencer_tree.bind("<<TreeviewSelect>>", self.on_step_select)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.sequencer_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.sequencer_tree.configure(yscrollcommand=scrollbar.set)
        # --- NEW: UI for providing a test data context ---
        ttk.Label(timeline_panel, text="Sequence Test Context (JSON):").pack(fill="x", padx=5, pady=(10, 2))
        self.test_context_text = ScrolledText(timeline_panel, height=5, wrap=tk.WORD, font=("Consolas", 9))
        self.test_context_text.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        self.test_context_text.insert(tk.END, '{\n  "job_ref": "TEST0001",\n  "new_text_line_1": "This is a test line from the context."\n}')
        self.sequencer_tree.tag_configure('running', background='lightblue')
        self.sequencer_tree.tag_configure('success', background='lightgreen')
        self.sequencer_tree.tag_configure('failure', background='lightcoral')

    def setup_logging(self):
        self.logger = logging.getLogger()
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        self.logger.setLevel(logging.DEBUG)

        # Add the custom filter to the handler
        handler = TextHandler(self.console)
        handler.addFilter(NoStreamFilter())

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.info("Debugger UI initialized. Console is hidden by default.")

    def test_find_aden_window(self):
        self.logger.info("Attempting to find ADEN window...")
        self.aden_window_region = find_aden_window(force_refind=True)
        if self.aden_window_region:
            self.logger.info(f"ADEN window found successfully at {self.aden_window_region}")
            self.window_status_label.config(text=f"ADEN Window: FOUND @ ({self.aden_window_region[0]}, {self.aden_window_region[1]})", background="lightgreen")
            overlay = ScreenOverlay(*self.aden_window_region, c="green")
            self.root.after(1500, overlay.close)
        else:
            self.logger.error("Failed to find ADEN window.")
            self.window_status_label.config(text="ADEN Window: NOT FOUND", background="lightcoral")

    def on_target_change(self, *args):
        target_name = self.active_target_var.get()
        self.logger.debug(f"Target changed to: {target_name}")
        if target_name and target_name != 'None':
            relative_coords = SEARCH_REGIONS.get(target_name)
            if relative_coords:
                self.left_var.set(relative_coords.get("left", 0))
                self.top_var.set(relative_coords.get("top", 0))
                self.width_var.set(relative_coords.get("width", 100))
                self.height_var.set(relative_coords.get("height", 30))
                self.logger.debug(f"Loaded coordinates for {target_name}: {relative_coords}")
            else:
                self.left_var.set(0)
                self.top_var.set(0)
                self.width_var.set(100)
                self.height_var.set(30)
                self.logger.debug(f"No coordinates found for {target_name}, using defaults.")
        self.update_debugger_for_target(target_name)

    def update_debugger_for_target(self, target_name):
        is_debugger_active = self.notebook.tab(self.notebook.select(), "text") == "Region Debugger"
        is_target_selected = target_name and target_name != 'None'

        if is_debugger_active and is_target_selected:
            try:
                ref_img = Image.open(IMAGE_ASSETS[target_name])
                self.update_image_label(self.ref_image_label, ref_img)
            except Exception:
                self.ref_image_label.config(image='')
                self.logger.warning(f"Could not load reference image for {target_name}")
        else:
            self.ref_image_label.config(image='')

        self._start_or_stop_overlay_loop()
        self._start_or_stop_pov_loop()

    def build_debugger_tab(self, parent):
        main = ttk.Frame(parent, padding=10)
        main.pack(fill="both", expand=True)
        self.setup_selection_ui(main, title="Select Target to Debug")
        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True)
        self.setup_pov_ui(right)
        self.setup_search_box_calibration_ui(right)
        self.setup_ocr_test_ui(right)

    def setup_selection_ui(self, parent, title="Select Target"):
        frame = ttk.LabelFrame(parent, text=title)
        frame.pack(fill="x", pady=5, anchor="n")

        target_dropdown = ttk.Combobox(frame, textvariable=self.active_target_var, state="readonly", values=[""] + sorted(list(IMAGE_ASSETS.keys())))
        target_dropdown.pack(pady=5, padx=5, fill="x")

        ttk.Button(frame, text="Add New Target...", command=self.add_new_target).pack(pady=(0, 5))

    def add_new_target(self):
        new_name = simpledialog.askstring("Add New Target", "Enter a name for the new target (e.g., CUSTOMER_NAME_IMG):")
        if not new_name: return
        new_name = new_name.strip().upper()
        if not re.match(r'^[A-Z0-9_]+$', new_name):
            messagebox.showerror("Invalid Name", "Name must be uppercase letters, numbers, and underscores only.")
            return
        if new_name in IMAGE_ASSETS:
            messagebox.showerror("Error", f"A target named '{new_name}' already exists.")
            return

        file_name = f"{new_name.lower()}.png"
        file_path = os.path.join(IMAGE_FOLDER, file_name)
        try:
            Image.new('RGB', (50, 20), color='grey').save(file_path)
        except Exception as e:
            messagebox.showerror("File Error", f"Could not create placeholder image:\n{e}")
            return

        _USER_ASSETS[new_name] = file_path
        with open(USER_ASSETS_PATH, "w", encoding="utf-8") as f:
            json.dump(_USER_ASSETS, f, indent=2, sort_keys=True)

        IMAGE_ASSETS[new_name] = file_path
        messagebox.showinfo("Success", f"Target '{new_name}' added. Please restart the application to see it in the list.")
        self.root.destroy()

    def setup_pov_ui(self, parent):
        frame = ttk.LabelFrame(parent, text="Live Analysis", padding=10)
        frame.pack(fill="both", expand=True, pady=5)
        ttk.Label(frame, text="Reference Image:").pack()
        self.ref_image_label = ttk.Label(frame)
        self.ref_image_label.pack(pady=5)
        ttk.Label(frame, text="Live POV on Screen:").pack()
        self.pov_image_label = ttk.Label(frame)
        self.pov_image_label.pack(pady=5)
        self.confidence_label = ttk.Label(frame, textvariable=self.confidence_var, font=("Segoe UI", 10, "bold"))
        self.confidence_label.pack(pady=(5, 0))

    def setup_search_box_calibration_ui(self, parent):
        frame = ttk.LabelFrame(parent, text="Search Box Calibration", padding=10)
        frame.pack(fill="x", pady=5)
        ttk.Checkbutton(frame, text="Display Red Overlay", variable=self.overlay_var, command=self._start_or_stop_overlay_loop).grid(row=0, column=0, columnspan=4, sticky="w", pady=2)

        ttk.Label(frame, text="Left (Rel):").grid(row=1, column=0, sticky="e", padx=(0,5))
        CustomSpinbox(frame, from_=0, to=4000, textvariable=self.left_var).grid(row=1, column=1, pady=2)
        ttk.Label(frame, text="Top (Rel):").grid(row=1, column=2, sticky="e", padx=(10,5))
        CustomSpinbox(frame, from_=0, to=4000, textvariable=self.top_var).grid(row=1, column=3, pady=2)
        ttk.Label(frame, text="Width:").grid(row=2, column=0, sticky="e", padx=(0,5))
        CustomSpinbox(frame, from_=1, to=4000, textvariable=self.width_var).grid(row=2, column=1, pady=2)
        ttk.Label(frame, text="Height:").grid(row=2, column=2, sticky="e", padx=(10,5))
        CustomSpinbox(frame, from_=1, to=4000, textvariable=self.height_var).grid(row=2, column=3, pady=2)

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=3, column=0, columnspan=4, pady=(10,0))
        ttk.Button(button_frame, text="Save Region to JSON", command=self.save_search_coords).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Recapture Ref Image", command=self.save_new_ref_image).pack(side="left", padx=5)

        for var in (self.left_var, self.top_var, self.width_var, self.height_var):
            var.trace_add("write", self.update_pov_viewer)

    def setup_ocr_test_ui(self, parent):
        """Creates the OCR testing button and output box."""
        frame = ttk.LabelFrame(parent, text="Live OCR Test", padding=10)
        frame.pack(fill="x", pady=5)

        ttk.Button(frame, text="Test OCR on Region", command=self.run_ocr_test).pack(pady=5)

        self.ocr_output_text = ScrolledText(frame, height=4, wrap=tk.WORD, font=("Consolas", 10))
        self.ocr_output_text.pack(fill="both", expand=True, pady=(0, 5))
        self.ocr_output_text.insert(tk.END, "OCR output will appear here...")
        self.ocr_output_text.configure(state='disabled')

    def run_ocr_test(self):
        """Performs OCR on the currently defined LIVE region and displays the result."""
        if not self.aden_window_region:
            messagebox.showerror("Error", "Cannot run OCR test. Find the ADEN window first.")
            return

        try:
            win_x, win_y, _, _ = self.aden_window_region
            rel_x = self.left_var.get()
            rel_y = self.top_var.get()
            w = self.width_var.get()
            h = self.height_var.get()
            absolute_region = (win_x + rel_x, win_y + rel_y, w, h)

            self.logger.info(f"Testing OCR on LIVE region at {absolute_region}")

            was_visible = self.overlay_window and self.overlay_var.get()
            if was_visible:
                self.overlay_window.root.withdraw()
                self.root.update_idletasks()
                time.sleep(0.1)

            img = pyautogui.screenshot(region=absolute_region)

            # Updated: Use specific config for single characters
            # This dramatically improves accuracy for things like job class letters
            config = r'--oem 3 --psm 10'
            text = pytesseract.image_to_string(img, config=config).strip()

            if was_visible:
                self.overlay_window.root.deiconify()

            self.ocr_output_text.configure(state='normal')
            self.ocr_output_text.delete('1.0', tk.END)
            self.ocr_output_text.insert(tk.END, text if text else "--- OCR returned no text ---")
            self.ocr_output_text.configure(state='disabled')
            self.logger.info(f"OCR Test Result: {text!r}")

        except Exception as e:
            messagebox.showerror("OCR Error", f"An error occurred during OCR test:\n{e}")
            self.logger.error(f"Failed OCR test on live region: {e}", exc_info=True)


    def calculate_confidence(self, pov_img, ref_img):
        try:
            pov_resized = pov_img.resize(ref_img.size)
            pov_np = np.array(pov_resized.convert('L'))
            ref_np = np.array(ref_img.convert('L'))
            score = ssim(ref_np, pov_np)
            display_score = max(0, score)
            self.confidence_var.set(f"Confidence: {display_score:.2%}")
        except Exception as e:
            self.logger.error(f"Confidence score error: {e}")
            self.confidence_var.set("Confidence: Error")

    def _pov_viewer_loop(self):
        pov_img = None
        if self.aden_window_region:
            try:
                win_x, win_y, _, _ = self.aden_window_region
                rel_x, rel_y, w, h = (self.left_var.get(), self.top_var.get(), self.width_var.get(), self.height_var.get())
                abs_region = (win_x + rel_x, win_y + rel_y, w, h)
                pov_img = pyautogui.screenshot(region=abs_region)
            except Exception:
                pov_img = None

        if pov_img:
            self.update_image_label(self.pov_image_label, pov_img)
        else:
            self.pov_image_label.config(image='')

        active_target = self.active_target_var.get()
        if pov_img and active_target and active_target in IMAGE_ASSETS:
            try:
                ref_img_pil = Image.open(IMAGE_ASSETS[active_target])
                self.calculate_confidence(pov_img, ref_img_pil)
            except Exception:
                self.confidence_var.set("Confidence: N/A")
        else:
            self.confidence_var.set("Confidence: N/A")

        self._pov_job = self.root.after(250, self._pov_viewer_loop)

    def update_pov_viewer(self, *args):
        if not self.aden_window_region: return
        is_debugger_active = self.notebook.tab(self.notebook.select(), "text") == "Region Debugger"
        if not is_debugger_active: return

        win_x, win_y, _, _ = self.aden_window_region
        rel_x, rel_y, w, h = (self.left_var.get(), self.top_var.get(), self.width_var.get(), self.height_var.get())
        abs_region = (win_x + rel_x, win_y + rel_y, w, h)
        try:
            pov_img = pyautogui.screenshot(region=abs_region)
            self.update_image_label(self.pov_image_label, pov_img)
        except Exception:
            self.pov_image_label.config(image='')

    def _start_or_stop_pov_loop(self):
        is_debugger_active = self.notebook.tab(self.notebook.select(), "text") == "Region Debugger"
        active_target = self.active_target_var.get()
        if is_debugger_active and active_target and active_target != 'None':
            if not self._pov_job:
                self.logger.info("Starting POV viewer loop.")
                self._pov_viewer_loop()
        else:
            if self._pov_job:
                self.logger.info("Stopping POV viewer loop.")
                self.root.after_cancel(self._pov_job)
                self._pov_job = None
            self.pov_image_label.config(image='')
            self.confidence_var.set("Confidence: N/A")

    def _overlay_loop(self):
        if not self.aden_window_region:
            self._start_or_stop_overlay_loop()
            return
        win_x, win_y, _, _ = self.aden_window_region
        rel_x, rel_y, w, h = (self.left_var.get(), self.top_var.get(), self.width_var.get(), self.height_var.get())
        abs_x, abs_y = win_x + rel_x, win_y + rel_y
        if self.overlay_window:
            self.overlay_window.root.geometry(f"{w}x{h}+{abs_x}+{abs_y}")
        else:
            self.overlay_window = ScreenOverlay(abs_x, abs_y, w, h)
        self._overlay_job = self.root.after(100, self._overlay_loop)

    def _start_or_stop_overlay_loop(self, *args):
        is_debugger_active = self.notebook.tab(self.notebook.select(), "text") == "Region Debugger"
        active_target = self.active_target_var.get()
        if self.overlay_var.get() and active_target and active_target != 'None' and is_debugger_active:
            if not self._overlay_job:
                self._overlay_loop()
        else:
            if self._overlay_job:
                self.root.after_cancel(self._overlay_job)
                self._overlay_job = None
            if self.overlay_window:
                self.overlay_window.close()
                self.overlay_window = None

    def save_new_ref_image(self):
        if not self.aden_window_region:
            messagebox.showerror("Error", "Cannot capture image. Find the ADEN window first.")
            return
        active_target = self.active_target_var.get()
        if not active_target or active_target == 'None': return
        ref_path = IMAGE_ASSETS[active_target]
        if not messagebox.askyesno("Confirm", f"This will overwrite:\n{os.path.basename(ref_path)}\nAre you sure?"): return

        was_visible = self.overlay_window and self.overlay_var.get()
        if was_visible:
            self.overlay_window.root.withdraw()
            self.root.update_idletasks()
            time.sleep(0.1)

        win_x, win_y, _, _ = self.aden_window_region
        rel_x, rel_y, w, h = (self.left_var.get(), self.top_var.get(), self.width_var.get(), self.height_var.get())
        capture_region = (win_x + rel_x, win_y + rel_y, w, h)

        try:
            img = pyautogui.screenshot(region=capture_region)
            self.logger.debug(f"Attempting to save screenshot to: {ref_path!r}")
            img.save(ref_path)
            messagebox.showinfo("Success", "Reference image has been recaptured and saved.")
        except Exception as e:
            self.logger.error(f"Failed to save reference image to {ref_path}", exc_info=True)
            messagebox.showerror("Error", f"Failed to save image:\n{e}")
        finally:
            if was_visible:
                self.overlay_window.root.deiconify()

    def start_test_thread(self, from_selected=False):
        if self.is_test_running:
            messagebox.showwarning("Test in Progress", "A test sequence is already running.")
            return

        # Parse the JSON from the new text box
        try:
            context_json = self.test_context_text.get("1.0", tk.END)
            if not context_json.strip(): # Handle empty input
                data_context = {}
            else:
                data_context = json.loads(context_json)
            self.logger.info(f"Using test data context: {data_context}")
        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"The test context is not valid JSON.\n\nError: {e}")
            return

        start_index = 0
        if from_selected:
            selected_item = self.sequencer_tree.selection()
            if not selected_item:
                messagebox.showerror("Error", "No step selected to start from.")
                return
            start_index = self.sequencer_tree.index(selected_item[0])

        self.is_test_running = True
        self.stop_test_event.clear()
        self.update_runner_buttons()
        for item in self.sequencer_tree.get_children():
            self.sequencer_tree.item(item, tags=())

        # The thread now gets the data_context passed to its target function
        test_thread = threading.Thread(target=self.run_test_sequence, args=(start_index, data_context), daemon=True)
        test_thread.start()

    def stop_test(self):
        if self.is_test_running:
            self.stop_test_event.set()

    def update_runner_buttons(self):
        state = tk.DISABLED if self.is_test_running else tk.NORMAL
        self.run_full_btn.config(state=state)
        self.run_selected_btn.config(state=state)
        self.stop_btn.config(state=tk.NORMAL if self.is_test_running else tk.DISABLED)

    def run_test_sequence(self, start_index=0, data_context={}):
        steps_to_run = self.automation_steps[start_index:]
        all_item_ids = self.sequencer_tree.get_children()

        for i, step in enumerate(steps_to_run):
            if self.stop_test_event.is_set():
                self.logger.warning("Test run stopped by user.")
                break

            item_id = all_item_ids[start_index + i]
            self.root.after(0, lambda id=item_id: self.sequencer_tree.item(id, tags=('running',)))

            action = step["action"]
            target = step.get("target_image")
            params = step.get("parameters", {})
            self.logger.info(f"Executing step {step['step']}: {action} on target {target}")

            # The data_context is passed to the execution function
            success = self._execute_single_step(action, target, params, data_context)

            tag = 'success' if success else 'failure'
            self.root.after(0, lambda id=item_id, t=tag: self.sequencer_tree.item(id, tags=(t,)))

            if not success:
                self.logger.error("Stopping test run due to step failure.")
                break
            time.sleep(0.5)

        self.is_test_running = False
        self.root.after(0, self.update_runner_buttons)
        self.logger.info("Test run finished.")

    def _execute_single_step(self, action, target, params, data_context):
        """Executes a single automation step and returns its success status."""
        try:
            if action == "type_from_context":
                key = params.get("param1")
                if not key:
                    self.logger.error("Action 'type_from_context' requires a key in Parameter 1.")
                    return False

                if key in data_context:
                    value_to_type = str(data_context[key])
                    self.logger.info(f"Typing value from context. Key: '{key}', Value: '{value_to_type}'")
                    pyautogui.write(value_to_type, interval=0.05)
                    return True
                else:
                    self.logger.error(f"Error: Key '{key}' not found in the provided test context.")
                    return False

            elif action == "count_list_items":
                input_key = params.get("param1")
                output_key = params.get("param2")
                if not input_key or not output_key:
                    self.logger.error("Action 'count_list_items' requires an input key (Param1) and an output key (Param2).")
                    return False

                input_list = data_context.get(input_key)
                if not isinstance(input_list, list):
                    self.logger.error(f"Error: Key '{input_key}' in context is not a list.")
                    return False

                count = len(input_list)
                data_context[output_key] = count
                self.logger.info(f"Counted {count} items in '{input_key}'. Stored result in new context variable '{output_key}'.")
                return True

            elif action == "press_key_context":
                key_to_press = params.get("param1")
                count_key = params.get("param2")
                if not key_to_press or not count_key:
                    self.logger.error("Action 'press_key_context' requires a key to press (Param1) and a context variable for the count (Param2).")
                    return False

                press_count = data_context.get(count_key)
                if not isinstance(press_count, int):
                    self.logger.error(f"Error: Count variable '{count_key}' in context is not an integer.")
                    return False

                self.logger.info(f"Pressing key '{key_to_press}' {press_count} times.")
                pyautogui.press(key_to_press, presses=press_count)
                return True

            # --- NEWLY ADDED OCR CAPTURE LOGIC FOR DEBUGGER ---
            elif action == "ocr_capture":
                output_key = params.get("param1")
                if not output_key:
                    self.logger.error("Action 'ocr_capture' requires an output key in Parameter 1.")
                    return False

                absolute_region = get_region(target)
                self.logger.info(f"Performing OCR capture on region '{target}' at {absolute_region}")
                img = pyautogui.screenshot(region=absolute_region)
                text = pytesseract.image_to_string(img).strip()
                if text:
                    data_context[output_key] = text.split('\n')
                else:
                    data_context[output_key] = []  # Return an empty list if no text was found
                # For testing, we'll just split the text into lines
                data_context[output_key] = text.strip().split('\n')
                self.logger.info(f"OCR captured {len(data_context[output_key])} lines into context variable '{output_key}'.")
                return True
            # --- END OF NEW LOGIC ---

            elif action == "click_center": return find_and_click(target)
            elif action == "right_click_center": return find_and_right_click(target)
            elif action == "double_click_center": return find_and_click(target, clicks=2)
            elif action == "click_offset":
                x = int(params.get("param1", 0))
                y = int(params.get("param2", 0))
                return find_label_and_click_offset(target, x_offset=x, y_offset=y)
            elif action == "double_click_offset":
                x = int(params.get("param1", 0))
                y = int(params.get("param2", 0))
                return find_and_double_click_offset(target, x_offset=x, y_offset=y)
            elif action == "move_to_target": return find_and_move_to(target)
            elif action == "type_text":
                pyautogui.write(params.get("param1", ""), interval=0.05)
                return True
            elif action == "press_key":
                pyautogui.press(params.get("param1", "enter"))
                return True

            elif action == "paste_from_clipboard": return paste_from_clipboard()
            elif action == "sleep":
                time.sleep(float(params.get("param1", 1.0)))
                return True
            elif action == "wait_for_target":
                timeout = int(params.get("param1", 10))
                return wait_for_image(target, timeout)
            elif action == "scroll_mouse":
                amount = int(params.get("param1", 0))
                pyautogui.scroll(amount)
                return True
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
            elif action == "type_current_date":
                # Get the current date and format it
                date_format = params.get("param1", "%d/%m/%Y")  # Default format: DD/MM/YYYY
                current_date = datetime.datetime.now().strftime(date_format)
                self.logger.info(f"Typing current date: {current_date}")
                pyautogui.write(current_date, interval=0.05)
                return True
            else:
                self.logger.warning(f"Action '{action}' is not implemented.")
                return False
        except Exception as e:
            self.logger.error(f"Error during step execution: {e}", exc_info=True)
            return False

    def on_step_select(self, event):
        selected_items = self.sequencer_tree.selection()
        if not selected_items:
            return

        selected_item = selected_items[0]
        selected_index = self.sequencer_tree.index(selected_item)

        try:
            step_data = self.automation_steps[selected_index]
            self.action_var.set(step_data.get("action", ""))
            self.active_target_var.set(step_data.get("target_image") or "")
            self.param1_var.set(step_data.get("parameters", {}).get("param1", ""))
            self.param2_var.set(step_data.get("parameters", {}).get("param2", ""))
        except IndexError:
            self.logger.error(f"Failed to load step data for index {selected_index}")

    def _create_step_from_ui(self):
        """Helper to create a step dictionary from the current UI state."""
        action = self.action_var.get()
        target = self.active_target_var.get() or None
        params = {}
        if self.param1_var.get(): params['param1'] = self.param1_var.get()
        if self.param2_var.get(): params['param2'] = self.param2_var.get()
        return {"action": action, "target_image": target, "parameters": params, "on_failure": "stop_with_error"}

    def insert_step_above(self):
        """Inserts a new step before the selected step in the list."""
        selected_items = self.sequencer_tree.selection()
        insert_index = 0
        if selected_items:
            insert_index = self.sequencer_tree.index(selected_items[0])

        new_step_data = self._create_step_from_ui()
        self.automation_steps.insert(insert_index, new_step_data)
        self.refresh_sequencer_view()
        self.logger.info(f"Inserted new step at position {insert_index + 1}")

    def add_step_to_sequence(self):
        """Adds a new step to the end of the sequence."""
        new_step_data = self._create_step_from_ui()
        self.automation_steps.append(new_step_data)
        self.refresh_sequencer_view()
        self.active_target_var.set("")

    def update_selected_step(self):
        selected_items = self.sequencer_tree.selection()
        if not selected_items:
            messagebox.showwarning("No Selection", "Please select a step to update.")
            return

        selected_item = selected_items[0]
        selected_index = self.sequencer_tree.index(selected_item)

        try:
            updated_step_data = self._create_step_from_ui()
            step_num = self.automation_steps[selected_index]['step']
            updated_step_data['step'] = step_num
            updated_step_data['name'] = f"Step {step_num}: {updated_step_data['action']}"
            self.automation_steps[selected_index] = updated_step_data
            self.refresh_sequencer_view()
            self.logger.info(f"Updated step #{step_num}")
        except IndexError:
            messagebox.showerror("Error", "Could not update the selected step. Index out of range.")

    def remove_selected_step(self):
        selected_item = self.sequencer_tree.selection()
        if not selected_item: return messagebox.showwarning("Warning", "No step selected to remove.")
        selected_index = self.sequencer_tree.index(selected_item[0])
        del self.automation_steps[selected_index]
        self.refresh_sequencer_view()

    def save_sequence_to_json(self):
        if not self.automation_steps:
            return messagebox.showerror("Error", "Cannot save an empty sequence.")
        filename = simpledialog.askstring("Save As", "Enter sequence name (no extension):")
        if not filename: return
        filename = filename.strip().replace(" ", "_")
        if not filename.endswith(".json"): filename += ".json"
        task_name = filename.replace(".json", "").replace("_", " ").title()
        output_data = {"task_name": task_name, "description": "An automated task.", "steps": self.automation_steps}
        path = os.path.join(SEQ_REPO, filename)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2)
            messagebox.showinfo("Success", f"Automation task saved as:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file:\n{e}")

    def load_sequence_from_json(self):
        filepath = askopenfilename(
            initialdir=SEQ_REPO,
            title="Select a Sequence File",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
        )
        if not filepath:
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if "steps" not in data or not isinstance(data["steps"], list):
                raise ValueError("JSON file is missing a valid 'steps' list.")

            self.automation_steps = data["steps"]
            self.refresh_sequencer_view()
            self.logger.info(f"Successfully loaded sequence from {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load or parse sequence file:\n{e}")
            self.logger.error(f"Failed to load sequence from {filepath}: {e}", exc_info=True)


    def refresh_sequencer_view(self):
        for item in self.sequencer_tree.get_children():
            self.sequencer_tree.delete(item)
        for i, step in enumerate(self.automation_steps):
            step['step'] = i + 1
            step['name'] = f"Step {i+1}: {step['action']}"
            params_str = json.dumps(step.get('parameters', {})) if step.get('parameters') else ""
            self.sequencer_tree.insert("", "end", values=(step['step'], step['action'], step.get('target_image') or "N/A", params_str))

    def save_search_coords(self):
        active_target = self.active_target_var.get()
        if not active_target or active_target == 'None': return
        l, t, w, h = (self.left_var.get(), self.top_var.get(), self.width_var.get(), self.height_var.get())
        write_region(active_target, l, t, w, h)
        messagebox.showinfo("Saved", f"Relative region for '{active_target}' saved to JSON.")

    def update_coords(self):
        try:
            x, y = pyautogui.position()
            self.coord_label.config(text=f"Mouse Position: X={x}, Y={y}")
            self.root.after(100, self.update_coords)
        except tk.TclError:
            pass # Main window was destroyed

    def update_image_label(self, label, pil_image):
        try:
            img_bordered = ImageOps.expand(pil_image, border=1, fill='red')
            photo = ImageTk.PhotoImage(img_bordered)
            label.config(image=photo)
            label.image = photo # Keep a reference
        except Exception:
            label.config(image='')

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = AutomationDesignerUI()
    app.run()
