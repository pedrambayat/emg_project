import sys, random, glob, subprocess, json, os
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, QTimer, QElapsedTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont

GPIO_PIN        = 22
DISPLAY_BTN_PIN = 6
DOT_THRESHOLD   = 300   # ms — shorter press = dot, longer = dash
LETTER_PAUSE    = 800   # ms silence → auto-submit
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

class _Sig(QObject):
    pressed  = pyqtSignal()
    released = pyqtSignal()

_sig = _Sig()


STYLESHEET = """
QMainWindow, QWidget#root {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #ffe4f1, stop:0.5 #f3e8ff, stop:1 #e0f2fe);
}
QLabel { color: #5b3a6b; }
QLabel#title {
    color: #d14b8f;
    padding: 6px 14px;
}
QLabel#scoreChip {
    background: #fff0f7;
    color: #c2185b;
    border: 2px solid #f8bbd0;
    border-radius: 14px;
    padding: 6px 14px;
}
QLabel#hiChip {
    background: #fff8e1;
    color: #a0761b;
    border: 2px solid #ffe082;
    border-radius: 14px;
    padding: 6px 14px;
}
QLabel#card {
    background: #ffffffcc;
    border: 2px dashed #f8bbd0;
    border-radius: 20px;
    padding: 14px;
}
QLabel#target { color: #7b2cbf; }
QLabel#hint   { color: #9d4edd; letter-spacing: 4px; }
QLabel#inp    { color: #0891b2; letter-spacing: 4px; }
QLabel#result { color: #6b4a7a; font-style: italic; }
QLabel#section {
    color: #b5179e;
    font-weight: bold;
    letter-spacing: 2px;
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffb3d9, stop:1 #ff80bf);
    color: white;
    border: none;
    border-radius: 14px;
    padding: 8px 18px;
    font-weight: bold;
}
QPushButton:hover { background: #ff6fae; }
QPushButton:pressed { background: #e0559a; }
QPushButton:disabled {
    background: #e8d5e8;
    color: #b8a5b8;
}
QPushButton#start {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #a0e7a0, stop:1 #5ec85e);
}
QPushButton#start:hover { background: #4db84d; }
QPushButton#reset {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffc4a0, stop:1 #ff9466);
}
QPushButton#reset:hover { background: #ff7a3d; }
"""

