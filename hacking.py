# hacking prototype - By: justin - Fri Mar 10 2023

import sensor
import time
import mjpeg
from pyb import UART, Pin
from time import sleep


class uart_handler():

    def __init__(self):
        self.uart = None
        self.reset = None

    def send_photo(self, photo):
        pass

    def command(self):
        if (self.uart.any()):
            return self.uart.readline()
        else:
            return ""

    def init(self):
        self.uart = UART(3, 155200, timemout=5000, timeout_char=1000)
        self.reset = Pin("P7", Pin.OUT_OD, Pin.PULL_NONE)
        self.reset.low()
        sleep(100)
        self.reset.high()
        sleep(100)
        self.uart.write("start up\r\n")
        sleep(1000)
        self.uart.readall()  # clear

    def send(self, data):
        self.uart.write(data)


def init_board():
    sensor.reset()
    sensor.set_pixformat(sensor.RGB565)
    sensor.set_framesize(sensor.FHD)
    sensor.skip_frames(time=2000)


init_board()

big = mjpeg.Mjpeg("lolygags.mjpeg")
clock = time.clock()

# 1. UART Read -- wait for signal to take snapshot
# 2. Take snapshot -- write it to the mjpeg on the SD card
# 3. Downscale the image -- write it over serial bus

frame = sensor.snapshot()

big.add_frame(frame)

sensor.alloc_extra_fb(640, 480, frame.format()).save("smallboi.jpg")
sensor.snapshot().save("small.jpg")

big.close(1)
print("DONE!!")

uart = uart_handler()
uart.init()

# Main LOOP WOOOOOO
while (True):
    # wait for uart command
    uart.command()

    clock.tick()
    frame = sensor.snapshot()
    print(clock.fps())
