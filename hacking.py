# hacking prototype - By: justin - Fri Mar 10 2023

import sensor
import time
import ustruct
import mjpeg
from pyb import UART, RTC


class Protocol():
    RESET = 0
    CAPTURE = 1
    READ_DATA_LENGTH = 2
    READ_DATA_IMAGE = 3
    STOP = 4

    def __init__(self):
        self.uart = UART(3, 115200, timeout=5000, timeout_char=1000)
        self.uart.write("start up\n")
        self.start_byte = 0
        self.length_to_read = -1
        self.rtc = RTC()

        date_time = self.rtc.datetime()
        print(date_time)
        self.mjpeg = mjpeg.Mjpeg(
                "{:04}-{:02}-{:02}-{:02}-{:02}-{:02}.mjpeg".format(
                    date_time[0],
                    date_time[1],
                    date_time[2],
                    date_time[4],
                    date_time[5],
                    date_time[6]
                )
            )

    def send_photo(self, image):
        compressed_image = image.compress(quality=80)
        image_size = compressed_image.size()
        print(image_size)

        if self.start_byte > image_size:
            self.start_byte = image_size

        if self.length_to_read < 0:
            self.length_to_read = image_size

        self.uart.write(bytes([0x76, 0x00, 0x32, 0x00, 0x00, 0xFF, 0xD8]))
        self.uart.write(
            compressed_image.bytearray()[self.start_byte:self.length_to_read]
        )
        self.uart.write(bytes([0xFF, 0xD9, 0x76, 0x00, 0x32, 0x00, 0x00,]))

    def send_photo_length(self):
        image_size = sensor.get_fb().compress(quality=80).size()
        print(image_size)
        self.uart.write(bytes([0x76, 0x00, 0x34, 0x00, 0x04, 0x00, 0x00]))
        self.uart.write(
                bytes(
                    [(image_size >> 24) & 0xff,
                     (image_size >> 16) & 0xff,
                     (image_size >> 8) & 0xff,
                     (image_size & 0xff)]
                )
            )

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
        if cmd[0] == 0x34 and cmd[1] == 0x01 and cmd[2] == 0x00:
            return self.send_photo_length()
        if cmd[0] == 0x32 and cmd[1] == 0x0C:
            return self.command_read_image_data(cmd[2:])

        raise OSError("command corrupted")

    def command_read_image_data(self, cmd):
        if len(cmd) < 11:
            raise OSError("command corrupted")
        if cmd[:4] != [0x00, 0x0A, 0x00, 0x00]:
            raise OSError("command corrupted")

        self.start_byte = cmd[4] << 8 | cmd[5]
        self.length_to_read = cmd[8] << 8 | cmd[9]

        if self.length_to_read == 0:
            self.length_to_read = -1

        self.send_photo(sensor.get_fb())
        return Protocol.READ_DATA_IMAGE

    def capture_image(self):
        image = sensor.snapshot()
        self.mjpeg.add_frame(image)
        image.scale(x_size=640, y_size=480)

    def cmd_image(self, cmd):
        if cmd[0] == 0x00:
            self.uart.write(bytes([0x76, 0x00, 0x36, 0x00, 0x00]))
            self.capture_image()
            return (Protocol.CAPTURE)

        if cmd[0] == 0x03:
            self.uart.write(bytes([0x76, 0x00, 0x36, 0x00, 0x00]))
            self.close()
            return (Protocol.STOP)

        raise OSError("command corrupted")

    def close(self):
        self.mjpeg.close(1)


def init_board():
    sensor.reset()
    sensor.set_pixformat(sensor.RGB565)
    sensor.set_framesize(sensor.FHD)
    sensor.skip_frames(time=2000)


def testing():
    try:
        protocol.capture_image()
        protocol.send_photo_length()
        protocol.command_read_image_data(
            # p      p     p    p      x    x     p     y     y     p      p
            [0x00, 0x0A, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0A]
        )
    except OSError as e:
        print(str(e))


init_board()
m = mjpeg.Mjpeg("movie.mjpeg")
protocol = Protocol()

testing()
# Main LOOP WOOOOOO
'''
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
'''
