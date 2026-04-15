from PyQt5.QtWidgets import *
from PyQt5.QtCore import QSize, Qt``

# Only needed for access to command line arguments
import sys

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("raspberyboo")
        button = QPushButton("Press Me!")

        self.setFixedSize(QSize(400,300))

        self.setCentralWidget(button)

app = QApplication(sys.argv) # instance of QApplication with command line arguments

# creates window 
window = MainWindow()
window.show()

# Start the event loop.
app.exec()