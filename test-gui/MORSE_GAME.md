# Morse Game Guide

This document explains how `test-gui/morse_game.py` works and which parts are meant to be customized.

## What the Game Does

`morse_game.py` is a PyQt5 desktop game that teaches Morse code. The app shows a target letter, waits for the player to enter dots and dashes, then checks whether the input matches the correct Morse pattern.

It supports two input modes:

- a GPIO button on Raspberry Pi
- BLE EMG input streamed from `BLE_Arduino_EMG_Sender`

The GUI still opens on a normal laptop if `gpiozero` is unavailable.

## How It Works

### 1. Configuration

The main behavior is controlled by constants at the top of the file:

- `GPIO_PIN`: input pin for the Morse key button
- `DISPLAY_BTN_PIN`: input pin for the screen-toggle button
- `SERVO_PIN`: output pin for the servo
- `DOT_THRESHOLD`: press length below this is a dot, otherwise a dash
- `LETTER_PAUSE`: silence timeout before the current input is auto-submitted
- `LIVES`: number of wrong answers allowed
- `HISCORE_PATH`: JSON file used to save high scores
- `BLE_ENABLED`: turns BLE EMG control on or off
- `BLE_ADDRESS`: optional direct BLE address
- `BLE_DEVICE_NAME`: advertised device name, such as `EMG_Sender_pbayat`
- `BLE_CONTROL_CHAR_UUID`: BLE characteristic that carries the button-like control state

The `MORSE` dictionary defines the supported alphabet. Right now it includes `A-Z`.

### 2. Hardware Setup

At import time, the script tries to create:

- a GPIO button for Morse input
- a GPIO button for toggling the display
- a servo for showing remaining lives
- an optional BLE client for EMG control-state streaming

If that setup fails, the game falls back safely:

- `GPIO_OK = False` means no physical button input
- `SERVO_OK = False` means the game still runs, but the servo is ignored
- BLE reconnects automatically if the Arduino is missing or disconnects

### 3. GUI Setup

`MorseGame.__init__()` creates the window, loads saved high scores, initializes lives and timers, builds the interface, and connects GPIO events to Qt signals.

The main UI pieces are:

- score, high score, and lives labels
- `Start`, `Skip`, and `Reset` buttons
- a challenge-mode checkbox
- a large target-letter display
- a hint label showing Morse code unless challenge mode is enabled
- a live input label and a result label

### 4. Input and Timing

The game uses two timers:

- `QElapsedTimer` measures how long the button was held
- `QTimer` waits for a pause between button presses

If BLE mode is enabled, the game subscribes to a button-like control characteristic from the Arduino:

1. the Arduino still streams raw EMG for plotting
2. the Arduino also publishes a second BLE characteristic with state `0` or `1`
3. `1` means "pressed"
4. `0` means "released"
5. the Python game maps those directly onto `_sig.pressed` and `_sig.released`

Flow:

1. `_press()` starts the elapsed timer.
2. `_release()` checks the press duration.
3. Short press becomes `.`.
4. Long press becomes `-`.
5. After each release, the pause timer starts.
6. If the player stays idle long enough, `_submit()` checks the answer.

### 5. Round Flow

- `_start()` resets the session and begins the game
- `_next()` chooses a random letter from `MORSE`
- `_submit()` compares the typed pattern with the correct one
- `_skip()` reveals the answer and advances
- `_reset()` clears the current session
- `_game_over()` ends the round once lives reach zero

### 6. Scoring

The game tracks:

- `score`: correct answers
- `total`: all attempts, including skips
- `lives`: remaining mistakes before game over

High scores are stored in `.morse_highscore.json` next to the script. Normal mode and challenge mode are saved separately.

## How to Customize It

### Adjust difficulty

Edit these constants near the top of the file:

- Increase `DOT_THRESHOLD` if dots are being read as dashes
- Increase `LETTER_PAUSE` if players need more time between symbols
- Increase or decrease `LIVES` to make the game easier or harder

Example:

```python
DOT_THRESHOLD = 400
LETTER_PAUSE = 1200
LIVES = 5
```

### Change the letters or add numbers

Update the `MORSE` dictionary.

Example:

