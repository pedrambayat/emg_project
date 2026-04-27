import sys
import os
import time
import math
import asyncio
import statistics
from collections import deque

import numpy as np
import pyqtgraph as pg
import qasync
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sys import platform

if platform == "win32":
    try:
        from bleak.backends.winrt.util import allow_sta

        allow_sta()
    except ImportError:
        pass


BLE_ADDRESS = os.getenv("EMG_BLE_ADDRESS", "80:7D:3A:85:E8:C6")
BLE_DEVICE_NAME = os.getenv("EMG_BLE_NAME", "EMG_Sender_pbayat")
BLE_SENSOR_CHAR_UUID = "5212ddd0-29e5-11eb-adc1-0242ac120002"
BLE_RETRY_SECONDS = 2.0

EMG_SAMPLE_RATE = 1000
EMG_AVG_WINDOW_MS = int(os.getenv("EMG_AVG_WINDOW_MS", "40"))
EMG_BASELINE_ALPHA = float(os.getenv("EMG_BASELINE_ALPHA", "0.02"))
EMG_THRESHOLD_MARGIN = float(os.getenv("EMG_THRESHOLD_MARGIN", "14"))
EMG_ACTIVE_RATIO = float(os.getenv("EMG_ACTIVE_RATIO", "0.85"))
EMG_GAP_MS = int(os.getenv("EMG_GAP_MS", "120"))
EMG_FIXED_THRESHOLD = os.getenv("EMG_FIXED_THRESHOLD")
EMG_DOT_THRESHOLD_MS = int(os.getenv("EMG_DOT_THRESHOLD_MS", "100"))
EMG_MIN_PRESS_MS = int(os.getenv("EMG_MIN_PRESS_MS", "10"))

EMG_AVG_WINDOW_SAMPLES = max(1, int(EMG_SAMPLE_RATE * EMG_AVG_WINDOW_MS / 1000))
PLOT_HISTORY_SECONDS = 8
PLOT_HISTORY_SAMPLES = EMG_SAMPLE_RATE * PLOT_HISTORY_SECONDS

REST_CAPTURE_SECONDS = int(os.getenv("EMG_CAL_REST_SECONDS", "6"))
DOT_CAPTURE_SECONDS = int(os.getenv("EMG_CAL_DOT_SECONDS", "10"))
DASH_CAPTURE_SECONDS = int(os.getenv("EMG_CAL_DASH_SECONDS", "10"))
SHORT_GAP_MAX_MS = 250


def clamp(value, low, high):
    return max(low, min(high, value))


def percentile(values, pct):
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    values = sorted(float(v) for v in values)
    idx = (len(values) - 1) * (pct / 100.0)
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return values[int(idx)]
    weight = idx - lo
    return values[lo] * (1.0 - weight) + values[hi] * weight


def median(values):
    return float(statistics.median(values)) if values else 0.0


def mean(values):
    return float(statistics.fmean(values)) if values else 0.0


def pstdev(values):
    return float(statistics.pstdev(values)) if len(values) > 1 else 0.0


def describe_series(values):
    if not values:
        return {}
    return {
        "count": len(values),
        "mean": mean(values),
        "median": median(values),
        "std": pstdev(values),
        "min": min(values),
        "max": max(values),
        "p05": percentile(values, 5),
        "p25": percentile(values, 25),
        "p75": percentile(values, 75),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
    }


def trim_start(values, ratio=0.2):
    if not values:
        return []
    start = min(len(values) - 1, int(len(values) * ratio))
    return values[start:]


