# EMG Signal Acquisition

Real-time EMG (electromyography) signal acquisition and visualization. An Arduino MKR WiFi 1010 samples analog EMG signals at 1 kHz and streams them wirelessly over BLE to a PyQt5 desktop app that plots the data live.

## Setup

### 1. Install uv

**macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Install dependencies

```bash
uv sync
```

if not working, change PATH:

```bash
$env:Path += ";C:\Users\pbayat\.local\bin"
uv --version
```

```bash
[Environment]::SetEnvironmentVariable(
  "Path",
  [Environment]::GetEnvironmentVariable("Path", "User") + ";C:\Users\pbayat\.local\bin",
  "User"
)
```

This creates a `.venv` and installs all pinned dependencies.

## Activate the virtual environment
If needed: 
```bash
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
then 
```bash
.venv\Scripts\activate
```

## Usage

**Find your Arduino's BLE address (first time only):**
```bash
uv run python bluetooth_discover.py
```

Note the address of the device named `EMG_Sender_<pennKey>`, then set the `ADDRESS` variable at the top of `Final_Starter_Code_Part_1.py`.

**Run the GUI:**
```bash
uv run python Final_Starter_Code_Part_1.py
```

## Arduino

Open `BLE_Arduino_EMG_Sender/BLE_Arduino_EMG_Sender.ino` in the Arduino IDE, set the `pennKey` variable to a unique identifier, then compile and upload to an Arduino MKR WiFi 1010.


## Pi setup
```bash
export DISPLAY=:0
chmod 0700 /run/user/1000
```
