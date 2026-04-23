# Morse Game Code Report

This report explains how `test-gui/morse_game.py` works, chunk by chunk, based on the current version of the file.

## Overview

The Morse game has four main responsibilities:

1. Build the PyQt GUI.
2. Read player input from either GPIO or BLE.
3. Convert EMG activity into Morse dots and dashes.
4. Run the game logic for rounds, scoring, lives, and feedback.

## 1. Imports and Platform Setup

At the top of the file, the code imports:

- standard Python modules like `sys`, `json`, `os`, and `asyncio`
- `deque` for the moving average window
- PyQt5 widgets, timers, fonts, and signals
- `bleak` for Bluetooth Low Energy communication
- `qasync` so PyQt and `asyncio` can run together

There is also a Windows-specific setup block:

```python
if platform == "win32":
    try:
        from bleak.backends.winrt.util import allow_sta
        allow_sta()
    except ImportError:
        pass
```

This makes Bleak cooperate correctly with the Qt GUI event loop on Windows.

## 2. Configuration Constants

The constants near the top of the file define the behavior of the game.

### Gameplay and hardware constants

- `GPIO_PIN`, `DISPLAY_BTN_PIN`, `SERVO_PIN`: pin numbers for Raspberry Pi hardware
- `MIN_PRESS_MS`: ignores accidental very short presses
- `DOT_THRESHOLD`: if a press is shorter than this, it becomes a dot; otherwise it becomes a dash
- `LETTER_PAUSE`: silence time before auto-submitting the current letter
- `CORRECT_PAUSE`: short delay before moving to the next letter after a correct answer
- `LIVES`: number of wrong attempts allowed
- `HISCORE_PATH`: where high scores are stored

### BLE constants

- `BLE_ADDRESS`, `BLE_DEVICE_NAME`: used to find the EMG peripheral
- `BLE_ENABLED`: enables BLE input
- `EMG_CONTROL_SOURCE`: decides whether to use raw EMG processing or the BLE control byte
- `BLE_SENSOR_CHAR_UUID`: raw EMG BLE characteristic
- `BLE_CONTROL_CHAR_UUID`: button-like BLE control characteristic
- `BLE_RETRY_SECONDS`: retry delay after disconnect

### EMG processing constants

- `EMG_SAMPLE_RATE`: expected sample rate of the EMG stream
- `EMG_AVG_WINDOW_MS`: moving average window length
- `EMG_GAP_MS`: allowed below-threshold gap before ending a segment
- `EMG_BASELINE_ALPHA`: speed of baseline adaptation
- `EMG_THRESHOLD_MARGIN`: amount above baseline needed to count as active
- `EMG_ACTIVE_RATIO`: fraction of a segment that must stay above threshold
- `EMG_FIXED_THRESHOLD`: optional fixed override threshold

The code also converts some of these into sample counts:

- `EMG_AVG_WINDOW_SAMPLES`
- `EMG_GAP_SAMPLES`

## 3. Morse and Feedback Tables

The `MORSE` dictionary maps letters `A-Z` to Morse strings like `".-"` or `"-..."`.

The `CORRECT_MESSAGES` list stores the short positive messages shown when the player gets a letter right.

## 4. Optional Hardware Setup

The two `try` blocks attempt to initialize:

- GPIO buttons using `gpiozero`
- a servo for displaying remaining lives

If GPIO setup fails:

- `_btn` and `_disp` are set to `None`
- `GPIO_OK` becomes `False`

If servo setup fails:

- `_servo` is set to `None`
- `SERVO_OK` becomes `False`

That fallback makes the game still runnable on non-Pi systems.

## 5. Signal Bridge

The `_Sig` class defines two Qt signals:

- `pressed`
- `released`

These signals are used as a clean abstraction layer between hardware input and game logic. GPIO, BLE control bytes, or processed EMG can all emit the same two signals.

## 6. Main Window Initialization

The `MorseGame` class inherits from `QMainWindow`.

In `__init__`, the code initializes:

- game state: current letter, typed Morse input, score, lives, challenge mode
- BLE state: client, task, connection status, active state
- EMG detector state: moving average buffer, baseline, threshold, segment counters
- timers:
  - `_ptimer`: measures one press duration
  - `_pause`: waits for silence before submitting a letter
  - `_result`: delays before showing the next letter

Then it:

- builds the GUI with `_build()`
- loads and displays high scores
- updates lives and servo state
- connects `_sig.pressed` and `_sig.released` to `_press()` and `_release()`
- optionally wires GPIO buttons if available
- starts the BLE loop if BLE input is enabled

