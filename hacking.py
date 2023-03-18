# Untitled - By: justin - Fri Mar 10 2023

import sensor
import time
import mjpeg
import image
from pyb import UART


class uart_handler():

    def __init__(self):
        self.uart = UART(3, 155200, timeout=5000, timeout_char=1000)

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

# Main LOOP WOOOOOO
'''
while (True):
    clock.tick()
    frame = sensor.snapshot()
    m.add_frame(frame)
    print(clock.fps())
'''
