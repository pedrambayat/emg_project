"""Autonomous servo test — sweeps a standard hobby servo on GPIO17 through
min / mid / max and a smooth continuous sweep, with no button input required.

Uses pigpio for jitter-free hardware-timed PWM (requires `sudo pigpiod` running).
If pigpio isn't available, falls back to gpiozero's default (software) pin factory.

Wiring (BCM 17 = physical pin 11):
    servo signal -> GPIO17
    servo V+     -> 5V (external supply recommended for torque; share GND with Pi)
    servo GND    -> Pi GND

Run:
    sudo pigpiod                 # once, if using pigpio
    python3 servo-sweep.py
"""

from time import sleep

from gpiozero import Servo

try:
    from gpiozero.pins.pigpio import PiGPIOFactory
    PIN_FACTORY = PiGPIOFactory()
    print("Using pigpio pin factory (hardware-timed PWM)")
except Exception as e:
    PIN_FACTORY = None
    print(f"pigpio unavailable ({e}); falling back to default factory")

SERVO_PIN        = 17
MIN_PULSE_WIDTH  = 0.5 / 1000   # 0.5 ms  -> full CCW
MAX_PULSE_WIDTH  = 2.5 / 1000   # 2.5 ms  -> full CW
SETTLE           = 1.0          # seconds to hold each discrete position
SWEEP_STEPS      = 40           # resolution of the smooth sweep
SWEEP_PERIOD     = 2.0          # seconds per min->max pass

servo = Servo(
    SERVO_PIN,
    min_pulse_width=MIN_PULSE_WIDTH,
    max_pulse_width=MAX_PULSE_WIDTH,
    pin_factory=PIN_FACTORY,
)


def discrete_positions():
    print("\n== discrete positions ==")
    for label, move in [("min", servo.min), ("mid", servo.mid), ("max", servo.max)]:
        print(f"  -> {label}")
        move()
        sleep(SETTLE)


def smooth_sweep(cycles=2):
    print(f"\n== smooth sweep ({cycles} cycles) ==")
    dt = SWEEP_PERIOD / SWEEP_STEPS
    for _ in range(cycles):
        for i in range(SWEEP_STEPS + 1):
            servo.value = -1 + 2 * (i / SWEEP_STEPS)       # -1 .. +1
            sleep(dt)
        for i in range(SWEEP_STEPS + 1):
            servo.value = 1 - 2 * (i / SWEEP_STEPS)        # +1 .. -1
            sleep(dt)


def main():
    try:
        discrete_positions()
        smooth_sweep(cycles=2)
        print("\n== parking at mid ==")
        servo.mid()
        sleep(SETTLE)
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        servo.detach()   # stop sending pulses so the servo goes slack
        servo.close()
        print("done")


if __name__ == "__main__":
    main()
