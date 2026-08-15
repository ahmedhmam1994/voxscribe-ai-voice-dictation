"""Entry point for the VoxScribe desktop app."""

import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()  # noqa: F841 -- kept alive by the reference here
    # Start hidden to the tray -- no window pops up on launch. Use the tray
    # icon's "Show Window" entry, or F9 anywhere, to interact with it.
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
