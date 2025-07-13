# aden_automation.py

import time
import logging
import pyautogui
import pyperclip

from utils.automation_helpers import (
    find_label_and_click_offset,
)

logger = logging.getLogger(__name__)

# === CLIPBOARD COPY ===
def clipboard_copy() -> str:
    """
    Selects all text in the focused field, copies it to the clipboard,
    and returns the trimmed text.
    """
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyautogui.hotkey('ctrl', 'c')
    time.sleep(0.1)
    text = pyperclip.paste().strip()
    logger.debug("Clipboard contents: %r", text)
    return text

# === ENTER JOB REFERENCE ===
def enter_job_ref(job_ref: str) -> bool:
    """
    Focuses the job reference input field via its label and enters the given job_ref.
    """
    logger.info(f"--- Task: Entering job reference {job_ref} ---")

    # Click the reference field label to focus the input
    if not find_label_and_click_offset(
        "REF_FIELD_LABEL_IMG",
        x_offset=0, y_offset=0
    ):
        logger.error("Failed to focus the job reference field.")
        return False
    time.sleep(0.5)

    # Clear any existing text
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.press('delete')
    time.sleep(0.2)

    # Type the new reference number character by character
    for char in str(job_ref):
        pyautogui.write(char)
        time.sleep(0.05)

    # Submit the job reference
    pyautogui.press('enter')
    time.sleep(2.5)  # Wait for ADEN to process the entry

    logger.debug("Finished entering job reference.")
    return True
