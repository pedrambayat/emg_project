# Morse Code Game

A PyQt5 training game for the International Morse alphabet (A–Z). The app shows a random target letter; you key the corresponding morse pattern on a GPIO button (or any bound input) and get scored on correctness. Includes Skip / Reset controls, persistent high scores, and a Challenge mode that hides the morse hint.

- **File:** `test-gui/morse_game.py`
- **Launch:** `uv run python test-gui/morse_game.py` (or `python morse_game.py` inside a venv with PyQt5 / gpiozero)
- **High-score file:** `test-gui/.morse_highscore.json` (auto-created next to the script)

## Hardware / Input Model

The game is designed for a Raspberry Pi with two GPIO buttons:

| Pin (BCM)           | Purpose                                    | Constant             |
|---------------------|--------------------------------------------|----------------------|
| `22`                | Morse key — hold short = `.`, long = `-`   | `GPIO_PIN`           |
| `6`                 | Display toggle — blanks the Pi's backlight | `DISPLAY_BTN_PIN`    |

`gpiozero.Button` wraps both pins with `pull_up=True`. On any non-Pi machine (or when `gpiozero` is missing), the `try/except` block at the top sets `GPIO_OK = False` and the GUI still launches — but you'll have no way to key in morse unless you wire up an alternate input (see "Customizing input").

## Runtime Flow

1. **Start** — `_start()` zeroes the score, flips `running = True`, disables the Start button, enables Skip/Reset, and calls `_next()`.
2. **Next letter** — `_next()` picks a random uppercase letter from `MORSE`, shows it in the big target label, and — unless Challenge Mode is on — displays the expected morse pattern as a hint.
3. **Keying** — Each GPIO press/release fires `_press()` / `_release()` via the `_Sig` Qt signal bridge (needed because gpiozero callbacks run on a non-Qt thread).
   - `_press()` starts `_ptimer` (a `QElapsedTimer`).
   - `_release()` measures the elapsed press time. `< DOT_THRESHOLD` ms → append `.`, otherwise append `-`. Then it (re)starts `_pause`, a `LETTER_PAUSE`-ms single-shot timer.
4. **Auto-submit** — If no new press arrives before `_pause` fires, `_submit()` runs: compares `self.inp` against `MORSE[self.letter]`. On match, score goes up and `_next()` is called immediately. On mismatch, an error message is shown and `_result` (a 1800 ms timer) schedules the next letter.
5. **Skip** — `_skip()` counts the current letter as a miss (`total += 1` without incrementing `score`), reveals the answer, disables the Skip button, and uses `_result` (1200 ms) to advance.
6. **Reset** — `_reset()` stops both timers, zeros the session, and re-enables the Start button. High scores are **not** cleared.

## Scoring

- `self.score` — correct letters this session.
- `self.total` — attempts this session (correct + wrong + skipped).
- Displayed live as `Current Score: X / Y  (Z%)`.
- High score updates if `score > hiscore`, or if `score == hiscore` and the current percentage is higher (rewards a cleaner run at the same count).
- Normal and Challenge-mode high scores are tracked separately in `.morse_highscore.json`:

  ```json
  {
    "normal":    { "score": 14, "pct": 93 },
    "challenge": { "score":  7, "pct": 70 }
  }
  ```

  Old flat-format files (`{"score": N, "pct": P}`) are auto-migrated to the `normal` slot on next save.

## UI Layout

Built in `_build()` as a `QVBoxLayout` on a `QWidget`:

1. Title label (`Morse Code Game`).
2. Top row: score chip, high-score chip, stretch, Start/Skip/Reset buttons.
3. Challenge Mode checkbox.
4. Horizontal separator.
5. **Your Letter** section — big target letter + morse hint (or `? ? ?` in Challenge Mode).
6. Horizontal separator.
7. **Your Input** section — live dot/dash buffer + result/feedback line.

The window is sized to the primary screen's available geometry × 75% height so it fills the monitor without exceeding it. Adjust the `0.75` in `__init__` to change this.

## Key Constants (top of `morse_game.py`)