class MorseGame(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("✨ Morse Code Game ✨")
        self.resize(560, 620)
        self.setStyleSheet(STYLESHEET)
        self.letter = ""
        self.inp    = ""
        self.score  = self.total = 0
        self.hiscore, self.hipct = self._load_hiscore()
        self.running = False
        self.disp_on = True

        self._ptimer = QElapsedTimer()
        self._pause  = QTimer(singleShot=True, timeout=self._submit)
        self._result = QTimer(singleShot=True, timeout=self._next)

        self._build()
        self._refresh_hi()
        _sig.pressed.connect(self._press)
        _sig.released.connect(self._release)
        if GPIO_OK:
            _btn.when_pressed  = _sig.pressed.emit
            _btn.when_released = _sig.released.emit
            _disp.when_pressed = self._toggle_display

    def _section(self, text):
        lbl = QLabel(text, alignment=Qt.AlignCenter)
        lbl.setObjectName("section")
        lbl.setFont(QFont("Helvetica", 10, QFont.Bold))
        return lbl

    def _build(self):
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        v = QVBoxLayout(root); v.setContentsMargins(24,20,24,20); v.setSpacing(12)

        title = QLabel("✨ Morse Code Game ✨", alignment=Qt.AlignCenter)
        title.setObjectName("title")
        title.setFont(QFont("Helvetica", 22, QFont.Bold))
        v.addWidget(title)

        h = QHBoxLayout(); h.setSpacing(10)
        self.score_lbl = QLabel("🎯 Current Score: 0 / 0")
        self.score_lbl.setObjectName("scoreChip")
        self.score_lbl.setFont(QFont("Helvetica", 11, QFont.Bold))
        h.addWidget(self.score_lbl)
        self.hi_lbl = QLabel()
        self.hi_lbl.setObjectName("hiChip")
        self.hi_lbl.setFont(QFont("Helvetica", 11, QFont.Bold))
        h.addWidget(self.hi_lbl)
        h.addStretch()
        self.start_btn = QPushButton("▶  Start"); self.start_btn.setObjectName("start"); self.start_btn.clicked.connect(self._start)
        self.skip_btn  = QPushButton("⏭  Skip");  self.skip_btn.clicked.connect(self._skip);  self.skip_btn.setEnabled(False)
        self.reset_btn = QPushButton("↺  Reset"); self.reset_btn.setObjectName("reset"); self.reset_btn.clicked.connect(self._reset); self.reset_btn.setEnabled(False)
        h.addWidget(self.start_btn); h.addWidget(self.skip_btn); h.addWidget(self.reset_btn)
        v.addLayout(h)

        v.addWidget(self._section("★  YOUR LETTER  ★"))
        self.target = QLabel("—", alignment=Qt.AlignCenter)
        self.target.setObjectName("card")
        self.target.setFont(QFont("Courier", 80, QFont.Bold))
        self.hint = QLabel("", alignment=Qt.AlignCenter)
        self.hint.setObjectName("hint")
        self.hint.setFont(QFont("Courier", 24, QFont.Bold))
        v.addWidget(self.target); v.addWidget(self.hint)

        v.addWidget(self._section("♡  YOUR INPUT  ♡"))
        self.inp_lbl = QLabel("", alignment=Qt.AlignCenter)
        self.inp_lbl.setObjectName("inp")
        self.inp_lbl.setFont(QFont("Courier", 30, QFont.Bold))
        self.inp_lbl.setMinimumHeight(48)
        self.result_lbl = QLabel("", alignment=Qt.AlignCenter)
        self.result_lbl.setObjectName("result")
        self.result_lbl.setFont(QFont("Helvetica", 11))
        self.result_lbl.setMinimumHeight(28)
        v.addWidget(self.inp_lbl); v.addWidget(self.result_lbl)
        v.addStretch()


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
        self.result_lbl.setText(f"⏭ skipped — '{self.letter}' was '{MORSE[self.letter]}'")
        self.skip_btn.setEnabled(False); self._result.start(1200)

    def _reset(self):
        self._pause.stop(); self._result.stop(); self.running = False
        self.score = self.total = 0; self.inp = self.letter = ""
        self.target.setText("—"); self.hint.setText("")
        self.inp_lbl.setText(""); self.result_lbl.setText("")
        self.score_lbl.setText("🎯 Current Score: 0 / 0")
        self.start_btn.setText("▶  Start"); self.start_btn.setEnabled(True); self.start_btn.show()
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
            self.result_lbl.setText(f"✗ oops! got '{self.inp}' ({decoded}), expected '{correct}'")
            self._score(); self.skip_btn.setEnabled(False); self._result.start(1800)

    def _score(self):
        pct = int(self.score/self.total*100) if self.total else 0
        self.score_lbl.setText(f"🎯 Current Score: {self.score} / {self.total}  ({pct}%)")
        if self.score > self.hiscore or (self.score == self.hiscore and pct > self.hipct):
            self.hiscore, self.hipct = self.score, pct
            self._save_hiscore()
        self._refresh_hi()

    def _refresh_hi(self):
        self.hi_lbl.setText(f"👑 High Score: {self.hiscore} ({self.hipct}%)" if self.hiscore else "👑 High Score: —")

    def _load_hiscore(self):
        try:
            with open(HISCORE_PATH) as f:
                d = json.load(f)
                return int(d.get("score", 0)), int(d.get("pct", 0))
        except Exception:
            return 0, 0

    def _save_hiscore(self):
        try:
            with open(HISCORE_PATH, "w") as f:
                json.dump({"score": self.hiscore, "pct": self.hipct}, f)
        except Exception:
            pass

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
