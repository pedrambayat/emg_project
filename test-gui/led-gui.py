import sys
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)
from PyQt5.QtCore import Qt

GPIO_PIN = 12 # change to whichever BCM pin your LED is wired to

try:
    from gpiozero import LED as GpioLED
    gpio_led = GpioLED(GPIO_PIN)
    GPIO_AVAILABLE = True
except Exception:
    gpio_led = None
    GPIO_AVAILABLE = False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LED Toggle")
        self.resize(400, 150)

        self.led_on = False

        # Toggle button
        self.toggle_btn = QPushButton("Toggle LED")
        self.toggle_btn.setMinimumHeight(80)
        self.toggle_btn.clicked.connect(self.toggle_led)

        # Status row: "LED State:" label on left, state value on right
        self.state_label = QLabel("LED State:")
        self.state_value = QLabel("OFF")

        status_layout = QHBoxLayout()
        status_layout.addWidget(self.state_label)
        status_layout.addStretch()
        status_layout.addWidget(self.state_value)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.toggle_btn)
        main_layout.addLayout(status_layout)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def toggle_led(self):
        self.led_on = not self.led_on

        if GPIO_AVAILABLE:
            # gpiozero LED.on() / LED.off() drive the GPIO pin high/low
            if self.led_on:
                gpio_led.on()
            else:
                gpio_led.off()

        self.state_value.setText("ON" if self.led_on else "OFF")

    def closeEvent(self, event):
        # Release the GPIO pin cleanly when the window is closed
        if GPIO_AVAILABLE:
            gpio_led.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
