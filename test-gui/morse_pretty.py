import sys, random, glob, subprocess, json, os, asyncio
from collections import deque
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QCheckBox, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QTimer, QElapsedTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
import qasync

from sys import platform

if platform == "win32":
    try:
        from bleak.backends.winrt.util import allow_sta
        allow_sta()
    except ImportError:
        pass

GPIO_PIN        = 22
DISPLAY_BTN_PIN = 6
SERVO_PIN       = 17
MIN_PRESS_MS    = int(os.getenv("EMG_MIN_PRESS_MS", "10"))
DOT_THRESHOLD   = int(os.getenv("EMG_DOT_THRESHOLD_MS", "100"))
LETTER_PAUSE    = int(os.getenv("EMG_LETTER_PAUSE_MS", "3000"))   # ms silence → auto-submit
CORRECT_PAUSE   = int(os.getenv("EMG_CORRECT_PAUSE_MS", "450"))
LIVES           = 3  # wrong answers allowed before game over
HISCORE_PATH    = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".morse_highscore.json")

BLE_ADDRESS             = os.getenv("EMG_BLE_ADDRESS", "80:7D:3A:85:E8:C6")
BLE_DEVICE_NAME         = os.getenv("EMG_BLE_NAME", "EMG_Sender_pbayat")
BLE_ENABLED             = os.getenv("EMG_USE_BLE", "1") != "0"
EMG_CONTROL_SOURCE      = os.getenv("EMG_CONTROL_SOURCE", "raw").lower()
BLE_SENSOR_CHAR_UUID    = "5212ddd0-29e5-11eb-adc1-0242ac120002"
BLE_CONTROL_CHAR_UUID   = "5212ddd1-29e5-11eb-adc1-0242ac120002"

# BLE_SENSOR_CHAR_UUID    = "386a83e2-28fa-11eb-adc1-0242ac120002"
# BLE_CONTROL_CHAR_UUID   = "386a83e2-28fa-11eb-adc1-0242ac120002"
BLE_RETRY_SECONDS       = 2.0
EMG_SAMPLE_RATE         = 1000
EMG_AVG_WINDOW_MS       = int(os.getenv("EMG_AVG_WINDOW_MS", "40"))
EMG_GAP_MS              = int(os.getenv("EMG_GAP_MS", "120"))
EMG_BASELINE_ALPHA      = float(os.getenv("EMG_BASELINE_ALPHA", "0.02"))
EMG_THRESHOLD_MARGIN    = float(os.getenv("EMG_THRESHOLD_MARGIN", "8"))
EMG_ACTIVE_RATIO        = float(os.getenv("EMG_ACTIVE_RATIO", "0.85"))
EMG_FIXED_THRESHOLD     = os.getenv("EMG_FIXED_THRESHOLD")
EMG_AVG_WINDOW_SAMPLES  = max(1, int(EMG_SAMPLE_RATE * EMG_AVG_WINDOW_MS / 1000))
EMG_GAP_SAMPLES         = max(1, int(EMG_SAMPLE_RATE * EMG_GAP_MS / 1000))

MORSE = {
    'A':'.-','B':'-...','C':'-.-.','D':'-..','E':'.','F':'..-.','G':'--.','H':'....','I':'..','J':'.---',
    'K':'-.-','L':'.-..','M':'--','N':'-.','O':'---','P':'.--.','Q':'--.-','R':'.-.','S':'...','T':'-',
    'U':'..-','V':'...-','W':'.--','X':'-..-','Y':'-.--','Z':'--..',
}

CORRECT_MESSAGES = [
    "Princess behavior. '{letter}' is '{morse}'.",
    "Cute and correct: '{letter}' = '{morse}'.",
    "Sparkly win. '{letter}' was '{morse}'.",
    "Glossy little genius. '{letter}' is '{morse}'.",
    "Heart eyes. '{letter}' = '{morse}'.",
]

try:
    from gpiozero import Button as GpioButton
    _btn     = GpioButton(GPIO_PIN, pull_up=True)
    _disp    = GpioButton(DISPLAY_BTN_PIN, pull_up=True)
    GPIO_OK  = True
