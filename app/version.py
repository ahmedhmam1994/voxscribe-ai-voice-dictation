"""Single source of truth for the app version.

Read by the update checker (core/updater.py) and the crash reporter
(core/crash_reporter.py). installer.iss's MyAppVersion is compiled
separately by Inno Setup and must be bumped by hand alongside this.
"""

__version__ = "1.5"
