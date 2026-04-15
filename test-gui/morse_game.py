"""
morse_game.py — Starter GUI for the EMG Morse Code Game

Controls (keyboard, for development):
  Space bar  → simulate EMG muscle contraction (press & hold = dash, tap = dot)

On Raspberry Pi the gpiozero Button on GPIO_PIN replaces the keyboard so that
a muscle contraction (EMG) drives the same press/release events.

Timing:
  Press duration < DOT_THRESHOLD ms  → dot  (·)
  Press duration ≥ DOT_THRESHOLD ms  → dash (—)
  No input for LETTER_PAUSE ms after last symbol → submit guess
"""

import sys
import random
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PyQt5.QtCore import Qt, QTimer, QElapsedTimer
from PyQt5.QtGui import QFont, QColor, QPalette

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
DOT_THRESHOLD  = 300   # presses shorter than this are dots
LETTER_PAUSE   = 800   # silence after last symbol triggers auto-submit

# ── Colours ───────────────────────────────────────────────────────────────────
CLR_BG         = "#1e1e2e"
CLR_PANEL      = "#2a2a3e"
CLR_ACCENT     = "#89b4fa"   # blue
CLR_SUCCESS    = "#a6e3a1"   # green
CLR_FAIL       = "#f38ba8"   # red
CLR_TEXT       = "#cdd6f4"
CLR_SUBTEXT    = "#6c7086"
CLR_DOT_DASH   = "#fab387"   # orange


class MorseGameWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EMG Morse Code Game")
        self.resize(700, 560)
        self._apply_palette()

        # ── State ─────────────────────────────────────────────────────────────
        self.target_letter  = ""
        self.current_input  = ""   # dots and dashes typed so far for this letter
        self.score          = 0
        self.total          = 0
        self.game_running   = False

        # ── Timers ────────────────────────────────────────────────────────────
        self._press_timer   = QElapsedTimer()   # how long the key is held
        self._pause_timer   = QTimer()           # detect end-of-symbol silence
        self._pause_timer.setSingleShot(True)
        self._pause_timer.timeout.connect(self._on_letter_pause)

        self._result_timer  = QTimer()           # show result briefly then advance
        self._result_timer.setSingleShot(True)
        self._result_timer.timeout.connect(self._next_letter)

        # ── Build UI ──────────────────────────────────────────────────────────
        self._build_ui()

        # ── GPIO hook (Raspberry Pi) ──────────────────────────────────────────
        if GPIO_AVAILABLE:
            _gpio_btn.when_pressed  = self._on_press
            _gpio_btn.when_released = self._on_release

    # ── UI construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QWidget()
        root.setStyleSheet(f"background-color: {CLR_BG};")
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(24, 24, 24, 24)
        main.setSpacing(16)

        # Title
        title = QLabel("EMG Morse Code Game")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Helvetica", 22, QFont.Bold))
        title.setStyleSheet(f"color: {CLR_ACCENT};")
        main.addWidget(title)

        # Score row
        score_row = QHBoxLayout()
        self.score_label = QLabel("Score: 0 / 0")
        self.score_label.setFont(QFont("Helvetica", 13))
        self.score_label.setStyleSheet(f"color: {CLR_TEXT};")
        gpio_status = QLabel("GPIO: READY" if GPIO_AVAILABLE else "GPIO: off (keyboard mode)")
        gpio_status.setFont(QFont("Helvetica", 11))
        gpio_status.setStyleSheet(f"color: {'#a6e3a1' if GPIO_AVAILABLE else CLR_SUBTEXT};")
        score_row.addWidget(self.score_label)
        score_row.addStretch()
        score_row.addWidget(gpio_status)
        main.addLayout(score_row)

        # Target letter panel
        target_panel = self._panel()
        target_layout = QVBoxLayout(target_panel)
        target_layout.setContentsMargins(16, 16, 16, 16)

        lbl = QLabel("Target Letter")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFont(QFont("Helvetica", 11))
        lbl.setStyleSheet(f"color: {CLR_SUBTEXT};")
        target_layout.addWidget(lbl)

        self.target_display = QLabel("—")
        self.target_display.setAlignment(Qt.AlignCenter)
        self.target_display.setFont(QFont("Courier", 80, QFont.Bold))
        self.target_display.setStyleSheet(f"color: {CLR_TEXT};")
        target_layout.addWidget(self.target_display)

        self.morse_hint = QLabel("")
        self.morse_hint.setAlignment(Qt.AlignCenter)
        self.morse_hint.setFont(QFont("Courier", 24))
        self.morse_hint.setStyleSheet(f"color: {CLR_DOT_DASH};")
        target_layout.addWidget(self.morse_hint)

        main.addWidget(target_panel)

        # Current input panel
        input_panel = self._panel()
        input_layout = QVBoxLayout(input_panel)
        input_layout.setContentsMargins(16, 12, 16, 12)

        lbl2 = QLabel("Your Input")
        lbl2.setAlignment(Qt.AlignCenter)
        lbl2.setFont(QFont("Helvetica", 11))
        lbl2.setStyleSheet(f"color: {CLR_SUBTEXT};")
        input_layout.addWidget(lbl2)

        self.input_display = QLabel("·  ·  ·")
        self.input_display.setAlignment(Qt.AlignCenter)
        self.input_display.setFont(QFont("Courier", 32))
        self.input_display.setStyleSheet(f"color: {CLR_DOT_DASH};")
        input_layout.addWidget(self.input_display)

        main.addWidget(input_panel)

        # Result / status label
        self.result_label = QLabel("")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setFont(QFont("Helvetica", 16, QFont.Bold))
        self.result_label.setStyleSheet(f"color: {CLR_TEXT};")
        self.result_label.setMinimumHeight(32)
        main.addWidget(self.result_label)

        # Instructions
        hint_text = (
            "SPACE to press  (tap = dot · | hold = dash —)   "
            "Release after last symbol to auto-submit"
        )
        hint = QLabel(hint_text)
        hint.setAlignment(Qt.AlignCenter)
        hint.setFont(QFont("Helvetica", 10))
        hint.setStyleSheet(f"color: {CLR_SUBTEXT};")
        main.addWidget(hint)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.start_btn = QPushButton("Start Game")
        self.start_btn.setMinimumHeight(48)
        self.start_btn.setFont(QFont("Helvetica", 13, QFont.Bold))
        self.start_btn.setStyleSheet(self._btn_style(CLR_ACCENT))
        self.start_btn.clicked.connect(self._start_game)

        self.skip_btn = QPushButton("Skip")
        self.skip_btn.setMinimumHeight(48)
        self.skip_btn.setFont(QFont("Helvetica", 13))
        self.skip_btn.setStyleSheet(self._btn_style(CLR_SUBTEXT))
        self.skip_btn.clicked.connect(self._next_letter)
        self.skip_btn.setEnabled(False)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setMinimumHeight(48)
        self.reset_btn.setFont(QFont("Helvetica", 13))
        self.reset_btn.setStyleSheet(self._btn_style(CLR_FAIL))
        self.reset_btn.clicked.connect(self._reset_game)
        self.reset_btn.setEnabled(False)

        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.skip_btn)
        btn_row.addWidget(self.reset_btn)
        main.addLayout(btn_row)

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
        self.target_display.setStyleSheet(f"color: {CLR_TEXT};")
        self.morse_hint.setText(MORSE[self.target_letter])
        self.input_display.setText("")
        self.result_label.setText("")
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
        self.target_display.setStyleSheet(f"color: {CLR_TEXT};")
        self.morse_hint.setText("")
        self.input_display.setText("·  ·  ·")
        self.result_label.setText("")
        self.score_label.setText("Score: 0 / 0")
        self.start_btn.setEnabled(True)
        self.skip_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)

    def _on_press(self):
        """Called when EMG contraction (or Space key) starts."""
        if not self.game_running:
            return
        self._pause_timer.stop()
        self._press_timer.start()

    def _on_release(self):
        """Called when EMG contraction (or Space key) ends."""
        if not self.game_running:
            return
        duration = self._press_timer.elapsed()
        symbol = "." if duration < DOT_THRESHOLD else "-"
        self.current_input += symbol
        self._refresh_input_display()
        # Restart pause timer — if no new press arrives, auto-submit
        self._pause_timer.start(LETTER_PAUSE)

    def _on_letter_pause(self):
        """Silence timeout → submit current input as the player's guess."""
        if not self.current_input:
            return
        self._submit()

    def _submit(self):
        self._pause_timer.stop()
        self.total += 1
        correct_morse = MORSE.get(self.target_letter, "")
        if self.current_input == correct_morse:
            self.score += 1
            self.result_label.setText(f"✓  Correct!  {self.current_input} = {self.target_letter}")
            self.result_label.setStyleSheet(f"color: {CLR_SUCCESS};")
            self.target_display.setStyleSheet(f"color: {CLR_SUCCESS};")
        else:
            decoded = self._decode(self.current_input)
            self.result_label.setText(
                f"✗  Got '{self.current_input}' ({decoded})  —  expected '{correct_morse}'"
            )
            self.result_label.setStyleSheet(f"color: {CLR_FAIL};")
            self.target_display.setStyleSheet(f"color: {CLR_FAIL};")
        self._update_score_label()
        self.skip_btn.setEnabled(False)
        self._result_timer.start(1800)   # show result 1.8 s then advance

    def _decode(self, morse_str):
        reverse = {v: k for k, v in MORSE.items()}
        return reverse.get(morse_str, "?")

    # ── Display helpers ────────────────────────────────────────────────────────
    def _refresh_input_display(self):
        pretty = "  ".join(
            "·" if s == "." else "—" for s in self.current_input
        )
        self.input_display.setText(pretty)

    def _update_score_label(self):
        pct = int(self.score / self.total * 100) if self.total else 0
        self.score_label.setText(f"Score: {self.score} / {self.total}  ({pct}%)")

    # ── Keyboard event (development mode) ─────────────────────────────────────
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._on_press()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._on_release()

    # ── Cleanup ────────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        if GPIO_AVAILABLE:
            _gpio_btn.close()
        event.accept()

    # ── Style helpers ──────────────────────────────────────────────────────────
    def _panel(self):
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background-color: {CLR_PANEL}; border-radius: 10px; }}"
        )
        return frame

    @staticmethod
    def _btn_style(color):
        return (
            f"QPushButton {{"
            f"  background-color: {color}; color: {CLR_BG};"
            f"  border-radius: 8px; padding: 6px 18px;"
            f"}}"
            f"QPushButton:disabled {{"
            f"  background-color: {CLR_SUBTEXT}; color: {CLR_BG};"
            f"}}"
            f"QPushButton:pressed {{ opacity: 0.8; }}"
        )

    def _apply_palette(self):
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor(CLR_BG))
        self.setPalette(pal)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MorseGameWindow()
    window.show()
    sys.exit(app.exec())
