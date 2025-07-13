# aden_controller.py

import time
import logging
import pyautogui
from tkinter import messagebox
import pyperclip

# Updated import paths for the new structure
from core import db
from services.aden_automation import enter_job_ref, clipboard_copy
from utils.automation_helpers import (
    find_and_click,
    find_label_and_click_offset,
    get_region,
    IMAGE_ASSETS,
    CONFIDENCE_LEVEL,
)

logger = logging.getLogger(__name__)

# --- ADEN STATE DETECTION ---
def check_aden_state() -> str:
    """
    Determines ADEN state by searching for images within calibrated regions.
    Returns 'job_card_loaded', 'ready', or 'unknown'.
    """
    # Check for loaded warranty job
    try:
        img_path = IMAGE_ASSETS["JOB_CLASS_WARRANTY_IMG"]
        region = get_region("JOB_CLASS_WARRANTY_IMG")
        if pyautogui.locateOnScreen(img_path, region=region,
                                    confidence=CONFIDENCE_LEVEL, grayscale=True):
            return "job_card_loaded"
    except Exception as e:
        logger.error(f"Error detecting loaded warranty state: {e}", exc_info=True)

    # Check for empty (ready) state
    try:
        img_path = IMAGE_ASSETS["JOB_CLASS_EMPTY_IMG"]
        region = get_region("JOB_CLASS_EMPTY_IMG")
        if pyautogui.locateOnScreen(img_path, region=region,
                                    confidence=CONFIDENCE_LEVEL, grayscale=True):
            return "ready"
    except Exception as e:
        logger.error(f"Error detecting ready state: {e}", exc_info=True)

    return "unknown"


# --- ERROR HANDLING ---
def handle_error_state(state: str) -> bool:
    """Displays an error message for an unexpected application state."""
    msg = (
        f"⚠️ ADEN is in an unexpected state: '{state}'.\n"
        "Ensure you are on the Job Card Ready screen.\n\n"
        "Click Retry to try again, or Cancel to abort."
    )
    return messagebox.askretrycancel("ADEN State Error", msg)


# === NEW FUNCTION: FIX FOR ImportError ===
def load_job_card(job_ref: str) -> bool:
    """Enters a job reference and verifies that the job card has loaded."""
    logger.info(f"--- Task: Loading Job Card {job_ref} ---")
    if not enter_job_ref(job_ref):
        return False
    time.sleep(1)  # Wait a moment for UI to update

    state = check_aden_state()
    if state == "job_card_loaded":
        logger.info("✅ Job card loaded successfully.")
        return True
    else:
        logger.error(f"❌ Failed to load job card. ADEN state is '{state}'.")
        handle_error_state(state)
        return False


# --- CORE TASKS ---
def save_and_close_job() -> bool:
    """
    Clicks the 'No Print' label then the Save button to close a job card.
    """
    logger.info("--- Task: Saving and Closing Job Card ---")

    # Click the 'No Print' checkbox or label
    if not find_label_and_click_offset(
            "NO_PRINT_LABEL_IMG", x_offset=-20, y_offset=0
    ):
        return False

    # Click the Save button
    if not find_and_click("SAVE_BUTTON_IMG"):
        return False

    time.sleep(2.5)
    logger.info("✅ Job saved and closed.")
    return True


def run_job(job_ref: str) -> dict:
    """
    Loads a job, prompts user to select text, scrapes data, and closes the job.
    """
    logger.info(f"--- Task: Scraping Job {job_ref} ---")
    if not load_job_card(job_ref):
        messagebox.showerror("Error", f"Could not load job {job_ref} in ADEN.")
        return {}

    messagebox.showinfo(
        "Action Required",
        "Please SELECT ALL text on the job card now.\n\n"
        "Click OK when you are ready for the app to copy it."
    )

    # Use the helper to copy the selected text to the clipboard
    text = clipboard_copy()
    if not text:
        logger.error("No text was copied from the clipboard.")
        save_and_close_job()  # Attempt to close the job to reset the state
        return {}

    # Basic parsing of the scraped text. This can be customized.
    lines = text.split('\n')
    job_data = {
        "job_ref": job_ref,
        "customer_no": "N/A",  # Placeholder
        "customer_name": "N/A",  # Placeholder
        "job_date": "N/A",  # Placeholder
        "descriptions": [line.strip() for line in lines if line.strip()]
    }

    if not save_and_close_job():
        logger.error("Failed to save and close after scraping.")

    return job_data


def add_job_line(
        job_ref: str,
        model_code: str,
        detailed_description: str,
        price: str
) -> bool:
    """
    Adds a new line item to the currently open job card.
    NOTE: This is an example workflow and may need to be adapted to your ADEN application.
    """
    logger.info(f"--- Task: Adding line item to {job_ref} ---")

    # Step 1: Find the description field in the 'add item' popup and click it.
    if not find_label_and_click_offset("LABEL_POPUP_ITEM_DESC_IMG", x_offset=150, y_offset=0):
        logger.error("Could not find the description field in the popup.")
        return False

    # Step 2: Combine the info, copy it to clipboard, and paste it.
    pyperclip.copy(f"{model_code} - {detailed_description} @ ${price}")
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.5)

    # Step 3: Find and click the save button in the popup.
    if not find_and_click("BUTTON_POPUP_SAVE_IMG"):
        logger.error("Could not find the 'Save' button in the popup.")
        return False

    logger.info("✅ Successfully added line item.")
    # Update the local database with the new line for reference
    db.update_job_description(job_ref, f"ADDED: {model_code} - {detailed_description} - ${price}")
    return True
