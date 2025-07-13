# automation_helpers.py
import sys
import os
import json
import time
import logging
import pyautogui
import pyperclip
import cv2
import numpy as np
import pytesseract
from PIL import Image
# --- Master region cache ---
_ADEN_WINDOW_REGION = None

# --- CONFIGURATION & ASSET LOADING ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    return os.path.join(base_path, relative_path)

CONFIG_PATH = resource_path("search_regions.json")
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f: SEARCH_REGIONS = json.load(f)
except FileNotFoundError: SEARCH_REGIONS = {}

IMAGE_FOLDER = resource_path('images')
# (The rest of the asset loading remains the same)

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
    "JOB_CARD_LOADED_CUE_IMG": os.path.join(IMAGE_FOLDER, "job_card_loaded_cue.png"),
    "PRINTED_CUST_NAME": os.path.join(IMAGE_FOLDER, "printed_cust_name.png"),
    "JOB_CLASS_COND": os.path.join(IMAGE_FOLDER, "job_class_cond.png"),
    "PRINTED_CUST_NO": os.path.join(IMAGE_FOLDER, "printed_cust_no.png"),
    "PRINTED_DATE": os.path.join(IMAGE_FOLDER, "printed_date.png"),
    "PRINTED_REF_NO": os.path.join(IMAGE_FOLDER, "printed_ref_no.png"),
    "ITEM_TEXT_BOX_FULL": os.path.join(IMAGE_FOLDER, "item_text_box_full.png"),
    "REPAIR_OF_TOOLS_TEXTBOX": os.path.join(IMAGE_FOLDER, "repair_of_tools_textbox.png")
}

USER_ASSETS_PATH = os.path.join(os.path.dirname(__file__), "user_assets.json")
try:
    with open(USER_ASSETS_PATH, "r", encoding="utf-8") as f: _USER_ASSETS = json.load(f)
except FileNotFoundError: _USER_ASSETS = {}
IMAGE_ASSETS = {**_SYSTEM_ASSETS, **_USER_ASSETS}

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 10; CONFIDENCE_LEVEL = 0.8

def find_aden_window(force_refind=False) -> tuple | None:
    global _ADEN_WINDOW_REGION
    if _ADEN_WINDOW_REGION and not force_refind:
        return _ADEN_WINDOW_REGION
    try:
        anchor_path = IMAGE_ASSETS["ADEN_WINDOW_ANCHOR_IMG"]
        anchor_pos = pyautogui.locateOnScreen(anchor_path, confidence=0.85)
        if anchor_pos:
            _ADEN_WINDOW_REGION = (int(anchor_pos.left), int(anchor_pos.top), 945, 600)
            logger.info(f"ADEN window found at: {_ADEN_WINDOW_REGION}")
            return _ADEN_WINDOW_REGION
    except Exception as e:
        logger.error(f"Error finding ADEN window anchor: {e}")
    _ADEN_WINDOW_REGION = None
    logger.error("Could not find the ADEN window on screen.")
    return None

def get_region(key: str) -> tuple:
    aden_window = find_aden_window()
    if not aden_window:
        raise Exception("Cannot get target region because the main ADEN window was not found.")
    relative_region_data = SEARCH_REGIONS.get(key)
    if not relative_region_data:
        raise KeyError(f"No region named '{key}' in {CONFIG_PATH}")
    absolute_left = aden_window[0] + relative_region_data["left"]
    absolute_top = aden_window[1] + relative_region_data["top"]
    return absolute_left, absolute_top, relative_region_data["width"], relative_region_data["height"]

def _save_failure_screenshot(key: str):
    """Helper to save a debug screenshot."""
    try:
        failure_timestamp = time.strftime("%Y%m%d-%H%M%S")

        screenshot_path = os.path.join(os.path.dirname(__file__), "..", "debug_images",
                                           f"debug_failure_{key}_{failure_timestamp}.png")
        pyautogui.screenshot(screenshot_path)
        logger.error(f"Debug screenshot saved to: {screenshot_path}")
    except Exception as e:
        logger.error(f"Failed to save debug screenshot: {e}")

