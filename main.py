"""Entry point for the VoxScribe desktop app."""

import sys

from PySide6.QtCore import QSharedMemory
from PySide6.QtWidgets import QApplication, QMessageBox

from app.main_window import MainWindow

# Fixed key -- create() fails with AlreadyExists if another VoxScribe process
# already holds this segment. Catches a second launch (e.g. the old instance
# still hiding in the tray after the window was merely closed, not quit)
# instead of silently running two copies that both grab the global F9
# hotkey -- which sends every recording to Whisper and every typed result
# to the focused window twice, interleaved, garbling the output.
_SINGLE_INSTANCE_KEY = "VoxScribe-SingleInstanceGuard-8f3c1a"


def main() -> int:
    app = QApplication(sys.argv)

    guard = QSharedMemory(_SINGLE_INSTANCE_KEY)
    if not guard.create(1):
        QMessageBox.warning(
            None,
            "VoxScribe",
            "VoxScribe is already running. Check the system tray.",
        )
        return 0

    window = MainWindow()  # noqa: F841 -- kept alive by the reference here
    # Start hidden to the tray -- no window pops up on launch. Use the tray
    # icon's "Show Window" entry, or F9 anywhere, to interact with it.
    result = app.exec()
    guard.detach()
    return result


if __name__ == "__main__":
    sys.exit(main())
