# 2.5 Button
from gpiozero import Button

button = Button(5)

while True:
    if button.is_pressed:
        print("Button is pressed")
    else:
        print("Button is not pressed")

from gpiozero import Button
from signal import pause

def say_hello():
    print("Hello!")

button = Button(5)

button.when_pressed = say_hello

pause()

