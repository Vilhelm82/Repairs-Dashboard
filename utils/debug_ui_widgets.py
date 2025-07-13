# debug_ui_widgets.py
import tkinter as tk
from tkinter import ttk
import logging

class TextHandler(logging.Handler):
    """A logging handler that directs log records to a Tkinter text widget."""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        # It's good practice for the handler not to change the widget's state initially.
        # The widget should be configured by the code that creates it.

    def emit(self, record):
        try:
            msg = self.format(record) + "\n"
            # The after(0,...) call is crucial to prevent thread-related Tkinter errors
            # It safely schedules the UI update on the main Tkinter thread.
            self.text_widget.master.after(0, self._update_widget, msg)
        except Exception:
            # Handle cases where the widget might be destroyed
            pass
            
    def _update_widget(self, msg):
        # Only auto-scroll if the view is already at the bottom
        scroll_pos = self.text_widget.yview()[1]
        
        self.text_widget.configure(state='normal')
        self.text_widget.insert(tk.END, msg)
        
        if scroll_pos >= 1.0:
            self.text_widget.see(tk.END)
        self.text_widget.configure(state='disabled')

class ScreenOverlay:
    """A transparent, colored Toplevel window to act as an on-screen overlay."""
    def __init__(self, x, y, w, h, c="red"):
        self.root = tk.Toplevel()
        self.root.attributes("-alpha", 0.4)
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        cv = tk.Canvas(self.root, bg=c, highlightthickness=0)
        cv.pack(fill="both", expand=True)

    def close(self):
        if self.root:
            self.root.destroy()
            self.root = None

class CustomSpinbox(ttk.Frame):
    """A custom spinbox with different increments for a single click vs. holding the button."""
    def __init__(self, master, from_=0, to=4000, textvariable=None, **kwargs):
        super().__init__(master, **kwargs)
        self.textvariable = textvariable
        self.from_ = from_
        self.to = to
        self._repeat_delay = 500  # ms before rapid-change starts
        self._repeat_interval = 100 # ms between rapid changes
        self._timer = None

        self.entry = ttk.Entry(self, textvariable=self.textvariable, width=8)
        self.entry.pack(side="left", fill="x", expand=True)

        button_frame = ttk.Frame(self)
        button_frame.pack(side="left")

        # Using smaller text for up/down arrows
        self.up_button = ttk.Button(button_frame, text="▲", width=2, style="Toolbutton")
        self.up_button.pack(side="top", fill="x", padx=(1,0))

        self.down_button = ttk.Button(button_frame, text="▼", width=2, style="Toolbutton")
        self.down_button.pack(side="top", fill="x", padx=(1,0))

        self.up_button.bind("<ButtonPress-1>", lambda e: self.start_repeat(1))
        self.up_button.bind("<ButtonRelease-1>", self.stop_repeat)
        self.down_button.bind("<ButtonPress-1>", lambda e: self.start_repeat(-1))
        self.down_button.bind("<ButtonRelease-1>", self.stop_repeat)

    def start_repeat(self, direction):
        # First action is a single increment
        self.step(direction, 1)
        # Schedule the rapid-change mechanism
        self._timer = self.after(self._repeat_delay, lambda: self.repeat_step(direction))

    def repeat_step(self, direction):
        # Subsequent actions are larger increments
        self.step(direction, 10)
        self._timer = self.after(self._repeat_interval, lambda: self.repeat_step(direction))

    def stop_repeat(self, event=None):
        if self._timer:
            self.after_cancel(self._timer)
            self._timer = None

    def step(self, direction, amount):
        try:
            current_value = int(self.textvariable.get())
            new_value = current_value + (direction * amount)
            # Ensure the new value is within the defined from/to range
            new_value = max(self.from_, min(new_value, self.to))
            self.textvariable.set(new_value)
        except (tk.TclError, ValueError):
            # If the current value is invalid, reset to the starting point
            self.textvariable.set(self.from_)
class RightClickMenu(tk.Menu):
    """A reusable right-click context menu for widgets."""
    def __init__(self, parent):
        super().__init__(parent, tearoff=0)

    def show(self, event):
        """Displays the menu at the cursor's position."""
        try:
            self.tk_popup(event.x_root, event.y_root)
        finally:
            self.grab_release()

class ClosableTab(ttk.Frame):
    """A custom widget for a notebook tab that includes a close button."""
    def __init__(self, parent, title: str, command):
        """
        Initializes the ClosableTab.
        :param parent: The parent notebook widget.
        :param title: The text to be displayed on the tab.
        :param command: The function to be called when the close button is pressed.
        """
        super().__init__(parent)

        self.label = ttk.Label(self, text=title)
        self.label.pack(side="left", padx=(5, 2), pady=2)

        # Use a small 'x' for the close button
        self.close_button = ttk.Button(
            self,
            text="✕",
            command=command,
            style="Toolbutton" # Use a minimal button style
        )
        self.close_button.pack(side="left", padx=(2, 5), pady=2)