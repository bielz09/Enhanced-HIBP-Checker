import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    """
    Initializes and runs the PyQt6 application.
    Sets up the main window and starts the application event loop.
    """
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    exit_code = app.exec()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()