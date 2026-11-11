#!/usr/bin/env python3
"""
Graphical application that executes the active macro whenever the Arduino buzzer is pressed.

Usage:  python3 main.py
"""

import sys

from PyQt5.QtWidgets import QApplication

from macro_window import MacroWindow


def main():
    app = QApplication(sys.argv)
    window = MacroWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
