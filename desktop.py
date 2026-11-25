"""Select the native desktop services without loading another platform's APIs."""
import sys

from shortcuts import DEFAULT_SHORTCUT, Shortcut

if sys.platform == "win32":
    from windows import AppInstance, BrowserCapture, downloads_folder, set_title_bar_colors, show_file
else:
    from unix_desktop import AppInstance, BrowserCapture, downloads_folder, set_title_bar_colors, show_file