## 7. GUI Construction

The `_build()` method constructs the whole interface.

It creates:

- the title label
- score, high-score, and lives labels
- `Start`, `Skip`, and `Reset` buttons
- the challenge mode checkbox
- a status label showing BLE state and whether input is active
- the large target-letter display
- the Morse hint display
- the current typed input display
- the bottom result/feedback label

The `_line()` helper just returns a horizontal separator widget.

## 8. Starting and Resetting Rounds

### `_start()`

Begins a new game session by:

- resetting score and lives
- resetting EMG detector state
- updating labels and servo
- enabling/disabling buttons appropriately
- calling `_next()` to start the first round

### `_next()`

Moves to the next round by:

- stopping any pending timers
- clearing current input and bottom message
- choosing a random target letter
- updating the large letter display
- showing either the Morse hint or `? ? ?` in challenge mode

### `_reset()`

Fully returns the game to its initial state:

- clears timers
- stops the run
- resets score, lives, letter, and EMG detector state
- resets labels and buttons

## 9. Challenge Mode

`_toggle_challenge()` only allows challenge mode to change when the game is not currently running.

If the player tries to toggle it mid-game, the checkbox is reverted to the current mode.

## 10. Skip Behavior

`_skip()`:

- counts the current letter as attempted
- updates score display
- shows a bottom message revealing the correct answer
- disables skip temporarily
- waits `1200 ms` before moving to the next letter

## 11. Press Detection

### `_press()`

Runs when a press begins:

- ignores input if the game is not running
- ignores repeated presses if one is already active
- ignores input while the result timer is active
- starts the elapsed timer for the press

### `_release()`

Runs when a press ends:

- ignores release if nothing is currently pressed
- passes the measured duration to `_append_symbol()`

## 12. Turning Presses Into Dots and Dashes

`_append_symbol(press_ms)` is where a measured press becomes Morse input.

It works like this:

1. Ignore the press if it is shorter than `MIN_PRESS_MS`.
2. If the press is shorter than `DOT_THRESHOLD`, append `"."`.
3. Otherwise append `"-"`.
4. Update the on-screen input label.
5. If the typed Morse exactly matches the target letter, submit immediately.
6. Otherwise start the silence timer so the letter can auto-submit later.

This is the place where press duration turns into dot vs dash.

## 13. Submitting a Letter

`_submit()` judges the current typed Morse against the target.

### If correct

- increment total attempts
- compare `self.inp` to `MORSE[self.letter]`
- show a random success message at the bottom
- increment score
- update score/high-score display
- disable skip temporarily
- start the short `CORRECT_PAUSE` timer before moving on

### If wrong

- build a message showing what was entered and what was expected
- decrement lives
- update the lives display and servo
- update the score label
- either go to game over or wait `1800 ms` before advancing

## 14. Score and High Score Management

### `_score()`

Updates the live score label with:

- correct answers
- total attempts
- percentage correct

It also updates the saved high score if the current run beats the previous one.

### `_refresh_hi()`

Updates the high-score label depending on whether challenge mode is on or off.

### `_load_hiscore()`

Loads high-score data from `.morse_highscore.json`.

It supports both:

- the newer format with separate `normal` and `challenge`
- an older flat format with just `score` and `pct`

### `_save_hiscore()`

Writes updated high-score data back to disk.

## 15. Lives and Servo

### `_refresh_lives()`

Shows remaining lives using hearts:

- filled hearts for remaining lives
- empty hearts for lost lives

### `_servo_to_lives()`

Moves the servo according to lives left. If no servo is present, the method safely does nothing.

## 16. Game Over

`_game_over()`:

- stops timers
- stops the current run
- shows the final score
- replaces the large target display with `"u suck lol"`
- disables skip
- re-enables the start button

## 17. Display Toggle

`_toggle_display()` toggles the backlight power of a Raspberry Pi display by writing to:

- `/sys/class/backlight/.../bl_power`

If permission is denied, it falls back to using `sudo`.

## 18. BLE Status Display

`_set_ble_status()` updates the small status label under the top controls.

It shows:

- current BLE state such as scanning/connecting/connected
- whether the input is currently `ACTIVE` or `IDLE`

## 19. Resetting EMG Detector State

`_reset_input_gate()` clears all raw-EMG processing state:

- active flags
- elapsed timer
- moving average buffer and sum
- baseline and threshold
- current segment counters

This is used when starting or resetting the game.

