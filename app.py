"""FixMate-AI desktop application entry point."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from storage.database import initialize_database
from ui.main_window import MainWindow


def main() -> int:
    initialize_database()

    app = QApplication(sys.argv)
    app.setApplicationName("FixMate-AI")
    app.setOrganizationName("FixMate-AI")
    app.setApplicationDisplayName("FixMate-AI")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
