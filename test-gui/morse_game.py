"""
morse_game.py — Starter GUI for the EMG Morse Code Game

Controls (keyboard, for development):
  Space bar  → simulate EMG muscle contraction (press & hold = dash, tap = dot)

On Raspberry Pi the gpiozero Button on GPIO_PIN replaces the keyboard so that
a muscle contraction (EMG) drives the same press/release events.

Timing:
  Press duration < DOT_THRESHOLD ms  → dot  (.)
  Press duration >= DOT_THRESHOLD ms → dash (-)
  No input for LETTER_PAUSE ms after last symbol → submit guess
"""

import sys
import random
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt5.QtCore import Qt, QTimer, QElapsedTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont

# ── GPIO / EMG input ──────────────────────────────────────────────────────────
GPIO_PIN = 22  # BCM pin wired to the EMG trigger (change as needed)

try:
    from gpiozero import Button as GpioButton
    _gpio_btn = GpioButton(GPIO_PIN, pull_up=True)
    GPIO_AVAILABLE = True
except Exception:
    _gpio_btn = None
    GPIO_AVAILABLE = False

# ── Morse code table ──────────────────────────────────────────────────────────
MORSE = {
    'A': '.-',   'B': '-...', 'C': '-.-.', 'D': '-..',  'E': '.',
    'F': '..-.', 'G': '--.',  'H': '....', 'I': '..',   'J': '.---',
    'K': '-.-',  'L': '.-..', 'M': '--',   'N': '-.',   'O': '---',
    'P': '.--.', 'Q': '--.-', 'R': '.-.',  'S': '...',  'T': '-',
    'U': '..-',  'V': '...-', 'W': '.--',  'X': '-..-', 'Y': '-.--',
    'Z': '--..',
}

# ── Timing constants (ms) ─────────────────────────────────────────────────────
DOT_THRESHOLD = 300   # presses shorter than this are dots
LETTER_PAUSE  = 800   # silence after last symbol triggers auto-submit


class _GpioSignals(QObject):
    pressed  = pyqtSignal()
    released = pyqtSignal()

_gpio_signals = _GpioSignals()


class MorseGameWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EMG Morse Code Game")
        self.resize(500, 400)

        self.target_letter = ""
        self.current_input = ""
        self.score         = 0
        self.total         = 0
        self.game_running  = False

        self._press_timer = QElapsedTimer()
        self._pause_timer = QTimer()
        self._pause_timer.setSingleShot(True)
        self._pause_timer.timeout.connect(self._on_letter_pause)

        self._result_timer = QTimer()
        self._result_timer.setSingleShot(True)
        self._result_timer.timeout.connect(self._next_letter)


        self._build_ui()

        _gpio_signals.pressed.connect(self._on_press)
        _gpio_signals.released.connect(self._on_release)

        if GPIO_AVAILABLE:
            _gpio_btn.when_pressed  = _gpio_signals.pressed.emit
            _gpio_btn.when_released = _gpio_signals.released.emit

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(20, 20, 20, 20)
        main.setSpacing(12)

        self.title_label = QLabel("EMG Morse Code Game")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(QFont("Helvetica", 18, QFont.Bold))
        main.addWidget(self.title_label)

        score_row = QHBoxLayout()
        self.score_label = QLabel("Score: 0 / 0")
        self.score_label.setFont(QFont("Helvetica", 11))
        gpio_lbl = QLabel("GPIO: on" if GPIO_AVAILABLE else "GPIO: off (keyboard mode)")
        gpio_lbl.setFont(QFont("Helvetica", 11))
        score_row.addWidget(self.score_label)
        score_row.addStretch()
        score_row.addWidget(gpio_lbl)
        main.addLayout(score_row)

        main.addWidget(self._hline())

        lbl_target = QLabel("Target Letter")
        lbl_target.setAlignment(Qt.AlignCenter)
        lbl_target.setFont(QFont("Helvetica", 11))
        main.addWidget(lbl_target)

        self.target_display = QLabel("—")
        self.target_display.setAlignment(Qt.AlignCenter)
        self.target_display.setFont(QFont("Courier", 72, QFont.Bold))
        main.addWidget(self.target_display)

        self.morse_hint = QLabel("")
        self.morse_hint.setAlignment(Qt.AlignCenter)
        self.morse_hint.setFont(QFont("Courier", 22))
        main.addWidget(self.morse_hint)

        main.addWidget(self._hline())

        lbl_input = QLabel("Your Input")
        lbl_input.setAlignment(Qt.AlignCenter)
        lbl_input.setFont(QFont("Helvetica", 11))
        main.addWidget(lbl_input)

        self.input_display = QLabel("")
        self.input_display.setAlignment(Qt.AlignCenter)
        self.input_display.setFont(QFont("Courier", 28))
        main.addWidget(self.input_display)

        self.result_label = QLabel("")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setFont(QFont("Helvetica", 13))
        self.result_label.setMinimumHeight(28)
        main.addWidget(self.result_label)

        hint = QLabel("Press button to input  (tap = dot  |  hold = dash)  —  release after last symbol to submit")
        hint.setAlignment(Qt.AlignCenter)
        hint.setFont(QFont("Helvetica", 9))
        main.addWidget(hint)

        main.addWidget(self._hline())

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self._start_game)

        self.skip_btn = QPushButton("Skip")
        self.skip_btn.clicked.connect(self._next_letter)
        self.skip_btn.setEnabled(False)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self._reset_game)
        self.reset_btn.setEnabled(False)

        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.skip_btn)
        btn_row.addWidget(self.reset_btn)
        main.addLayout(btn_row)

    def _hline(self):
        from PyQt5.QtWidgets import QFrame
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    # ── Game logic ─────────────────────────────────────────────────────────────
    def _start_game(self):
        self.score = 0
        self.total = 0
        self.game_running = True
        self.start_btn.setEnabled(False)
        self.skip_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        self._next_letter()

    def _next_letter(self):
        self._result_timer.stop()
        self._pause_timer.stop()
        self.current_input = ""
        self.target_letter = random.choice(list(MORSE.keys()))
        self.target_display.setText(self.target_letter)
        self.morse_hint.setText(MORSE[self.target_letter])
        self.input_display.setText("")
        self.result_label.setText("")
        self.skip_btn.setEnabled(True)
        self._update_score_label()

    def _reset_game(self):
        self._pause_timer.stop()
        self._result_timer.stop()
        self.game_running = False
        self.score = 0
        self.total = 0
        self.current_input = ""
        self.target_letter = ""
        self.target_display.setText("—")
        self.morse_hint.setText("")
        self.input_display.setText("")
        self.result_label.setText("")
        self.score_label.setText("Score: 0 / 0")
        self.start_btn.setEnabled(True)
        self.skip_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)

    def _on_press(self):
        if not self.game_running:
            return
        self._pause_timer.stop()
        self._press_timer.start()

    def _on_release(self):
        if not self.game_running:
            return
        duration = self._press_timer.elapsed()
        symbol = "." if duration < DOT_THRESHOLD else "-"
        self.current_input += symbol
        self.input_display.setText(self.current_input)
        self._pause_timer.start(LETTER_PAUSE)

    def _on_letter_pause(self):
        if not self.current_input:
            return
        self._submit()

    def _submit(self):
        self._pause_timer.stop()
        self.total += 1
        correct = MORSE.get(self.target_letter, "")
        if self.current_input == correct:
            self.score += 1
            self.result_label.setText(f"Correct!  {self.current_input} = {self.target_letter}")
        else:
            decoded = {v: k for k, v in MORSE.items()}.get(self.current_input, "?")
            self.result_label.setText(
                f"Wrong — got '{self.current_input}' ({decoded}), expected '{correct}'"
            )
        self._update_score_label()
        self.skip_btn.setEnabled(False)
        self._result_timer.start(1800)

    def _update_score_label(self):
        pct = int(self.score / self.total * 100) if self.total else 0
        self.score_label.setText(f"Score: {self.score} / {self.total}  ({pct}%)")

    def closeEvent(self, event):
        if GPIO_AVAILABLE:
            _gpio_btn.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MorseGameWindow()
    window.show()
    sys.exit(app.exec())