def detect_segments(mavg_values, threshold, gap_ms, min_press_ms):
    if not mavg_values:
        return []

    gap_samples = max(1, int(EMG_SAMPLE_RATE * gap_ms / 1000))
    min_press_samples = max(1, int(EMG_SAMPLE_RATE * min_press_ms / 1000))
    segments = []

    active = False
    total_samples = 0
    above_samples = 0
    below_gap_samples = 0
    start_index = 0
    peak_value = 0.0

    for idx, value in enumerate(mavg_values):
        above = value >= threshold

        if not active:
            if above:
                active = True
                total_samples = 1
                above_samples = 1
                below_gap_samples = 0
                start_index = idx
                peak_value = value
            continue

        total_samples += 1
        peak_value = max(peak_value, value)

        if above:
            above_samples += 1
            below_gap_samples = 0
        else:
            below_gap_samples += 1

        if below_gap_samples < gap_samples:
            continue

        effective_samples = total_samples - below_gap_samples
        if effective_samples >= min_press_samples:
            ratio = above_samples / effective_samples if effective_samples else 0.0
            segments.append(
                {
                    "start_idx": start_index,
                    "end_idx": idx - below_gap_samples,
                    "duration_ms": int(effective_samples * 1000 / EMG_SAMPLE_RATE),
                    "peak": peak_value,
                    "above_ratio": ratio,
                }
            )

        active = False
        total_samples = 0
        above_samples = 0
        below_gap_samples = 0
        peak_value = 0.0

    if active:
        effective_samples = total_samples
        if effective_samples >= min_press_samples:
            ratio = above_samples / effective_samples if effective_samples else 0.0
            segments.append(
                {
                    "start_idx": start_index,
                    "end_idx": len(mavg_values) - 1,
                    "duration_ms": int(effective_samples * 1000 / EMG_SAMPLE_RATE),
                    "peak": peak_value,
                    "above_ratio": ratio,
                }
            )

    return segments


def find_short_below_runs(mavg_values, threshold, max_gap_ms=SHORT_GAP_MAX_MS):
    if not mavg_values:
        return []

    max_gap_samples = max(1, int(EMG_SAMPLE_RATE * max_gap_ms / 1000))
    runs = []
    below_count = 0
    had_above_before = False

    for value in mavg_values:
        above = value >= threshold
        if above:
            if 0 < below_count <= max_gap_samples and had_above_before:
                runs.append(int(below_count * 1000 / EMG_SAMPLE_RATE))
            had_above_before = True
            below_count = 0
        elif had_above_before:
            below_count += 1

    return runs


class EmgCalibrationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Raw EMG Calibration")
        screen = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(screen.x(), screen.y(), screen.width(), int(screen.height() * 0.8))

        self._client = None
        self._ble_task = None
        self._closing = False
        self._ble_status = "BLE: idle"
        self._sample_index = 0

        self._raw_plot = deque(maxlen=PLOT_HISTORY_SAMPLES)
        self._mavg_plot = deque(maxlen=PLOT_HISTORY_SAMPLES)
        self._baseline_plot = deque(maxlen=PLOT_HISTORY_SAMPLES)
        self._threshold_plot = deque(maxlen=PLOT_HISTORY_SAMPLES)

        self._mavg_window = deque(maxlen=EMG_AVG_WINDOW_SAMPLES)
        self._mavg_window_sum = 0.0
        self._last_raw = 0.0
        self._last_mavg = 0.0
        self._live_baseline = None
        self._live_threshold = None
        self._live_active = False

        self._phase_name = None
        self._phase_started_at = None
        self._phase_duration_s = 0
        self._phase_samples = []
        self._phase_results = {}

        self._build()

        self._plot_timer = QTimer(self, interval=80, timeout=self._refresh_plot)
        self._plot_timer.start()
        self._phase_timer = QTimer(self, interval=200, timeout=self._refresh_phase_status)
        self._phase_timer.start()

        self._set_ble_status("BLE: waiting to connect")
        QTimer.singleShot(0, self._start_ble)

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Raw EMG Calibration", alignment=Qt.AlignCenter)
        title.setFont(QFont("Helvetica", 18, QFont.Bold))
        layout.addWidget(title)

        self.status_lbl = QLabel()
        self.status_lbl.setFont(QFont("Helvetica", 11, QFont.Bold))
        layout.addWidget(self.status_lbl)

        self.phase_lbl = QLabel(
            "Workflow: capture rest first, then dots, then dashes. The report will suggest env vars for morse_game.py."
        )
        self.phase_lbl.setWordWrap(True)
        layout.addWidget(self.phase_lbl)

        btn_row = QHBoxLayout()
        self.rest_btn = QPushButton(f"Capture Rest ({REST_CAPTURE_SECONDS}s)")
        self.rest_btn.clicked.connect(lambda: self._begin_phase("rest", REST_CAPTURE_SECONDS))
        self.dot_btn = QPushButton(f"Capture Dots ({DOT_CAPTURE_SECONDS}s)")
        self.dot_btn.clicked.connect(lambda: self._begin_phase("dots", DOT_CAPTURE_SECONDS))
        self.dash_btn = QPushButton(f"Capture Dashes ({DASH_CAPTURE_SECONDS}s)")
        self.dash_btn.clicked.connect(lambda: self._begin_phase("dashes", DASH_CAPTURE_SECONDS))
        self.clear_btn = QPushButton("Clear Captures")
        self.clear_btn.clicked.connect(self._clear_captures)
        btn_row.addWidget(self.rest_btn)
        btn_row.addWidget(self.dot_btn)
        btn_row.addWidget(self.dash_btn)
        btn_row.addWidget(self.clear_btn)
        layout.addLayout(btn_row)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("w")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self.plot_widget.addLegend(offset=(10, 10))
        self.plot_widget.setLabel("left", "Signal")
        self.plot_widget.setLabel("bottom", "Seconds")
        self.raw_curve = self.plot_widget.plot(pen=pg.mkPen("#b0b0b0", width=1), name="Raw")
        self.mavg_curve = self.plot_widget.plot(pen=pg.mkPen("#0f766e", width=2), name="Moving Avg")
        self.baseline_curve = self.plot_widget.plot(pen=pg.mkPen("#1d4ed8", width=2), name="Baseline")
        self.threshold_curve = self.plot_widget.plot(pen=pg.mkPen("#dc2626", width=2), name="Threshold")
        layout.addWidget(self.plot_widget, stretch=1)

        layout.addWidget(self._line())

        self.report = QTextEdit()
        self.report.setReadOnly(True)
        self.report.setFont(QFont("Courier", 11))
        layout.addWidget(self.report, stretch=1)

        self._refresh_report()

    def _line(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def _set_ble_status(self, text):
        self._ble_status = text
        active = "ACTIVE" if self._live_active else "IDLE"
        baseline = f"{self._live_baseline:.1f}" if self._live_baseline is not None else "—"
        threshold = f"{self._live_threshold:.1f}" if self._live_threshold is not None else "—"
        self.status_lbl.setText(
            f"{self._ble_status} | raw {self._last_raw:.1f} | avg {self._last_mavg:.1f} | baseline {baseline} | "
            f"threshold {threshold} | state {active}"
        )

    def _refresh_phase_status(self):
        if self._phase_name is None:
            self._phase_lbl_default()
            return

        elapsed = max(0.0, time.monotonic() - self._phase_started_at)
        remaining = max(0.0, self._phase_duration_s - elapsed)
        instructions = {
            "rest": "Stay relaxed and avoid flexing.",
            "dots": "Make repeated short contractions with clear pauses.",
            "dashes": "Make repeated longer contractions with clear pauses.",
        }
        self.phase_lbl.setText(
            f"Capturing {self._phase_name} for {remaining:.1f}s. {instructions[self._phase_name]}"
        )

    def _phase_lbl_default(self):
        self.phase_lbl.setText(
            "Workflow: capture rest first, then dots, then dashes. The report will suggest env vars for morse_game.py."
        )

    def _refresh_plot(self):
        if not self._raw_plot:
            return

        count = len(self._raw_plot)
        x = np.linspace(-count / EMG_SAMPLE_RATE, 0, count)
        self.raw_curve.setData(x, np.array(self._raw_plot, dtype=float))
        self.mavg_curve.setData(x, np.array(self._mavg_plot, dtype=float))
        self.baseline_curve.setData(x, np.array(self._baseline_plot, dtype=float))
        self.threshold_curve.setData(x, np.array(self._threshold_plot, dtype=float))

    def _clear_captures(self):
        self._phase_name = None
        self._phase_started_at = None
        self._phase_duration_s = 0
        self._phase_samples = []
        self._phase_results = {}
        self._refresh_report()
        self._phase_lbl_default()

    def _begin_phase(self, name, duration_s):
        if self._phase_name is not None:
            return
        if name != "rest" and "rest" not in self._phase_results:
            self.phase_lbl.setText("Capture rest first so the threshold recommendation has a baseline.")
            return

        self._phase_name = name
        self._phase_started_at = time.monotonic()
        self._phase_duration_s = duration_s
        self._phase_samples = []
        self._refresh_phase_status()
        QTimer.singleShot(duration_s * 1000, self._finish_phase)

    def _finish_phase(self):
        if self._phase_name is None:
            return

        samples = self._phase_samples[:]
        self._phase_results[self._phase_name] = self._summarize_phase(self._phase_name, samples)
        self._phase_name = None
        self._phase_started_at = None
        self._phase_duration_s = 0
        self._phase_samples = []
        self._phase_lbl_default()
        self._refresh_report()

    def _summarize_phase(self, name, samples):
        raw_values = [sample["raw"] for sample in samples]
        mavg_values = [sample["mavg"] for sample in samples]
        trimmed = trim_start(mavg_values, 0.2)
        return {
            "name": name,
            "sample_count": len(samples),
            "seconds": len(samples) / EMG_SAMPLE_RATE,
            "raw_stats": describe_series(raw_values),
            "mavg_stats": describe_series(trimmed if trimmed else mavg_values),
            "mavg_values": mavg_values,
        }

    def _provisional_threshold(self):
        rest = self._phase_results.get("rest")
        if not rest:
            return None

        stats = rest["mavg_stats"]
        baseline = stats.get("median", 0.0)
        rest_p95 = stats.get("p95", baseline)
        rest_std = stats.get("std", 0.0)
        return max(rest_p95 + max(2.0, 1.5 * rest_std), baseline + 6.0)

    def _recommendations(self):
        rest = self._phase_results.get("rest")
        if not rest:
            return None

        provisional_threshold = self._provisional_threshold()
        if provisional_threshold is None:
            return None

        dot_phase = self._phase_results.get("dots")
        dash_phase = self._phase_results.get("dashes")
        phase_segments = {}
        short_gap_runs = []

        for phase_name, phase in (("dots", dot_phase), ("dashes", dash_phase)):
            if not phase:
                continue
            mavg_values = phase["mavg_values"]
            segments = detect_segments(mavg_values, provisional_threshold, EMG_GAP_MS, EMG_MIN_PRESS_MS)
            phase_segments[phase_name] = [seg for seg in segments if seg["above_ratio"] >= 0.45]
            short_gap_runs.extend(find_short_below_runs(mavg_values, provisional_threshold))

        all_segments = phase_segments.get("dots", []) + phase_segments.get("dashes", [])
        if not all_segments:
            return {
                "provisional_threshold": provisional_threshold,
                "message": "No clear contractions were detected. Try stronger flexes or lower the threshold margin during calibration.",
            }

        rest_stats = rest["mavg_stats"]
        rest_baseline = rest_stats.get("median", 0.0)
        rest_p95 = rest_stats.get("p95", rest_baseline)

        peaks = [segment["peak"] for segment in all_segments]
        peak_floor = percentile(peaks, 25)
        fixed_threshold = int(round((rest_p95 + peak_floor) / 2.0))
        fixed_threshold = max(fixed_threshold, int(math.ceil(rest_p95 + 1.0)))
        threshold_margin = round(max(1.0, fixed_threshold - rest_baseline), 1)

        dot_durations = [segment["duration_ms"] for segment in phase_segments.get("dots", [])]
        dash_durations = [segment["duration_ms"] for segment in phase_segments.get("dashes", [])]
        all_ratios = [segment["above_ratio"] for segment in all_segments]

        if dot_durations:
            dot_min_press = int(round(clamp(percentile(dot_durations, 10) * 0.35, 10, 80)))
        else:
            dot_min_press = EMG_MIN_PRESS_MS

        if dot_durations and dash_durations:
            dot_center = median(dot_durations)
            dash_center = median(dash_durations)
            if dash_center > dot_center + 20:
                dot_threshold = int(round((dot_center + dash_center) / 2.0))
            else:
                dot_threshold = int(round(dot_center + 40))
            dot_threshold = int(clamp(dot_threshold, 40, 500))
        elif dot_durations:
            dot_threshold = int(round(clamp(percentile(dot_durations, 90) + 35, 40, 500)))
        else:
            dot_threshold = EMG_DOT_THRESHOLD_MS

        if short_gap_runs:
            gap_ms = int(round(clamp(percentile(short_gap_runs, 95) + 20, 60, 220)))
        else:
            gap_ms = EMG_GAP_MS

        if all_ratios:
            active_ratio = round(clamp(percentile(all_ratios, 20) - 0.05, 0.6, 0.95), 2)
        else:
            active_ratio = EMG_ACTIVE_RATIO

        return {
            "provisional_threshold": provisional_threshold,
            "phase_segments": phase_segments,
            "fixed_threshold": fixed_threshold,
            "threshold_margin": threshold_margin,
            "dot_threshold_ms": dot_threshold,
            "min_press_ms": dot_min_press,
            "gap_ms": gap_ms,
            "active_ratio": active_ratio,
            "dot_durations": dot_durations,
            "dash_durations": dash_durations,
            "message": None,
        }

    def _refresh_report(self):
        lines = []
        lines.append("Calibration report")
        lines.append("")
        lines.append("Current launch defaults")
        lines.append(f"  EMG_AVG_WINDOW_MS={EMG_AVG_WINDOW_MS}")
        lines.append(f"  EMG_GAP_MS={EMG_GAP_MS}")
        lines.append(f"  EMG_THRESHOLD_MARGIN={EMG_THRESHOLD_MARGIN}")
        lines.append(f"  EMG_DOT_THRESHOLD_MS={EMG_DOT_THRESHOLD_MS}")
        lines.append(f"  EMG_MIN_PRESS_MS={EMG_MIN_PRESS_MS}")
        lines.append(f"  EMG_ACTIVE_RATIO={EMG_ACTIVE_RATIO}")
        lines.append("")

        for phase_name in ("rest", "dots", "dashes"):
            phase = self._phase_results.get(phase_name)
            if not phase:
                lines.append(f"{phase_name}: not captured")
                lines.append("")
                continue

            stats = phase["mavg_stats"]
            lines.append(f"{phase_name}: {phase['seconds']:.1f}s, {phase['sample_count']} samples")
            lines.append(
                "  moving avg median "
                f"{stats.get('median', 0.0):.1f}, std {stats.get('std', 0.0):.1f}, "
                f"p95 {stats.get('p95', 0.0):.1f}, max {stats.get('max', 0.0):.1f}"
            )
            lines.append("")

        recommendations = self._recommendations()
        if not recommendations:
            lines.append("Capture rest to generate recommendations.")
            self.report.setPlainText("\n".join(lines))
            return

        lines.append("Recommendations")
        lines.append(f"  provisional threshold during analysis: {recommendations['provisional_threshold']:.1f}")

        if recommendations["message"]:
            lines.append(f"  {recommendations['message']}")
            self.report.setPlainText("\n".join(lines))
            return

        dot_segments = recommendations["phase_segments"].get("dots", [])
        dash_segments = recommendations["phase_segments"].get("dashes", [])
        lines.append(f"  detected dot segments: {len(dot_segments)}")
        lines.append(f"  detected dash segments: {len(dash_segments)}")
        if recommendations["dot_durations"]:
            lines.append(f"  dot durations ms: {recommendations['dot_durations']}")
        if recommendations["dash_durations"]:
            lines.append(f"  dash durations ms: {recommendations['dash_durations']}")
        lines.append("")
        lines.append("Suggested env vars")
        lines.append(f"  EMG_FIXED_THRESHOLD={recommendations['fixed_threshold']}")
        lines.append(f"  EMG_THRESHOLD_MARGIN={recommendations['threshold_margin']}")
        lines.append(f"  EMG_GAP_MS={recommendations['gap_ms']}")
        lines.append(f"  EMG_MIN_PRESS_MS={recommendations['min_press_ms']}")
        lines.append(f"  EMG_DOT_THRESHOLD_MS={recommendations['dot_threshold_ms']}")
        lines.append(f"  EMG_ACTIVE_RATIO={recommendations['active_ratio']}")
        lines.append("")
        lines.append("Launch example")
        lines.append(
            "  EMG_USE_BLE=1 EMG_CONTROL_SOURCE=raw "
            f"EMG_FIXED_THRESHOLD={recommendations['fixed_threshold']} "
            f"EMG_GAP_MS={recommendations['gap_ms']} "
            f"EMG_MIN_PRESS_MS={recommendations['min_press_ms']} "
            f"EMG_DOT_THRESHOLD_MS={recommendations['dot_threshold_ms']} "
            f"EMG_ACTIVE_RATIO={recommendations['active_ratio']} "
            "uv run python test-gui/morse_game.py"
        )
        lines.append("")
        lines.append("Interpretation")
        lines.append("  If resting noise still triggers, raise EMG_FIXED_THRESHOLD or EMG_GAP_MS slightly.")
        lines.append("  If real contractions are missed, lower EMG_FIXED_THRESHOLD by 3 to 8.")
        lines.append("  If dots get split into several symbols, raise EMG_GAP_MS.")
        lines.append("  If dots become dashes, raise EMG_DOT_THRESHOLD_MS only if your short flexes are genuinely longer.")

        self.report.setPlainText("\n".join(lines))

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
            device = await BleakScanner.find_device_by_address(BLE_ADDRESS, timeout=5.0)
            if device is not None:
                return device

        devices = await BleakScanner.discover(timeout=5.0)
        for device in devices:
            if device.name == BLE_DEVICE_NAME:
                return device
        for device in devices:
            if device.name and device.name.startswith("EMG_Sender_"):
                return device
        return None

    def _handle_emg_data(self, characteristic: BleakGATTCharacteristic, data: bytearray):
        if not data:
            return

        for sample in data:
            self._process_sample(float(sample))

        self._set_ble_status(self._ble_status)

    def _process_sample(self, sample):
        self._sample_index += 1
        self._last_raw = sample

        if len(self._mavg_window) == self._mavg_window.maxlen:
            self._mavg_window_sum -= self._mavg_window[0]
        self._mavg_window.append(sample)
        self._mavg_window_sum += sample
        self._last_mavg = self._mavg_window_sum / len(self._mavg_window)

        if self._live_baseline is None:
            self._live_baseline = self._last_mavg
        elif not self._live_active:
            self._live_baseline = (
                (1.0 - EMG_BASELINE_ALPHA) * self._live_baseline
                + EMG_BASELINE_ALPHA * self._last_mavg
            )

        if EMG_FIXED_THRESHOLD is not None:
            self._live_threshold = float(EMG_FIXED_THRESHOLD)
        else:
            self._live_threshold = self._live_baseline + EMG_THRESHOLD_MARGIN

        self._live_active = self._last_mavg >= self._live_threshold

        self._raw_plot.append(self._last_raw)
        self._mavg_plot.append(self._last_mavg)
        self._baseline_plot.append(self._live_baseline)
        self._threshold_plot.append(self._live_threshold)

        if self._phase_name is not None:
            self._phase_samples.append({"raw": self._last_raw, "mavg": self._last_mavg})

    async def _disconnect_ble(self):
        client, self._client = self._client, None
        if client is None:
            return
        try:
            if client.is_connected:
                try:
                    await client.stop_notify(BLE_SENSOR_CHAR_UUID)
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

    def closeEvent(self, event):
        self._closing = True
        if self._ble_task is not None:
            asyncio.create_task(self.shutdown())
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    window = EmgCalibrationWindow()
    app.aboutToQuit.connect(lambda: asyncio.create_task(window.shutdown()))
    window.show()
    with loop:
        loop.run_forever()
