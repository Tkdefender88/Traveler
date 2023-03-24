# hacking prototype - By: justin - Fri Mar 10 2023

import sensor
import time
from pyb import UART


class uart_handler():

    def __init__(self):
        self.uart = None

    def send_photo(self, photo):
        pass

    def command(self):
        if (self.uart.any()):
            return self.uart.readline()
        else:
            return ""

    def init(self):
        self.uart = UART(3, 115200, timeout=5000, timeout_char=1000)
        self.uart.write("start up\n")
        self.uart.readline()  # clear

    def send(self, data):
        self.uart.write(data)

    def read_line(self):
        if self.uart.any():
            return self.uart.readline()
        else:
            return None


class protocol():
    def __init__(self):
        pass

    def command(self, cmd):
        if cmd[0] != 0x56: raise OSError("command corrupted")
        if cmd[1] != 0x00: raise OSError("command corrupted")
        protocol.__process(cmd[2:])

    def __process(cmd):
        pass


def init_board():
    sensor.reset()
    sensor.set_pixformat(sensor.RGB565)
    sensor.set_framesize(sensor.FHD)
    sensor.skip_frames(time=2000)


clock = time.clock()

# 1. UART Read -- wait for signal to take snapshot
# 2. Take snapshot -- write it to the mjpeg on the SD card
# 3. Downscale the image -- write it over serial bus

serial = uart_handler()
serial.init()

init_board()

uart = uart_handler()
uart.init()

# Main LOOP WOOOOOO
while (True):
    data = serial.read_line()
    if (data is not None):
        frame = sensor.snapshot()
        serial.send("pic\r\n")

print("DONE!!")
