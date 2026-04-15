from PyQt5.QtWidgets import *
from PyQt5.QtCore import QSize, Qt

# Only needed for access to command line arguments
import sys

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.button_is_checked = True

        self.setWindowTitle("raspberyboo")
        button = QPushButton("Press Me!")
        button.setCheckable(True)
        button.clicked.connect(self.the_button_was_clicked)
        button.clicked.connect(self.the_button_was_toggled)

        self.setFixedSize(QSize(400,300))

        self.setCentralWidget(button)

    def the_button_was_clicked(self):
        print("clicked")
    
    def the_button_was_toggled(self, checked):
        self.button_is_checked = checked
        # print("Checked?", checked)
        print(self.button_is_checked)
    
    def the_button_was_released(self):
        self.button_is_checked = self.button.isChecked()
        print(self.button_is_checkeD)

app = QApplication(sys.argv) # instance of QApplication with command line arguments

# creates window 
window = MainWindow()
window.show()

# Start the event loop.
app.exec()