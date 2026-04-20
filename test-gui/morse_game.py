import sys, random, glob, subprocess
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt5.QtCore import Qt, QTimer, QElapsedTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont

GPIO_PIN        = 22
DISPLAY_BTN_PIN = 6
DOT_THRESHOLD   = 300   # ms — shorter press = dot, longer = dash
LETTER_PAUSE    = 800   # ms silence → auto-submit

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

class _Sig(QObject):
    pressed  = pyqtSignal()
    released = pyqtSignal()

_sig = _Sig()


class MorseGame(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EMG Morse Code Game")
        self.resize(500, 380)
        self.letter = ""
        self.inp    = ""
        self.score  = self.total = 0
        self.running = False
        self.disp_on = True

        self._ptimer = QElapsedTimer()
        self._pause  = QTimer(singleShot=True, timeout=self._submit)
        self._result = QTimer(singleShot=True, timeout=self._next)

        self._build()
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
        self.score_lbl = QLabel("Score: 0 / 0"); h.addWidget(self.score_lbl)
        h.addStretch()
        self.skip_btn  = QPushButton("Skip");  self.skip_btn.clicked.connect(self._skip);  self.skip_btn.setEnabled(False)
        self.reset_btn = QPushButton("Reset"); self.reset_btn.clicked.connect(self._reset); self.reset_btn.setEnabled(False)
        h.addWidget(self.skip_btn); h.addWidget(self.reset_btn)
        v.addLayout(h)

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

        v.addWidget(self._line())

        self.start_btn = QPushButton("Start"); self.start_btn.clicked.connect(self._start)
        v.addWidget(self.start_btn)

    def _line(self):
        f = QFrame(); f.setFrameShape(QFrame.HLine); f.setFrameShadow(QFrame.Sunken); return f

    def _start(self):
        self.score = self.total = 0; self.running = True
        self.start_btn.setEnabled(False); self.skip_btn.setEnabled(True); self.reset_btn.setEnabled(True)
        self._next()

    def _next(self):
        self._pause.stop(); self._result.stop()
        self.inp = ""; self.letter = random.choice(list(MORSE))
        self.target.setText(self.letter); self.hint.setText(MORSE[self.letter])
        self.inp_lbl.setText(""); self.result_lbl.setText("")
        self.skip_btn.setEnabled(True); self._score()

    def _skip(self):
        self._pause.stop(); self._result.stop()
        self.total += 1; self._score()
        self.result_lbl.setText(f"Skipped — '{self.letter}' was '{MORSE[self.letter]}'")
        self.skip_btn.setEnabled(False); self._result.start(1200)

    def _reset(self):
        self._pause.stop(); self._result.stop(); self.running = False
        self.score = self.total = 0; self.inp = self.letter = ""
        self.target.setText("—"); self.hint.setText("")
        self.inp_lbl.setText(""); self.result_lbl.setText("")
        self.score_lbl.setText("Score: 0 / 0")
        self.start_btn.setText("Start"); self.start_btn.setEnabled(True)
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
            self._score(); self.skip_btn.setEnabled(False); self._result.start(1800)

    def _score(self):
        pct = int(self.score/self.total*100) if self.total else 0
        self.score_lbl.setText(f"Score: {self.score} / {self.total}  ({pct}%)")

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
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MorseGame(); w.show()
    sys.exit(app.exec())
