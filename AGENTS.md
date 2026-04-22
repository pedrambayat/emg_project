# Repository Guidelines

## Project Structure & Module Organization
This repository is organized around a small set of Python scripts rather than a packaged `src/` layout. `Final_Starter_Code_Part_1.py` is the main PyQt5 BLE client for live EMG plotting, and `bluetooth_discover.py` is the helper used to find the Arduino BLE address. Arduino firmware lives in `BLE_Arduino_EMG_Sender/`, GUI experiments live in `test-gui/`, and Raspberry Pi hardware checks live in `gpio-testing/`. Reference material is under `docs/`, with screenshots in `screenshots/`.

## Build, Test, and Development Commands
Use Python 3.11 with `uv`.

```bash
uv sync
```
Installs pinned dependencies into `.venv`.

```bash
uv run python bluetooth_discover.py
```
Scans for the Arduino BLE peripheral before updating the `ADDRESS` constant in the main app.

```bash
uv run python Final_Starter_Code_Part_1.py
```
Runs the desktop GUI for BLE streaming and EMG visualization.

```bash
uv run python gpio-testing/testing-led.py
```
Runs a hardware-specific Raspberry Pi smoke test.

## Coding Style & Naming Conventions
Follow existing Python style: 4-space indentation, `snake_case` for functions and modules, and `CapWords` for classes such as `MyApp`. Keep new scripts focused and single-purpose, matching the current file naming pattern (`bluetooth_discover.py`, `testing-servo.py`). No formatter or linter is configured, so keep imports tidy, avoid unused code, and stay close to PEP 8.

## Testing Guidelines
There is no automated test suite configured in `pyproject.toml`. Validate changes with targeted manual runs:

- GUI/BLE changes: run `uv run python Final_Starter_Code_Part_1.py`
- Discovery changes: run `uv run python bluetooth_discover.py`
- GPIO changes: run the relevant script in `gpio-testing/` on Pi hardware

Document the exact hardware used when behavior depends on BLE, GPIO, or Arduino firmware.

## Commit & Pull Request Guidelines
Recent commits use short, lowercase subjects such as `gui`, `gpio testing`, and `servo-test`. Keep commit messages brief, imperative, and scoped to one change. Pull requests should describe the user-visible effect, note any required hardware or BLE setup, link the related issue when available, and include screenshots for GUI changes.

## Configuration & Safety Notes
Do not commit personal BLE addresses, local device names, or machine-specific paths. Treat `ADDRESS` values and Pi display setup as local configuration, and keep `.ui` file expectations aligned with `simple_GUI.ui`.
