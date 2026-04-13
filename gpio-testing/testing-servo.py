from gpiozero.pins.pigpio import PiGPIOFactory
from gpiozero import Servo
from time import sleep

myFactory = PiGPIOFactory()

servo_button = 5

servo = Servo(
    servo_button,
    min_pulse_width=0.05/1000,
    max_pulse_width=2.5/1000,
    pin_factory=myFactory
)


# servo = Servo(servo_button)

# while True:
#     servo.min()
#     sleep(2)
#     servo.mid()
#     sleep(2)
#     servo.max()
#     sleep(2)



# from gpiozero import Servo
# from gpiozero.tools import sin_values
# from signal import pause

# servo = Servo(servo_button)

# servo.source = sin_values()
# servo.source_delay = 0.1

# pause()

from gpiozero import Servo
from time import sleep

servo = Servo(17)

while True:
    servo.min()
    sleep(2)
    servo.mid()
    sleep(2)
    servo.max()
    sleep(2)