```python
MORSE.update({
    "1": ".----",
    "2": "..---",
    "3": "...--",
})
```

If you want a beginner mode, you can also limit the random choice in `_next()` to a smaller set of letters.

### Change the UI text or appearance

Most visible text is set in `_build()`, `_skip()`, `_submit()`, and `_game_over()`.

Common changes:

- rename the window title in `setWindowTitle(...)`
- change fonts in `QFont(...)`
- change the game-over message in `_game_over()`
- resize the window by editing `setGeometry(...)`

### Change the scoring rules

Edit `_submit()` and `_score()` if you want different behavior.

Examples:

- subtract points for wrong answers
- give bonus points for streaks
- disable high-score updates until a minimum number of rounds

### Change the input source

The clean extension point is the `_sig` signal bridge:

- `_sig.pressed`
- `_sig.released`

Anything that emits those signals can drive the game. That means you can replace the GPIO button with:

- a keyboard key
- BLE button-state input
- EMG threshold events
- a custom USB controller

For non-Pi development, a practical approach is to add `keyPressEvent()` and `keyReleaseEvent()` methods and emit `_sig.pressed.emit()` / `_sig.released.emit()`.

### Disable optional hardware features

If you do not want the extra Pi hardware behavior:

- remove `_disp.when_pressed = self._toggle_display`
- ignore `_servo_to_lives()` or remove servo setup entirely

The game logic does not depend on either feature.

### Configure BLE EMG input

The default BLE device name matches the Arduino sketch in this repo:

```bash
EMG_USE_BLE=1 uv run python test-gui/morse_game.py
```

If you want to target a specific peripheral:

```bash
EMG_USE_BLE=1 EMG_BLE_ADDRESS="80:7D:3A:85:E8:C6" uv run python test-gui/morse_game.py
```

To force the old GPIO button behavior:

```bash
EMG_USE_BLE=0 uv run python test-gui/morse_game.py
```

### Calibrate raw EMG mode

If you are using `EMG_CONTROL_SOURCE=raw`, use the calibration tool before tuning the game by hand:

```bash
EMG_USE_BLE=1 EMG_CONTROL_SOURCE=raw uv run python test-gui/emg_calibration.py
```

Recommended workflow:

- capture `rest` first while fully relaxed
- capture `dots` using repeated short contractions with clear pauses
- capture `dashes` using repeated longer contractions with clear pauses

The calibration window will show:

- live raw EMG and moving average plots
- the current baseline and threshold preview
- suggested values for `EMG_FIXED_THRESHOLD`
- suggested timing values such as `EMG_GAP_MS`, `EMG_MIN_PRESS_MS`, and `EMG_DOT_THRESHOLD_MS`

Then launch the game with the suggested values, for example:

```bash
EMG_USE_BLE=1 EMG_CONTROL_SOURCE=raw EMG_FIXED_THRESHOLD=92 EMG_GAP_MS=140 EMG_DOT_THRESHOLD_MS=135 uv run python test-gui/morse_game.py
```

## Arduino Control State

`BLE_Arduino_EMG_Sender/BLE_Arduino_EMG_Sender.ino` now exposes two BLE characteristics in the same service:

- raw EMG samples for plotting
- a one-byte control state for the Morse game

The Arduino decides the control state using two thresholds:

- `CONTROL_ON_THRESHOLD`: signal level required to enter the pressed state
- `CONTROL_OFF_THRESHOLD`: lower threshold required to leave the pressed state

That small hysteresis window prevents rapid toggling near the boundary while keeping Python simple.

## Running the Game

From the repository root:

```bash
uv run python test-gui/morse_game.py
```

## Good Places to Edit

If you only want quick changes, these are the main places:

- top constants: timing, pins, lives, save path
- `MORSE`: supported symbols
- `_build()`: layout and labels
- `_next()`: target selection logic
- `_submit()`: correctness and penalties
- `_game_over()`: end-of-game behavior

## Summary

The file is organized cleanly enough that most customization falls into one of three categories:

- top-level constants for timing and hardware
- `MORSE` for content
- a few methods for UI and scoring behavior

If you want to extend it, the safest pattern is to keep the existing signal flow and modify the logic around it rather than rewriting the whole event loop.
