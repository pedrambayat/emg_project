import sys, random, glob, subprocess, json, os
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QCheckBox
from PyQt5.QtCore import Qt, QTimer, QElapsedTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont

GPIO_PIN        = 22
DISPLAY_BTN_PIN = 6
SERVO_PIN       = 17
DOT_THRESHOLD   = 300   # ms — shorter press = dot, longer = dash
LETTER_PAUSE    = 800   # ms silence → auto-submit
LIVES           = 5     # wrong answers allowed before game over
HISCORE_PATH    = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".morse_highscore.json")

MORSE = {
    'A':'.-','B':'-...','C':'-.-.','D':'-..','E':'.','F':'..-.','G':'--.','H':'....','I':'..','J':'.---',
    'K':'-.-','L':'.-..','M':'--','N':'-.','O':'---','P':'.--.','Q':'--.-','R':'.-.','S':'...','T':'-',
    'U':'..-','V':'...-','W':'.--','X':'-..-','Y':'-.--','Z':'--..',
}

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
        self.setWindowTitle("EMG Morse Code Game")
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

        self._ptimer = QElapsedTimer()
        self._pause  = QTimer(singleShot=True, timeout=self._submit)
        self._result = QTimer(singleShot=True, timeout=self._next)

        self._build()
        self._refresh_hi()
        self._refresh_lives()
        self._servo_to_lives()
        _sig.pressed.connect(self._press)
        _sig.released.connect(self._release)
        if GPIO_OK:
            _btn.when_pressed  = _sig.pressed.emit
            _btn.when_released = _sig.released.emit
            _disp.when_pressed = self._toggle_display

    def _build(self):
        root = QWidget(); self.setCentralWidget(root)
        v = QVBoxLayout(root); v.setContentsMargins(20,20,20,20); v.setSpacing(10)

        title = QLabel("Morse Code Game", alignment=Qt.AlignCenter)
        title.setFont(QFont("Helvetica", 18, QFont.Bold))
        v.addWidget(title)

        h = QHBoxLayout()
        self.score_lbl = QLabel("Current Score: 0 / 0")
        self.score_lbl.setFont(QFont("Helvetica", 11, QFont.Bold))
        h.addWidget(self.score_lbl)
        h.addSpacing(20)
        self.hi_lbl = QLabel()
        self.hi_lbl.setFont(QFont("Helvetica", 11, QFont.Bold))
        h.addWidget(self.hi_lbl)
        h.addSpacing(20)
        self.lives_lbl = QLabel()
        self.lives_lbl.setFont(QFont("Helvetica", 11, QFont.Bold))
        h.addWidget(self.lives_lbl)
        h.addStretch()
        self.start_btn = QPushButton("Start"); self.start_btn.clicked.connect(self._start)
        self.skip_btn  = QPushButton("Skip");  self.skip_btn.clicked.connect(self._skip);  self.skip_btn.setEnabled(False)
        self.reset_btn = QPushButton("Reset"); self.reset_btn.clicked.connect(self._reset); self.reset_btn.setEnabled(False)
        h.addWidget(self.start_btn); h.addWidget(self.skip_btn); h.addWidget(self.reset_btn)
        v.addLayout(h)

        h2 = QHBoxLayout()
        self.challenge_cb = QCheckBox("Challenge Mode (hide morse hint)")
        self.challenge_cb.toggled.connect(self._toggle_challenge)
        h2.addWidget(self.challenge_cb); h2.addStretch()
        v.addLayout(h2)

        v.addWidget(self._line())

        v.addWidget(QLabel("Your Letter", alignment=Qt.AlignCenter))
        self.target = QLabel("—", alignment=Qt.AlignCenter)
        self.target.setFont(QFont("Courier", 72, QFont.Bold))
        self.hint = QLabel("", alignment=Qt.AlignCenter)
        self.hint.setFont(QFont("Courier", 22))
        v.addWidget(self.target); v.addWidget(self.hint)

        v.addWidget(self._line())

        v.addWidget(QLabel("Your Input", alignment=Qt.AlignCenter))
        self.inp_lbl = QLabel("", alignment=Qt.AlignCenter)
        self.inp_lbl.setFont(QFont("Courier", 28))
        self.result_lbl = QLabel("", alignment=Qt.AlignCenter)
        self.result_lbl.setMinimumHeight(24)
        v.addWidget(self.inp_lbl); v.addWidget(self.result_lbl)


    def _line(self):
        f = QFrame(); f.setFrameShape(QFrame.HLine); f.setFrameShadow(QFrame.Sunken); return f

    def _start(self):
        self.score = self.total = 0; self.lives = LIVES; self.running = True
        self._refresh_lives(); self._servo_to_lives()
        self.start_btn.setEnabled(False); self.skip_btn.setEnabled(True); self.reset_btn.setEnabled(True)
        self._next()

    def _next(self):
        self._pause.stop(); self._result.stop()
        self.inp = ""; self.letter = random.choice(list(MORSE))
        self.target.setText(self.letter)
        self.hint.setText("? ? ?" if self.challenge else MORSE[self.letter])
        self.inp_lbl.setText(""); self.result_lbl.setText("")
        self.skip_btn.setEnabled(True); self._score()

    def _toggle_challenge(self, on):
        if self.running:
            self.challenge_cb.blockSignals(True)
            self.challenge_cb.setChecked(self.challenge)
            self.challenge_cb.blockSignals(False)
            return
        self.challenge = on
        self._refresh_hi()

    def _skip(self):
        self._pause.stop(); self._result.stop()
        self.total += 1; self._score()
        self.result_lbl.setText(f"Skipped — '{self.letter}' was '{MORSE[self.letter]}'")
        self.skip_btn.setEnabled(False); self._result.start(1200)

    def _reset(self):
        self._pause.stop(); self._result.stop(); self.running = False
        self.score = self.total = 0; self.lives = LIVES; self.inp = self.letter = ""
        self.target.setText("—"); self.hint.setText("")
        self.inp_lbl.setText(""); self.result_lbl.setText("")
        self.score_lbl.setText("Current Score: 0 / 0")
        self._refresh_lives(); self._servo_to_lives()
        self.start_btn.setText("Start"); self.start_btn.setEnabled(True); self.start_btn.show()
        self.skip_btn.setEnabled(False); self.reset_btn.setEnabled(False)

    def _press(self):
        if not self.running: return
        self._pause.stop(); self._ptimer.start()

    def _release(self):
        if not self.running: return
        self.inp += "." if self._ptimer.elapsed() < DOT_THRESHOLD else "-"
        self.inp_lbl.setText(self.inp)
        self._pause.start(LETTER_PAUSE)

    def _submit(self):
        self.total += 1
        correct = MORSE[self.letter]
        if self.inp == correct:
            self.score += 1; self._score(); self._next()
        else:
            decoded = {v:k for k,v in MORSE.items()}.get(self.inp, "?")
            self.result_lbl.setText(f"Wrong — got '{self.inp}' ({decoded}), expected '{correct}'")
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
        label = "Challenge High" if self.challenge else "High Score"
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
        hearts = "♥" * self.lives + "♡" * (LIVES - self.lives)
        self.lives_lbl.setText(f"Lives: {hearts}")

    def _servo_to_lives(self):
        if not SERVO_OK: return
        try:
            _servo.value = -1 + 2 * (self.lives / LIVES)
        except Exception:
            pass

    def _game_over(self):
        self._pause.stop(); self._result.stop(); self.running = False
        self.result_lbl.setText(f"💀 GAME OVER — final score {self.score}/{self.total}")
        self.target.setText("✗"); self.hint.setText("")
        self.skip_btn.setEnabled(False)
        self.start_btn.setText("Start"); self.start_btn.setEnabled(True)

    def _toggle_display(self):
        self.disp_on = not self.disp_on
        val = "0" if self.disp_on else "1"
        for path in glob.glob("/sys/class/backlight/*/bl_power"):
            try:
                open(path,"w").write(val)
            except PermissionError:
                subprocess.call(["sudo","sh","-c",f"echo {val} > {path}"])

    def closeEvent(self, e):
        if GPIO_OK: _btn.close(); _disp.close()
        if SERVO_OK:
            try: _servo.detach(); _servo.close()
            except Exception: pass
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MorseGame(); w.show()
    sys.exit(app.exec())
