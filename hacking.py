# hacking prototype - By: justin - Fri Mar 10 2023

import sensor
import mjpeg
import time
from pyb import UART


class Protocol():

    def __init__(self):
        self.uart = UART(3, 115200, timeout=150, timeout_char=150)
        self.uart.write("start up\n")
        self.start_byte = 0
        self.length_to_read = -1
        self.running = True
        self.file_count = 0

        self.open_new_mjpeg()

    def is_running(self):
        return self.running

    def send_photo(self, image):
        compressed_image = image.compress(quality=50)
        image_size = compressed_image.size()

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
        print("image size " + str(image_size))
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
        cmd = self.uart.read()
        if cmd is not None:
            print("Command received")
            print([hex(x) for x in cmd])
            if cmd[0] != 0x56:
                raise OSError("command corrupted first byte not 0x56")
            if cmd[1] != 0x00:
                raise OSError("command corrupted second byte not 0x00")
            return self.process_cmd(cmd[2:])

    def process_cmd(self, cmd):
        if cmd[0] == 0x36 and cmd[1] == 0x01:
            self.cmd_image(cmd[2:])
        elif cmd[0] == 0x34 and cmd[1] == 0x01 and cmd[2] == 0x00:
            self.send_photo_length()
        elif cmd[0] == 0x32 and cmd[1] == 0x0C:
            self.command_read_image_data(cmd[2:])
        else:
            print([hex(x) for x in cmd])
            raise OSError("command corrupted did not recognize command prefix")

    def command_read_image_data(self, cmd):
        if len(cmd) < 9:
            print(cmd)
            raise OSError(
                "command corrupted - command length too short for image data"
            )
        self.start_byte = cmd[4] << 8 | cmd[5]
        self.length_to_read = cmd[8] << 8 | cmd[9]

        if self.length_to_read == 0:
            self.length_to_read = -1

        self.send_photo(sensor.get_fb())

    def capture_image(self):
        image = sensor.snapshot()
        self.mjpeg.add_frame(image)
        image.scale(x_size=640, y_size=480)

    def open_new_mjpeg(self):
        if self.mjpeg.is_closed():
            self.mjpeg = mjpeg.Mjpeg("video" + str(self.file_count) + ".mjpeg")
            self.file_count += 1

    def capture_video(self):
        clock = time.clock()
        watch_dog = 0
        if self.mjpeg.is_closed():
            self.open_new_mjpeg()
        while (watch_dog < 200):
            frame = sensor.snapshot()
            clock.tick()
            self.mjpeg.add_frame(frame)
            if self.uart.any():
                line = self.uart.readline()
                print([hex(x) for x in line])
                print(line == bytes([0x56, 0x00, 0x5A]))
                if line == bytes([0x56, 0x00, 0x5A]):
                    print("respond")
                    self.uart.write(bytes([0x76, 0x00, 0x5A]))
                    watch_dog = 0
                    self.mjpeg.sync(clock.fps())
            else:
                watch_dog += 1

        print(clock.fps())
        self.mjpeg.close(clock.fps())

    def cmd_image(self, cmd):
        if cmd[0] == 0x00:
            self.uart.write(bytes([0x76, 0x00, 0x36, 0x00, 0x00]))
            print('capture image')
            self.capture_image()
            return

        if cmd[0] == 0x01:
            self.uart.write(bytes([0x76, 0x00, 0x36, 0x00, 0x01]))
            print('capture video')
            self.capture_video()
            return

        if cmd[0] == 0x03:
            self.uart.write(bytes([0x76, 0x00, 0x36, 0x00, 0x00]))
            print('close')
            self.close()
            return

        raise OSError("command corrupted -- did not recognize image command")

    def close(self):
        self.mjpeg.close(1)
        self.uart.deinit()
        self.running = False


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
            # p     p     x     x     p     p     y     y     p     p
            [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0A]
        )
        protocol.capture_video()
        protocol.close()
    except OSError as e:
        print(str(e))


init_board()

protocol = Protocol()

# testing()
# Main LOOP WOOOOOO

while (protocol.is_running()):
    try:
        protocol.command()
    except OSError as e:
        print(str(e))