| Constant             | Default | What it controls                                                                 |
|----------------------|---------|----------------------------------------------------------------------------------|
| `GPIO_PIN`           | `22`    | BCM pin number of the morse-key button.                                          |
| `DISPLAY_BTN_PIN`    | `6`     | BCM pin of the secondary button that blanks/unblanks the backlight.              |
| `DOT_THRESHOLD`      | `300`   | ms. Press shorter than this = dot, longer = dash.                                |
| `LETTER_PAUSE`       | `800`   | ms of silence after the last release before the input is auto-submitted.         |
| `HISCORE_PATH`       | —       | Where the high-score JSON is written. Defaults to next to the script.            |

## How to Customize

### Change the timing feel

- **Make dots/dashes easier to distinguish:** raise `DOT_THRESHOLD` (e.g. `400`). A dash now requires a longer hold.
- **Give more time between letters:** raise `LETTER_PAUSE`. Useful for beginners who pause mid-letter.
- **Speed up reviewing wrong answers:** change the `1800` in `self._result.start(1800)` inside `_submit()` (or the `1200` in `_skip()`).

### Change the alphabet

The `MORSE` dict at the top is the entire vocabulary. Add digits or punctuation by dropping them in:

```python
MORSE.update({
    '0':'-----','1':'.----','2':'..---','3':'...--','4':'....-',
    '5':'.....','6':'-....','7':'--...','8':'---..','9':'----.',
    '?':'..--..', '.':'.-.-.-', ',':'--..--',
})
```

Restrict difficulty by temporarily whitelisting letters (e.g. only E/T/A/I/N/S for absolute beginners): edit `random.choice(list(MORSE))` in `_next()` to `random.choice(list("ETAINSON"))` (and look up each in `MORSE`).

### Change the input device

The GUI is driven by the `_sig.pressed` / `_sig.released` signals. Anything that emits those at the right times will work. Current binding (at the bottom of `__init__`):

```python
_btn.when_pressed  = _sig.pressed.emit
_btn.when_released = _sig.released.emit
```

Alternatives:

- **Keyboard (for development on Mac/Windows):** override `keyPressEvent` / `keyReleaseEvent` on `MorseGame` and emit the signals. Remember to set `event.setAutoRepeat(False)`-aware logic (Qt auto-repeats held keys — ignore `event.isAutoRepeat()`).
- **BLE from the Arduino in this repo:** have your BLE notification handler emit `_sig.pressed` / `_sig.released` on edge transitions of the EMG-threshold signal.
- **Different GPIO pin:** just change `GPIO_PIN`.

### Rearrange / restyle the UI

Everything is imperative Qt in `_build()`. Examples:

- **Bigger target letter:** change `QFont("Courier", 72, QFont.Bold)` on `self.target`.
- **Different window shape:** replace the `self.setGeometry(...)` line with `self.resize(w, h)` or `self.showMaximized()`.
- **Color theme:** call `self.setStyleSheet(...)` in `__init__` with Qt stylesheet rules; widgets like `self.target` / `self.score_lbl` can be given `setObjectName("foo")` so you can target them with `QLabel#foo { ... }`.

### Change scoring rules

Edit `_score()` and `_submit()` to taste:

- **Penalize wrong answers more harshly:** subtract from `self.score` on mismatch.
- **Require a minimum number of attempts for a high score:** guard the update with `if self.total >= 10`.
- **Time-attack mode:** start a `QTimer` in `_start()` and end the session in a timeout slot.

### Persist other things

`_load_hiscore` / `_save_hiscore` already use a JSON blob. Add new top-level keys (e.g. `"streaks"`, `"per_letter_accuracy"`) and extend the save/load helpers to match.

### Disable the Pi display toggle

If you don't want the second button to blank the backlight, drop the `_toggle_display` binding in `__init__`:

```python
# _disp.when_pressed = self._toggle_display   # remove this line
```

…or leave the code but change `_toggle_display` to no-op on non-Pi systems (it's already safe — the glob returns nothing if no backlight exists).

## Troubleshooting

- **No response to the button:** check `GPIO_OK` at startup — if `gpiozero` failed to import or the pin is busy, the app falls back silently. Run `python -c "from gpiozero import Button; Button(22)"` to see the real error.
- **"Every press becomes a dash":** your `DOT_THRESHOLD` is too low or your button bounce is long enough that the release fires late. Raise the threshold or add debouncing via `gpiozero.Button(bounce_time=0.05)`.
- **High score not saving:** check write permissions on `.morse_highscore.json` next to the script. The save path is logged silently (errors are swallowed).
- **Challenge Mode checkbox is stuck:** it refuses to toggle mid-game. Hit Reset first, then toggle.
