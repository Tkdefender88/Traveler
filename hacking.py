# hacking prototype - By: justin - Fri Mar 10 2023

import sensor
import time
import ustruct
import mjpeg
from pyb import UART


class uart_handler():

    def __init__(self):
        self.uart = None

    def init(self):
        self.uart = UART(3, 115200, timeout=5000, timeout_char=1000)
        self.uart.write("start up\n")
        time.sleep_ms(80)

    def write(self, data):
        self.uart.write(data)

    def read_line(self):
        if self.uart.any():
            return self.uart.readline()
        else:
            return None


class Protocol():
    RESET = 0
    CAPTURE = 1
    READ_DATA_LENGTH = 2
    READ_DATA_IMAGE = 3
    STOP = 4

    def __init__(self):
        self.uart = uart_handler()
        self.uart.init()
        self.image_compressed = None

    def write(self, image, start_byte=0):
        self.image_compressed = image.compress(quality=80)
        image_size = len(self.image_compressed)
        self.uart.write(image)

        if start_byte > image_size:
            start_byte = image_size

        self.uart.write(bytes([0x76, 0x00, 0x32, 0x00, 0x00, 0xFF, 0xD8]))
        self.uart.write(image_compressed[start_byte:])
        self.uart.write(bytes([0xFF, 0xD9, 0x76, 0x00, 0x32, 0x00, 0x00,]))

    def command(self):
        cmd = self.uart.read_line()
        if cmd is not None:
            if cmd[0] != 0x56:
                raise OSError("command corrupted")
            if cmd[1] != 0x00:
                raise OSError("command corrupted")
            return self.process_cmd(cmd[2:])

    def process_cmd(self, cmd):
        if cmd[0] == 0x36 and cmd[1] == 0x01:
            return self.cmd_image(cmd[2:])
        if cmd[0] == 0x26 and cmd[1] == 0x00:
            self.uart.send(
                ustruct.pack("<bbbb", 0x76, 0x00, 0x26, 0x00)
            )
            return (Protocol.RESET)
        raise OSError("command corrupted")

    def cmd_image(self, cmd):
        if cmd[0] == 0x00:
            self.uart.send(
                ustruct.pack("<bbbbb", 0x76, 0x00, 0x36, 0x00, 0x00)
            )
            return (Protocol.CAPTURE)
        if cmd[0] == 0x03:
            self.uart.send(
                ustruct.pack("<bbbbb", 0x76, 0x00, 0x36, 0x00, 0x00)
            )
            return (Protocol.STOP)
        raise OSError("command corrupted")


def init_board():
    sensor.reset()
    sensor.set_pixformat(sensor.RGB565)
    sensor.set_framesize(sensor.FHD)
    sensor.skip_frames(time=2000)


init_board()
clock = time.clock()
m = mjpeg.Mjpeg("movie.mjpeg")

# 1. UART Read -- wait for signal to take snapshot
# 2. Take snapshot -- write it to the mjpeg on the SD card
# 3. Downscale the image
# 4. write it over serial bus

protocol = Protocol()

# Main LOOP WOOOOOO
while (True):
    try:
        command = protocol.command()
        if command == Protocol.CAPTURE:
            frame = sensor.snapshot()
            m.add_frame(frame)
            small_image = frame.scale(x_size=640, y_size=480)
            protocol.send(small_image)
        if command == Protocol.STOP:
            break
    except OSError as e:
        print(str(e))

m.close(1)