## 20. BLE Control-Byte Path

`_set_effective_input_state(active)` translates a boolean active/inactive state into:

- `_sig.pressed.emit()`
- `_sig.released.emit()`

This is used only when the code is configured to use the BLE control characteristic directly.

## 21. Starting the BLE Background Task

`_start_ble()` launches the BLE loop only if one is not already running.

The BLE loop itself runs in the background as an `asyncio` task.

## 22. BLE Connection Loop

`_ble_loop()` handles the full BLE lifecycle:

1. update status to scanning
2. find the device
3. connect with `BleakClient`
4. subscribe to both:
   - raw EMG notifications
   - control-byte notifications
5. update status to connected
6. keep the connection alive until disconnect
7. retry after a short delay if disconnected or if an error happens

This loop runs until the window is closing.

## 23. Finding the BLE Device

`_find_ble_device()`:

- searches by BLE address if one is set
- otherwise scans by advertised device name

This keeps BLE setup flexible for different machines.

## 24. BLE Control Characteristic Handler

`_handle_control_state()` reads the one-byte BLE control state from the Arduino.

If `EMG_CONTROL_SOURCE == "ble"`:

- a change to `1` becomes active input
- a change to `0` becomes inactive input

If the game is using raw EMG processing instead, this handler effectively does nothing for gameplay.

## 25. Raw EMG Processing

`_process_emg_sample()` is the core of the raw EMG detector.

This is the chunk that turns a noisy EMG signal into a clean Morse press.

### Step 1: moving average

The code keeps a fixed-length `deque` of recent samples and a running sum.

That lets it compute a moving average efficiently:

- subtract oldest sample if needed
- add newest sample
- divide by window length

### Step 2: baseline tracking

If no EMG segment is active, the baseline slowly adapts toward the moving average using:

- `EMG_BASELINE_ALPHA`

This gives the detector a notion of “resting signal level”.

### Step 3: threshold calculation

The active threshold is either:

- `EMG_FIXED_THRESHOLD`, if explicitly set
- or `baseline + EMG_THRESHOLD_MARGIN`

### Step 4: segment start

If the moving average rises above threshold while no segment is active:

- begin a segment
- mark input as active
- initialize counters for total samples, above-threshold samples, and below-threshold gap length

### Step 5: segment continuation

While a segment is active:

- count how many total samples belong to the segment
- count how many of them stay above threshold
- count consecutive samples below threshold

### Step 6: segment end

If the below-threshold gap becomes at least `EMG_GAP_SAMPLES`, the segment ends.

The code then computes:

- segment duration in milliseconds
- ratio of above-threshold samples to total effective samples

### Step 7: symbol acceptance

If the ratio is at least `EMG_ACTIVE_RATIO`, the segment is considered a valid press.

Its duration is converted into a dot or dash through `_append_symbol()`.

If the ratio is too low, the segment is discarded.

Finally, all segment counters are reset and the input state becomes idle again.

## 26. Raw BLE Sensor Handler

`_handle_emg_data()` is called whenever a BLE packet of raw EMG samples arrives.

If the game is using raw EMG mode:

- convert the packet into a Python list
- feed each sample into `_process_emg_sample()`
- refresh the BLE/input status label

This is the bridge between BLE packets and symbol generation.

## 27. BLE Disconnect and Shutdown

### `_disconnect_ble()`

Stops BLE notifications and disconnects the client safely. If the input was still marked active, it forces a release first.

### `shutdown()`

Cancels the BLE background task and then disconnects cleanly.

### `closeEvent()`

Runs when the window is closing:

- marks the app as closing
- starts async shutdown if needed
- closes GPIO inputs
- detaches and closes the servo
- accepts the close event

## 28. Program Entry Point

At the bottom of the file:

1. create `QApplication`
2. create a `qasync` event loop
3. set it as the current asyncio event loop
4. create and show `MorseGame`
5. hook app shutdown into async cleanup
6. run the combined Qt + asyncio loop forever

## Summary

The full control flow is:

1. raw EMG or BLE control data arrives
2. raw EMG is converted into a clean segment by `_process_emg_sample()`
3. the segment duration becomes a dot or dash in `_append_symbol()`
4. if the Morse string is complete, `_submit()` runs immediately
5. `_submit()` updates score/lives and schedules the next round

In short:

- BLE provides the signal
- the EMG detector turns signal into presses
- press duration becomes dots and dashes
- dots and dashes are compared against the target letter
- the game updates score, lives, and feedback
