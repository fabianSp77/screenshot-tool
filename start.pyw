"""
Startet das Screenshot-Tool ohne CMD-Fenster (Windows).
Doppelklick auf diese Datei genügt.
"""
import subprocess
import sys
import os

script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      'screenshot_tool.py')
subprocess.Popen([sys.executable, script])