except Exception:
    _btn = _disp = None
    GPIO_OK = False

try:
    from gpiozero import Servo
    try:
        from gpiozero.pins.pigpio import PiGPIOFactory
        _servo = Servo(SERVO_PIN, min_pulse_width=0.5/1000, max_pulse_width=2.5/1000, pin_factory=PiGPIOFactory())
    except Exception:
        _servo = Servo(SERVO_PIN, min_pulse_width=0.5/1000, max_pulse_width=2.5/1000)
    SERVO_OK = True
except Exception:
    _servo   = None
    SERVO_OK = False

class _Sig(QObject):
    pressed  = pyqtSignal()
    released = pyqtSignal()

_sig = _Sig()


class MorseGame(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EMG Baby Girl Morse Club")
        screen = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(screen.x(), screen.y(), screen.width(), int(screen.height() * 0.75))
        self.letter = ""
        self.inp    = ""
        self.score  = self.total = 0
        self.hiscore, self.hipct = self._load_hiscore()
        self.challenge_hiscore, self.challenge_hipct = self._load_hiscore(challenge=True)
        self.challenge = False
        self.lives = LIVES
        self.running = False
        self.disp_on = True
        self.ble_enabled = BLE_ENABLED
        self.ble_status = "BLE: idle"
        self._client = None
        self._ble_task = None
        self._closing = False
        self._emg_active = False
        self._input_pressed = False
        self._ble_control_active = False
        self._emg_window = deque(maxlen=EMG_AVG_WINDOW_SAMPLES)
        self._emg_window_sum = 0.0
        self._emg_mavg = None
        self._emg_baseline = None
        self._emg_threshold = None
        self._segment_active = False
        self._segment_total_samples = 0
        self._segment_above_samples = 0
        self._segment_below_gap_samples = 0
        self._banner_frames = [
            "♡ dot dot dash darling ♡",
            "♡ pretty little signal princess ♡",
            "♡ sugar, sparkle, and Morse code ♡",
            "♡ decode it, diva ♡",
        ]
        self._banner_index = 0

        self._ptimer = QElapsedTimer()
        self._pause  = QTimer(singleShot=True, timeout=self._submit)
        self._result = QTimer(singleShot=True, timeout=self._next)
        self._sparkle = QTimer(self, timeout=self._tick_banner)

        self._build()
        self._apply_theme()
        self._refresh_hi()
        self._refresh_lives()
        self._servo_to_lives()
        self._update_mode_copy()
        self._update_input_preview()
        self._set_result_message("Tap Start when you're ready to serve dots and dashes.", "neutral")
        self._tick_banner()
        self._sparkle.start(1400)
        _sig.pressed.connect(self._press)
        _sig.released.connect(self._release)
        if GPIO_OK:
            if not self.ble_enabled:
                _btn.when_pressed  = _sig.pressed.emit
                _btn.when_released = _sig.released.emit
            _disp.when_pressed = self._toggle_display
        if self.ble_enabled:
            self._set_ble_status("BLE: waiting to connect")
            QTimer.singleShot(0, self._start_ble)
        else:
            self._set_ble_status("Input: GPIO button")

    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(28, 24, 28, 24)
        v.setSpacing(14)

        self.banner_lbl = QLabel("", alignment=Qt.AlignCenter)
        self.banner_lbl.setObjectName("bannerLabel")
        self.banner_lbl.setFont(QFont("Comic Sans MS", 12, QFont.Bold))
        v.addWidget(self.banner_lbl)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 22, 28, 22)
        hero_layout.setSpacing(6)

        self.title_lbl = QLabel("Baby Girl Morse Club", alignment=Qt.AlignCenter)
        self.title_lbl.setObjectName("titleLabel")
        self.title_lbl.setFont(QFont("Comic Sans MS", 24, QFont.Bold))
        hero_layout.addWidget(self.title_lbl)

        self.subtitle_lbl = QLabel("", alignment=Qt.AlignCenter)
        self.subtitle_lbl.setObjectName("subtitleLabel")
        self.subtitle_lbl.setFont(QFont("Trebuchet MS", 11))
        self.subtitle_lbl.setWordWrap(True)
        hero_layout.addWidget(self.subtitle_lbl)

        self.decoration_lbl = QLabel("♥ ♥ ♥  pretty little nerve signals  ♥ ♥ ♥", alignment=Qt.AlignCenter)
        self.decoration_lbl.setObjectName("decorationLabel")
        self.decoration_lbl.setFont(QFont("Comic Sans MS", 10, QFont.Bold))
        hero_layout.addWidget(self.decoration_lbl)
        v.addWidget(hero)

        stats_card = QFrame()
        stats_card.setObjectName("scoreCard")
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(20, 16, 20, 16)
        stats_layout.setSpacing(12)

        h = QHBoxLayout()
        h.setSpacing(12)
        self.score_lbl = QLabel("Current Score: 0 / 0")
        self.score_lbl.setProperty("role", "stat")
        self.score_lbl.setFont(QFont("Trebuchet MS", 11, QFont.Bold))
        h.addWidget(self.score_lbl)
        self.hi_lbl = QLabel()
        self.hi_lbl.setProperty("role", "stat")
        self.hi_lbl.setFont(QFont("Trebuchet MS", 11, QFont.Bold))
        h.addWidget(self.hi_lbl)
        self.lives_lbl = QLabel()
        self.lives_lbl.setProperty("role", "stat")
        self.lives_lbl.setFont(QFont("Trebuchet MS", 11, QFont.Bold))
        h.addWidget(self.lives_lbl)
        h.addStretch()
        stats_layout.addLayout(h)

        h2 = QHBoxLayout()
        h2.setSpacing(12)
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("startButton")
        self.start_btn.clicked.connect(self._start)
        self.skip_btn = QPushButton("Skip")
        self.skip_btn.setObjectName("skipButton")
        self.skip_btn.clicked.connect(self._skip)
        self.skip_btn.setEnabled(False)
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("resetButton")
        self.reset_btn.clicked.connect(self._reset)
        self.reset_btn.setEnabled(False)
        self.challenge_cb = QCheckBox("Princess Challenge Mode (hide the hint)")
        self.challenge_cb.setObjectName("challengeToggle")
        self.challenge_cb.toggled.connect(self._toggle_challenge)
        h2.addWidget(self.start_btn)
        h2.addWidget(self.skip_btn)
        h2.addWidget(self.reset_btn)
        h2.addSpacing(12)
        h2.addWidget(self.challenge_cb)
        h2.addStretch()
        stats_layout.addLayout(h2)
        v.addWidget(stats_card)

        self.input_lbl = QLabel("", alignment=Qt.AlignCenter)
        self.input_lbl.setProperty("role", "status")
        self.input_lbl.setFont(QFont("Trebuchet MS", 10, QFont.Bold))
        self.input_lbl.setWordWrap(True)
        v.addWidget(self.input_lbl)

        v.addWidget(self._line())

        letter_card = QFrame()
        letter_card.setObjectName("sectionCard")
        letter_layout = QVBoxLayout(letter_card)
        letter_layout.setContentsMargins(26, 20, 26, 20)
        letter_layout.setSpacing(10)

        letter_heading = QLabel("♡ Your Letter ♡", alignment=Qt.AlignCenter)
        letter_heading.setProperty("role", "caption")
        letter_heading.setFont(QFont("Comic Sans MS", 11, QFont.Bold))
        letter_layout.addWidget(letter_heading)

        self.target = QLabel("—", alignment=Qt.AlignCenter)
        self.target.setProperty("role", "target")
        self.target.setFont(QFont("Comic Sans MS", 42, QFont.Bold))
        self.hint = QLabel("", alignment=Qt.AlignCenter)
        self.hint.setProperty("role", "hint")
        self.hint.setFont(QFont("Courier", 16, QFont.Bold))
        letter_layout.addWidget(self.target)
        letter_layout.addWidget(self.hint)
        v.addWidget(letter_card)

        v.addWidget(self._line())

        input_card = QFrame()
        input_card.setObjectName("sectionCard")
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(26, 20, 26, 20)
        input_layout.setSpacing(10)

        input_heading = QLabel("♡ Your Input ♡", alignment=Qt.AlignCenter)
        input_heading.setProperty("role", "caption")
        input_heading.setFont(QFont("Comic Sans MS", 11, QFont.Bold))
        input_layout.addWidget(input_heading)

        self.inp_lbl = QLabel("", alignment=Qt.AlignCenter)
        self.inp_lbl.setProperty("role", "display")
        self.inp_lbl.setFont(QFont("Courier", 22, QFont.Bold))
        self.inp_lbl.setWordWrap(True)
        self.result_lbl = QLabel("", alignment=Qt.AlignCenter)
        self.result_lbl.setProperty("role", "result")
        self.result_lbl.setProperty("state", "neutral")
        self.result_lbl.setFont(QFont("Trebuchet MS", 11, QFont.Bold))
        self.result_lbl.setMinimumHeight(56)
        self.result_lbl.setWordWrap(True)
        input_layout.addWidget(self.inp_lbl)
        input_layout.addWidget(self.result_lbl)
        v.addWidget(input_card)

        self.footer_lbl = QLabel("Short squeeze = dot. Long squeeze = dash. Keep it glossy.", alignment=Qt.AlignCenter)
        self.footer_lbl.setObjectName("footerLabel")
        self.footer_lbl.setFont(QFont("Trebuchet MS", 10))
        v.addWidget(self.footer_lbl)

        for widget in (hero, stats_card, letter_card, input_card):
            self._add_shadow(widget)

    def _line(self):
        f = QFrame()
        f.setObjectName("divider")
        f.setFrameShape(QFrame.HLine)
        f.setFrameShadow(QFrame.Plain)
        return f

    def _apply_theme(self):
        self.setStyleSheet("""
            QWidget#root {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #ffe8f3,
                    stop: 0.45 #ffd3e6,
                    stop: 1 #ffc2df
                );
                color: #7b2951;
            }
            QFrame#heroCard, QFrame#scoreCard, QFrame#sectionCard {
                background: rgba(255, 251, 254, 230);
                border: 2px solid #f6b8d1;
                border-radius: 24px;
            }
            QLabel#bannerLabel {
                background: rgba(255, 250, 253, 220);
                border: 1px solid #f3bdd6;
                border-radius: 18px;
                color: #f05c9c;
                padding: 8px 18px;
            }
            QLabel#titleLabel {
                color: #c63d7e;
            }
            QLabel#subtitleLabel {
                color: #8b4a6a;
            }
            QLabel#decorationLabel, QLabel#footerLabel {
                color: #d15691;
            }
            QLabel[role="stat"] {
                background: #fff2f8;
                border: 1px solid #f6c1d8;
                border-radius: 18px;
                color: #a33f6e;
                padding: 9px 14px;
            }
            QLabel[role="status"] {
                background: rgba(255, 248, 252, 220);
                border: 1px solid #f6bdd3;
                border-radius: 18px;
                color: #8e4665;
                padding: 10px 16px;
            }
            QLabel[role="caption"] {
                color: #c85c8e;
                letter-spacing: 1px;
            }
            QLabel[role="target"] {
                color: #a11f62;
                background: #fff6fb;
                border: 2px solid #ffc7dd;
                border-radius: 24px;
                padding: 18px;
            }
            QLabel[role="hint"] {
                color: #d45a95;
            }
            QLabel[role="display"] {
                background: #fff7fb;
                border: 2px solid #ffd4e6;
                border-radius: 22px;
                color: #8a2657;
                padding: 16px;
            }
            QLabel[role="result"] {
                border-radius: 18px;
                padding: 12px 16px;
            }
            QLabel[role="result"][state="neutral"] {
                background: #fff0f7;
                border: 1px solid #f5bfd5;
                color: #9d496e;
            }
            QLabel[role="result"][state="success"] {
                background: #ffe2ef;
                border: 1px solid #f08db6;
                color: #b12f6f;
            }
            QLabel[role="result"][state="error"] {
                background: #ffe7f0;
                border: 1px solid #eb7da6;
                color: #a42a59;
            }
            QPushButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #ff91bc,
                    stop: 1 #ff6da7
                );
                border: 2px solid #fff7fb;
                border-radius: 18px;
                color: white;
                font: bold 11pt "Trebuchet MS";
                padding: 10px 18px;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #ff7bb0,
                    stop: 1 #ff5d9f
                );
            }
            QPushButton:pressed {
                padding-top: 12px;
            }
            QPushButton:disabled {
                background: #ebb9cd;
                border-color: #f7dde9;
                color: #fff8fb;
            }
            QCheckBox {
                color: #964b71;
                font: bold 10pt "Trebuchet MS";
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 22px;
                height: 22px;
                border-radius: 11px;
                border: 2px solid #e68cb2;
                background: #fff8fc;
            }
            QCheckBox::indicator:checked {
                background: #ff80b5;
                border: 2px solid #ff5f9f;
            }
            QFrame#divider {
                background: rgba(241, 123, 175, 0.35);
                border: none;
                min-height: 2px;
                max-height: 2px;
                margin: 2px 20px;
            }
        """)

    def _add_shadow(self, widget, color=QColor(226, 107, 160, 80)):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(color)
        widget.setGraphicsEffect(shadow)

    def _tick_banner(self):
        self.banner_lbl.setText(self._banner_frames[self._banner_index])
        self._banner_index = (self._banner_index + 1) % len(self._banner_frames)

    def _update_mode_copy(self):
        if self.running and self.challenge:
            self.subtitle_lbl.setText("Challenge mode is on: no hint, just heart, hustle, and Morse.")
        elif self.running:
            self.subtitle_lbl.setText("Read the letter, squeeze the signal, and stay cute under pressure.")
        elif self.challenge:
            self.subtitle_lbl.setText("Challenge mode armed. Hide the hint and trust the vibes.")
        else:
            self.subtitle_lbl.setText("A sugary little Morse game for your EMG setup.")

    def _update_input_preview(self):
        if not self.inp:
            self.inp_lbl.setText("♡ waiting for your first pretty little signal ♡")
            return
        words = "  ".join("dot" if ch == "." else "dash" for ch in self.inp)
        self.inp_lbl.setText(f"{self.inp}\n{words}")

    def _set_result_message(self, text, state="neutral"):
        self.result_lbl.setProperty("state", state)
        self.result_lbl.style().unpolish(self.result_lbl)
        self.result_lbl.style().polish(self.result_lbl)
        self.result_lbl.update()
        self.result_lbl.setText(text)

    def _start(self):
        self.score = self.total = 0; self.lives = LIVES; self.running = True
        self._reset_input_gate()
        self._refresh_lives(); self._servo_to_lives()
        self.start_btn.setEnabled(False); self.skip_btn.setEnabled(True); self.reset_btn.setEnabled(True)
        self._update_mode_copy()
        self._next()

    def _next(self):
        self._pause.stop(); self._result.stop()
        self.inp = ""; self.letter = random.choice(list(MORSE))
        self.target.setText(self.letter)
        self.hint.setText("? ? ?" if self.challenge else MORSE[self.letter])
        self._update_input_preview()
        self._set_result_message("Make it cute: short squeeze for dot, long squeeze for dash.", "neutral")
        self.skip_btn.setEnabled(True); self._score()
        self._update_mode_copy()

    def _toggle_challenge(self, on):
        if self.running:
            self.challenge_cb.blockSignals(True)
            self.challenge_cb.setChecked(self.challenge)
            self.challenge_cb.blockSignals(False)
            return
        self.challenge = on
        self._refresh_hi()
        self._update_mode_copy()

    def _skip(self):
        self._pause.stop(); self._result.stop()
        self.total += 1; self._score()
        self._set_result_message(f"Skip, no shame. '{self.letter}' was '{MORSE[self.letter]}'.", "neutral")
        self.skip_btn.setEnabled(False); self._result.start(1200)

    def _reset(self):
        self._pause.stop(); self._result.stop(); self.running = False
        self.score = self.total = 0; self.lives = LIVES; self.inp = self.letter = ""
        self._reset_input_gate()
        self.target.setText("—"); self.hint.setText("")
        self._update_input_preview()
        self.score_lbl.setText("Current Score: 0 / 0")
        self._refresh_lives(); self._servo_to_lives()
        self.start_btn.setText("Start"); self.start_btn.setEnabled(True); self.start_btn.show()
        self.skip_btn.setEnabled(False); self.reset_btn.setEnabled(False)
        self._update_mode_copy()
        self._set_result_message("Reset complete. Fix your bow and tap Start.", "neutral")

    def _press(self):
        if not self.running or self._input_pressed or self._result.isActive(): return
        self._input_pressed = True
        self._pause.stop(); self._ptimer.start()
        self._set_result_message("Holding... tiny press for dot, longer press for dash.", "neutral")

    def _release(self):
        if not self.running or not self._input_pressed: return
        self._input_pressed = False
        self._append_symbol(self._ptimer.elapsed())
        self._ptimer.invalidate()

    def _append_symbol(self, press_ms):
        self._ptimer.invalidate()
        if press_ms < MIN_PRESS_MS:
            return
        self.inp += "." if press_ms < DOT_THRESHOLD else "-"
        self._update_input_preview()
        if self.running and self.letter and self.inp == MORSE[self.letter]:
            self._pause.stop()
            self._submit()
            return
        self._pause.start(LETTER_PAUSE)

    def _submit(self):
        self.total += 1
        correct = MORSE[self.letter]
        if self.inp == correct:
            self._set_result_message(random.choice(CORRECT_MESSAGES).format(letter=self.letter, morse=correct), "success")
            self.score += 1; self._score()
            self.skip_btn.setEnabled(False)
            self._result.start(CORRECT_PAUSE)
        else:
            decoded = {v:k for k,v in MORSE.items()}.get(self.inp, "?")
            self._set_result_message(
                f"Oopsie. You sent '{self.inp}' ({decoded}), but the answer was '{correct}'.",
                "error",
            )
            self.lives -= 1; self._refresh_lives(); self._servo_to_lives()
            self._score(); self.skip_btn.setEnabled(False)
            if self.lives <= 0:
                self._game_over()
            else:
                self._result.start(1800)

    def _score(self):
        pct = int(self.score/self.total*100) if self.total else 0
        self.score_lbl.setText(f"Current Score: {self.score} / {self.total}  ({pct}%)")
        hs, hp = (self.challenge_hiscore, self.challenge_hipct) if self.challenge else (self.hiscore, self.hipct)
        if self.score > hs or (self.score == hs and pct > hp):
            if self.challenge:
                self.challenge_hiscore, self.challenge_hipct = self.score, pct
            else:
                self.hiscore, self.hipct = self.score, pct
            self._save_hiscore(self.challenge)
        self._refresh_hi()

    def _refresh_hi(self):
        hs, hp = (self.challenge_hiscore, self.challenge_hipct) if self.challenge else (self.hiscore, self.hipct)
        label = "Challenge Crown" if self.challenge else "High Score"
        self.hi_lbl.setText(f"{label}: {hs} ({hp}%)" if hs else f"{label}: —")

    def _load_hiscore(self, challenge=False):
        key = "challenge" if challenge else "normal"
        try:
            with open(HISCORE_PATH) as f:
                d = json.load(f)
                sub = d.get(key, {})
                if not sub and not challenge and "score" in d:
                    sub = d
                return int(sub.get("score", 0)), int(sub.get("pct", 0))
        except Exception:
            return 0, 0

    def _save_hiscore(self, challenge=False):
        try:
            data = {}
            try:
                with open(HISCORE_PATH) as f:
                    data = json.load(f)
                    if "score" in data and "normal" not in data:
                        data = {"normal": {"score": data.get("score", 0), "pct": data.get("pct", 0)}}
            except Exception:
                data = {}
            data["challenge" if challenge else "normal"] = {
                "score": self.challenge_hiscore if challenge else self.hiscore,
                "pct":   self.challenge_hipct   if challenge else self.hipct,
            }
            with open(HISCORE_PATH, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _refresh_lives(self):
        hearts = " ".join(["♥"] * self.lives + ["♡"] * (LIVES - self.lives))
        self.lives_lbl.setText(f"Lives: {hearts}")

    def _servo_to_lives(self):
        if not SERVO_OK: return
        try:
            _servo.value = -1 + 2 * (self.lives / LIVES)
        except Exception:
            pass

    def _game_over(self):
        self._pause.stop(); self._result.stop(); self.running = False
        self._set_result_message(f"Game over, cupcake. Final score: {self.score}/{self.total}.", "error")
        self.target.setText("try again")
        self.hint.setText("♡")
        self.skip_btn.setEnabled(False)
        self.start_btn.setText("Start"); self.start_btn.setEnabled(True)
        self._update_mode_copy()

    def _toggle_display(self):
        self.disp_on = not self.disp_on
        val = "0" if self.disp_on else "1"
        for path in glob.glob("/sys/class/backlight/*/bl_power"):
            try:
                open(path,"w").write(val)
            except PermissionError:
                subprocess.call(["sudo","sh","-c",f"echo {val} > {path}"])

    def _set_ble_status(self, text):
        self.ble_status = text
        input_state = "squeezing" if self._emg_active else "waiting"
        suffix = f" | input: {input_state}" if self.ble_enabled else ""
        self.input_lbl.setText(f"♡ {self.ble_status}{suffix} ♡")

    def _reset_input_gate(self):
        self._emg_active = False
        self._input_pressed = False
        self._ptimer.invalidate()
        self._segment_active = False
        self._segment_total_samples = 0
        self._segment_above_samples = 0
        self._segment_below_gap_samples = 0
        self._emg_window.clear()
        self._emg_window_sum = 0.0
        self._emg_mavg = None
        self._emg_baseline = None
        self._emg_threshold = None
        self._set_ble_status(self.ble_status)

    def _set_effective_input_state(self, active):
        if active == self._emg_active:
            return

        self._emg_active = active
        self._set_ble_status(self.ble_status)
        if active:
            _sig.pressed.emit()
        else:
            _sig.released.emit()

    def _start_ble(self):
        if self._ble_task is None:
            self._ble_task = asyncio.create_task(self._ble_loop())

    async def _ble_loop(self):
        while not self._closing:
            try:
                self._set_ble_status("BLE: scanning")
                device = await self._find_ble_device()
                if device is None:
                    raise RuntimeError("EMG peripheral not found")

                self._set_ble_status("BLE: connecting")
                self._client = BleakClient(device)
                await self._client.connect()
                await self._client.start_notify(BLE_SENSOR_CHAR_UUID, self._handle_emg_data)
                await self._client.start_notify(BLE_CONTROL_CHAR_UUID, self._handle_control_state)
                name = getattr(device, "name", None) or BLE_DEVICE_NAME or "EMG device"
                self._set_ble_status(f"BLE: connected to {name}")

                while self._client.is_connected and not self._closing:
                    await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._set_ble_status(f"BLE: {exc}")
            finally:
                await self._disconnect_ble()

            if not self._closing:
                self._set_ble_status(f"BLE: retrying in {BLE_RETRY_SECONDS:.0f}s")
                await asyncio.sleep(BLE_RETRY_SECONDS)

    async def _find_ble_device(self):
        if BLE_ADDRESS:
            return await BleakScanner.find_device_by_address(BLE_ADDRESS, timeout=5.0)

        devices = await BleakScanner.discover(timeout=5.0)
        for device in devices:
            if device.name == BLE_DEVICE_NAME:
                return device
        return None

    def _handle_control_state(self, characteristic: BleakGATTCharacteristic, data: bytearray):
        if not data:
            return

        active = bool(data[0])
        if active != self._ble_control_active:
            self._ble_control_active = active
            if EMG_CONTROL_SOURCE == "ble":
                self._set_effective_input_state(active)
        return

    def _process_emg_sample(self, sample):
        if len(self._emg_window) == self._emg_window.maxlen:
            self._emg_window_sum -= self._emg_window[0]
        self._emg_window.append(sample)
        self._emg_window_sum += sample
        self._emg_mavg = self._emg_window_sum / len(self._emg_window)

        if self._emg_baseline is None:
            self._emg_baseline = self._emg_mavg
        elif not self._segment_active:
            self._emg_baseline = (
                (1.0 - EMG_BASELINE_ALPHA) * self._emg_baseline
                + EMG_BASELINE_ALPHA * self._emg_mavg
            )

        if EMG_FIXED_THRESHOLD is not None:
            self._emg_threshold = float(EMG_FIXED_THRESHOLD)
        else:
            self._emg_threshold = self._emg_baseline + EMG_THRESHOLD_MARGIN

        above_threshold = self._emg_mavg >= self._emg_threshold

        if not self._segment_active:
            if above_threshold:
                self._segment_active = True
                self._segment_total_samples = 1
                self._segment_above_samples = 1
                self._segment_below_gap_samples = 0
                self._emg_active = True
                self._set_ble_status(self.ble_status)
            return

        self._segment_total_samples += 1
        if above_threshold:
            self._segment_above_samples += 1
            self._segment_below_gap_samples = 0
        else:
            self._segment_below_gap_samples += 1

        if self._segment_below_gap_samples < EMG_GAP_SAMPLES:
            return

        effective_samples = self._segment_total_samples - self._segment_below_gap_samples
        duration_ms = int(effective_samples * 1000 / EMG_SAMPLE_RATE)
        ratio = round(self._segment_above_samples / effective_samples, 2) if effective_samples > 0 else 0.0

        if effective_samples > 0 and ratio >= EMG_ACTIVE_RATIO:
            self._append_symbol(duration_ms)

        self._segment_active = False
        self._segment_total_samples = 0
        self._segment_above_samples = 0
        self._segment_below_gap_samples = 0
        self._emg_active = False
        self._set_ble_status(self.ble_status)

    def _handle_emg_data(self, characteristic: BleakGATTCharacteristic, data: bytearray):
        if not data:
            return

        vals = list(data)
        if EMG_CONTROL_SOURCE == "raw":
            for sample in vals:
                self._process_emg_sample(sample)
            self._set_ble_status(self.ble_status)
            return

    async def _disconnect_ble(self):
        client, self._client = self._client, None
        if self._emg_active:
            self._emg_active = False
            _sig.released.emit()
            self._set_ble_status(self.ble_status)
        if client is None:
            return
        try:
            if client.is_connected:
                try:
                    await client.stop_notify(BLE_SENSOR_CHAR_UUID)
                except Exception:
                    pass
                try:
                    await client.stop_notify(BLE_CONTROL_CHAR_UUID)
                except Exception:
                    pass
                await client.disconnect()
        except Exception:
            pass

    async def shutdown(self):
        self._closing = True
        if self._ble_task is not None:
            self._ble_task.cancel()
            try:
                await self._ble_task
            except asyncio.CancelledError:
                pass
            self._ble_task = None
        await self._disconnect_ble()

    def closeEvent(self, e):
        self._closing = True
        if self._ble_task is not None:
            asyncio.create_task(self.shutdown())
        if GPIO_OK: _btn.close(); _disp.close()
        if SERVO_OK:
            try: _servo.detach(); _servo.close()
            except Exception: pass
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    w = MorseGame()
    app.aboutToQuit.connect(lambda: asyncio.create_task(w.shutdown()))
    w.show()
    with loop:
        loop.run_forever()
