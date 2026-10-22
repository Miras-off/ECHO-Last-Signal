"""Compatibility script. Use generate_soundtrack.py for the current audio pack."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('generate_soundtrack.py')),run_name='__main__')