# --- HELPER FUNCTIONS ---
def find_image_and_get_text(key: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    """
    Finds a reference image within a region, then performs OCR on the area
    immediately to the right of the found image.

    Args:
        key (str): The key for the image asset and search region.
        timeout (int): How long to search for the image.

    Returns:
        str | None: The extracted text if the image is found, otherwise None.
    """
    logger.info(f"--- Task: Finding '{key}' to read text ---")
    image_path = IMAGE_ASSETS.get(key)
    if not image_path:
        raise KeyError(f"No image asset for key '{key}'")

    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            search_region = get_region(key)

            # 1. Take a screenshot of the broader search region
            screenshot_pil = pyautogui.screenshot(region=search_region)
            screenshot_cv = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2GRAY)

            # 2. Load the reference image (template) to find
            template_cv = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if template_cv is None:
                logger.error(f"Could not load reference image for key '{key}' at path: {image_path}")
                return None

            # 3. Perform template matching
            result = cv2.matchTemplate(screenshot_cv, template_cv, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            # 4. If a match is found, define the OCR area and extract text
            if max_val >= CONFIDENCE_LEVEL:
                logger.info(f"✅ Found '{key}' with confidence {max_val:.2f} at {max_loc} within the region.")

                # Define the OCR region relative to the found image
                # This crops the original screenshot (in PIL format)
                # It starts from the right edge of the found image to the right edge of the search area
                match_width = template_cv.shape[1]
                ocr_left = max_loc[0] + match_width
                ocr_top = max_loc[1]
                ocr_right = screenshot_pil.width  # Extends to the end of the search region
                ocr_bottom = max_loc[1] + template_cv.shape[0]

                # Crop the screenshot to get the OCR area
                ocr_image = screenshot_pil.crop((ocr_left, ocr_top, ocr_right, ocr_bottom))

                # For debugging, you can save the cropped image
                # ocr_image.save(f"debug_ocr_crop_{key}.png")

                # 5. Extract text using Tesseract
                text = pytesseract.image_to_string(ocr_image, config='--psm 7').strip()
                logger.info(f"✅ Extracted Text: '{text}'")
                return text

        except Exception as e:
            logger.error(f"An error occurred in find_image_and_get_text for '{key}': {e}", exc_info=True)
            break  # Exit loop on unexpected error

        time.sleep(0.5)

    logger.error(f"❌ Timed out after {timeout}s. Could not find '{key}'.")
    _save_failure_screenshot(key)
    return None
def paste_from_clipboard() -> bool:
    """
    Gets text from the clipboard and types it out character by character.
    This is often more reliable than a direct paste (Ctrl+V) command.
    """
    logger.info("--- Task: Retyping from clipboard ---")
    try:
        text = pyperclip.paste().strip()
        if text:
            pyautogui.write(text, interval=0.05)  # Type with a small delay between keys
            logger.info("✅ Retyped content from clipboard.")
            return True
        else:
            logger.warning("Clipboard was empty. Nothing to retype.")
            # Returning True because the action itself didn't fail
            return True
    except Exception as e:
        logger.error(f"Failed to retype from clipboard: {e}", exc_info=True)
        return False


def find_and_click(key: str, timeout: int = DEFAULT_TIMEOUT, clicks: int = 1) -> bool:
    image_path = IMAGE_ASSETS.get(key)
    if not image_path: raise KeyError(f"No image asset for key '{key}'")
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            region = get_region(key) 
            loc = pyautogui.locateCenterOnScreen(image_path, confidence=CONFIDENCE_LEVEL, region=region, grayscale=True)
            if loc:
                logger.info(f"✅ Found '{key}' at {loc}. Clicking.")
                pyautogui.click(loc, clicks=clicks)
                return True
        except pyautogui.ImageNotFoundException: pass
        except Exception as e: logger.error(f"Error in find_and_click for '{key}': {e}", exc_info=True); break
        time.sleep(0.5)
    logger.error(f"❌ Timed out after {timeout}s. Could not find '{key}'.")
    _save_failure_screenshot(key)
    return False

def find_label_and_click_offset(key: str, x_offset: int = 0, y_offset: int = 0, timeout: int = DEFAULT_TIMEOUT) -> bool:
    image_path = IMAGE_ASSETS.get(key)
    if not image_path: raise KeyError(f"No image asset for key '{key}'")
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            region = get_region(key)
            loc = pyautogui.locateCenterOnScreen(image_path, confidence=CONFIDENCE_LEVEL, region=region, grayscale=True)
            if loc:
                click_point = (loc.x + x_offset, loc.y + y_offset)
                logger.info(f"✅ Found '{key}' at {loc}. Clicking offset target at {click_point}.")
                pyautogui.click(click_point)
                return True
        except pyautogui.ImageNotFoundException: pass
        except Exception as e: logger.error(f"Error in find_label_and_click_offset for '{key}': {e}", exc_info=True); break
        time.sleep(0.5)
    logger.error(f"❌ Timed out after {timeout}s. Could not find '{key}'")
    _save_failure_screenshot(key)
    return False

def find_and_right_click(key: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
    logger.info(f"--- Task: Right-clicking {key} ---")
    image_path = IMAGE_ASSETS.get(key)
    if not image_path: raise KeyError(f"No image asset for key '{key}'")
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            region = get_region(key)
            loc = pyautogui.locateCenterOnScreen(image_path, confidence=CONFIDENCE_LEVEL, region=region, grayscale=True)
            if loc:
                pyautogui.rightClick(loc)
                logger.info(f"✅ Right-clicked '{key}' at {loc}.")
                return True
        except pyautogui.ImageNotFoundException: pass
        except Exception as e: logger.error(f"Error in find_and_right_click for '{key}': {e}", exc_info=True); break
        time.sleep(0.5)
    logger.error(f"❌ Timed out after {timeout}s. Could not find '{key}'.")
    _save_failure_screenshot(key)
    return False

def find_and_double_click_offset(key: str, x_offset: int, y_offset: int, timeout: int = DEFAULT_TIMEOUT) -> bool:
    logger.info(f"--- Task: Double-clicking offset from {key} ---")
    image_path = IMAGE_ASSETS.get(key)
    if not image_path: raise KeyError(f"No image asset for key '{key}'")
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            region = get_region(key)
            loc = pyautogui.locateCenterOnScreen(image_path, confidence=CONFIDENCE_LEVEL, region=region, grayscale=True)
            if loc:
                click_point = (loc.x + x_offset, loc.y + y_offset)
                pyautogui.doubleClick(click_point)
                logger.info(f"✅ Double-clicked offset from '{key}' at {click_point}.")
                return True
        except pyautogui.ImageNotFoundException: pass
        except Exception as e: logger.error(f"Error in find_and_double_click_offset for '{key}': {e}", exc_info=True); break
        time.sleep(0.5)
    logger.error(f"❌ Timed out after {timeout}s. Could not find '{key}'.")
    _save_failure_screenshot(key)
    return False

def find_and_move_to(key: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
    logger.info(f"--- Task: Moving mouse to {key} ---")
    image_path = IMAGE_ASSETS.get(key)
    if not image_path: raise KeyError(f"No image asset for key '{key}'")
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            region = get_region(key)
            loc = pyautogui.locateCenterOnScreen(image_path, confidence=CONFIDENCE_LEVEL, region=region, grayscale=True)
            if loc:
                pyautogui.moveTo(loc)
                logger.info(f"✅ Moved mouse to '{key}' at {loc}.")
                return True
        except pyautogui.ImageNotFoundException: pass
        except Exception as e: logger.error(f"Error in find_and_move_to for '{key}': {e}", exc_info=True); break
        time.sleep(0.5)
    logger.error(f"❌ Timed out after {timeout}s. Could not find '{key}'.")
    _save_failure_screenshot(key)
    return False

def wait_for_image(key: str, timeout: int = 10) -> bool:
    logger.info(f"--- Task: Waiting for {key} to appear ---")
    image_path = IMAGE_ASSETS.get(key)
    if not image_path: raise KeyError(f"No image asset for key '{key}'")
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            region = get_region(key)
            if pyautogui.locateOnScreen(image_path, confidence=CONFIDENCE_LEVEL, region=region, grayscale=True):
                logger.info(f"✅ Found '{key}'.")
                return True
        except pyautogui.ImageNotFoundException: pass
        except Exception as e: logger.error(f"Error in wait_for_image for '{key}': {e}", exc_info=True); break
        time.sleep(0.5)
    logger.error(f"❌ Timed out after {timeout}s waiting for '{key}'.")
    return False

def find_image_in_region(image_key: str, region_key: str, action: str = "click", timeout: int = DEFAULT_TIMEOUT) -> bool:
    """
    Finds an image within a specified region and performs the specified action.
    Uses the same region dimensions as find_aden_window for drawing the region box and for the search,
    while using the selected target for determining what to search for.

    Args:
        image_key (str): The key for the image asset to find.
        region_key (str): The key for the region to search in (used only for logging).
        action (str): The action to perform when the image is found (click, double_click, right_click, move_to, get_text).
        timeout (int): How long to search for the image.

    Returns:
        bool: True if the image is found and the action is performed successfully, False otherwise.
        If action is "get_text", returns the extracted text if found, None otherwise.
    """
    logger.info(f"--- Task: Finding '{image_key}' in region '{region_key}' and performing '{action}' ---")
    image_path = IMAGE_ASSETS.get(image_key)
    if not image_path: 
        raise KeyError(f"No image asset for key '{image_key}'")

    # Get the ADEN window region for drawing the region box and for the search
    aden_window = find_aden_window()
    if not aden_window:
        logger.error("Cannot find image in region because the main ADEN window was not found.")
        return False

    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            # Use the ADEN window region for the search
            region = aden_window
            loc = pyautogui.locateCenterOnScreen(image_path, confidence=CONFIDENCE_LEVEL, region=region, grayscale=True)

            if loc:
                logger.info(f"✅ Found '{image_key}' at {loc} in region '{region_key}'.")

                if action == "click" or action == "click_center":
                    pyautogui.click(loc)
                    logger.info(f"Clicked on '{image_key}'.")
                    return True
                elif action == "double_click" or action == "double_click_center":
                    pyautogui.doubleClick(loc)
                    logger.info(f"Double-clicked on '{image_key}'.")
                    return True
                elif action == "right_click" or action == "right_click_center":
                    pyautogui.rightClick(loc)
                    logger.info(f"Right-clicked on '{image_key}'.")
                    return True
                elif action == "move_to" or action == "move_to_target":
                    pyautogui.moveTo(loc)
                    logger.info(f"Moved to '{image_key}'.")
                    return True
                elif action == "get_text":
                    # Take a screenshot of the region
                    # For get_text action, we still want to use the selected target region
                    # to get more accurate OCR results
                    try:
                        target_region = get_region(region_key)
                        screenshot = pyautogui.screenshot(region=target_region)
                    except Exception:
                        # Fallback to ADEN window region if target region is not available
                        screenshot = pyautogui.screenshot(region=region)

                    # Convert to grayscale for OCR
                    screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)

                    # Extract text using Tesseract
                    text = pytesseract.image_to_string(screenshot_cv).strip()
                    logger.info(f"Extracted text from region: '{text}'")
                    return text
                else:
                    logger.warning(f"Unknown action '{action}'. No action performed.")
                    return True  # Return True because the image was found

        except pyautogui.ImageNotFoundException: 
            pass
        except Exception as e: 
            logger.error(f"Error in find_image_in_region for '{image_key}' in '{region_key}': {e}", exc_info=True)
            break

        time.sleep(0.5)

    logger.error(f"❌ Timed out after {timeout}s. Could not find '{image_key}' in region '{region_key}'.")
    _save_failure_screenshot(image_key)
    return False
