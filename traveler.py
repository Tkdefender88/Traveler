# hacking prototype - By: justin - Fri Mar 10 2023

import sensor
import mjpeg
import time
import pyb
from pyb import UART
from pyb import RTC
import os


rtc = RTC()


class CameraHandler():
    VGA = 0
    QVGA = 1
    QQVGA = 2
    IMAGE_COMPRESSION_QUALITY = 50

    def __init__(self):
        self.set_image_resolution(CameraHandler.VGA)
        self.setup_sensor(sensor.RGB565)

    def setup_sensor(self, mode):
        sensor.reset()
        sensor.set_pixformat(mode)
        sensor.set_framesize(sensor.FHD)
        sensor.skip_frames(time=2000)

    def set_image_resolution(self, resolution):
        if resolution in [
            CameraHandler.VGA,
            CameraHandler.QVGA,
            CameraHandler.QQVGA
        ]:
            self.resolution = resolution
        else:
            raise OSError("resolution not recognized")

    def capture_image(self):
        image = sensor.snapshot()
        now = rtc.datetime()
        folder = "{year}-{month}-{day}".format(
            year=now[0],
            month=now[1],
            day=now[2],
        )
        try:
            os.stat(folder)
        except OSError:
            os.mkdir(folder)
        finally:
            os.chdir(folder)

        filename = "{hour}-{minute}-{second}-{subsecond}.jpeg".format(
             hour=now[4],
             minute=now[5],
             second=now[6],
             subsecond=now[7]
        )

        print(filename)

        image.save(filename)
        os.chdir('..')
        self.__scale_image(image)

    def __scale_image(self, image):
        if self.resolution == CameraHandler.VGA:
            image.scale(x_size=640, y_size=480)
        elif self.resolution == CameraHandler.QVGA:
            image.scale(x_size=320, y_size=240)
        elif self.resolution == CameraHandler.QQVGA:
            image.scale(x_size=160, y_size=120)

    def compress_frame_buffer(self):
        image = sensor.get_fb().compress(
            quality=CameraHandler.IMAGE_COMPRESSION_QUALITY
        )
        return image

    def begin_video_capture(self, uart):
        clock = time.clock()

        now = rtc.datetime()

        folder = "{year}-{month}-{day}".format(
            year=now[0],
            month=now[1],
            day=now[2],
        )

        try:
            os.stat(folder)
        except OSError:
            os.mkdir(folder)
        finally:
            os.chdir(folder)

        file_name = "{hour}-{minute}-{second}.mjpeg".format(
            hour=now[4],
            minute=now[5],
            second=now[6]
        )

        print(file_name)
        video_buffer = mjpeg.Mjpeg(file_name)

        frames = 200

        while (frames > 0):
            frames -= 1
            clock.tick()
            frame = sensor.snapshot()
            video_buffer.add_frame(frame)
            print(clock.fps())
            if uart.any():
                line = uart.readline()
                if line == bytes([0x56, 0x00, 0x5A]):
                    frames = 200
                    uart.write(bytes([0x76, 0x00, 0x5A]))
                    video_buffer.sync(clock.fps())
                else:
                    uart.write(bytes([0x76, 0x00, 0x12, 0x34]))
                    frames = 0

        # close the file
        video_buffer.close(clock.fps())


class CommandProcessor():
    def __init__(self, cameraHandler: CameraHandler):
        self.camera_handler = cameraHandler
        self.current_state = 'start'
        self.uart = self.uart = UART(3, 115200, timeout=150, timeout_char=150)
        self.fsm = {
            ('start',   (0x56, 0x00)): (lambda _: 'command'),
            ('command', (0x26, 0x00)): self.reset,
            ('command', (0x36, 0x01)): (lambda _: 'capture'),
            ('command', (0x34, 0x01)): self.tx_data_len,
            ('command', (0x32, 0x0C)): self.tx_image_data,
            ('command', (0x31, 0x05)): self.set_resolution,
            ('command', (0x30, 0x04)): self.set_color_mode,
            ('command', (0x29, 0x05)): self.set_rtc,
            ('capture', (0x00, 0x05)): self.capture_image,
            ('capture', (0x00, 0x0C)): self.capture_video
        }

    def process_command(self, cmd: list[int], state: str = 'start') -> str:
        """ recursive """
        token = tuple(cmd[0:2])
        print(token)
        try:
            print((state, token))
            fn = self.fsm[(state, token)]
            state = fn(cmd[2:])

            # base case
            if state is None:
                return 'Success'

            self.process_command(cmd[2:], state)
        except KeyError:
            self.uart.write(bytes([0x76, 0x00, 0xEE]))
            return 'Invalid State'

    def reset(self, cmd: list[int]):
        self.uart.write(bytes([0x76, 0x00, 0x26, 0x00]))
        pyb.hard_reset()

    def tx_data_len(self, cmd: list[int]):
        image_size = sensor.get_fb().compress(
            quality=CameraHandler.IMAGE_COMPRESSION_QUALITY
        ).size()
        self.uart.write(bytes([0x76, 0x00, 0x34, 0x00, 0x04, 0x00, 0x00]))
        self.uart.write(
                bytes(
                    [(image_size >> 24) & 0xff,
                     (image_size >> 16) & 0xff,
                     (image_size >> 8) & 0xff,
                     (image_size & 0xff)]
                )
            )
        pass

    def tx_image_data(self, cmd):
        start_address = (cmd[4] << 8) + cmd[5]
        data_length = (cmd[8] << 8) + cmd[9]
        image = self.camera_handler.compress_frame_buffer()
        image_size = image.size()

        if start_address > image_size:
            start_address = image_size

        if data_length == 0:
            data_length = image_size

        self.uart.write(bytes([0x76, 0x00, 0x32, 0x00, 0x00, 0xFF, 0xD8]))
        self.uart.write(image.bytearray()[start_address:data_length])
        self.uart.write(bytes([0xFF, 0xD9, 0x76, 0x00, 0x32, 0x00, 0x00,]))

    def set_resolution(self, cmd):
        resolution = 0
        if cmd[0] == 0x00:
            resolution = CameraHandler.VGA
        elif cmd[0] == 0x11:
            resolution = CameraHandler.QVGA
        elif cmd[0] == 0x22:
            resolution = CameraHandler.QQVGA

        self.uart.write(bytes([0x76, 0x00, 0x31, 0x00, 0x00]))
        self.camera_handler.set_image_resolution(resolution)

    def set_color_mode(self, cmd):
        mode = sensor.RGB565
        if cmd[0] == 0x01:
            mode = sensor.GRAYSCALE
        self.uart.write(bytes([0x76, 0x00, 0x30, 0x00, 0x00]))
        self.camera_handler.setup_sensor(mode)

    def set_rtc(self, cmd):
        if not len(cmd) == 7:
            self.uart.write(bytes([0x76, 0x00, 0x29, 0xFF]))
            return 'error'
        date_time = (
            (cmd[0] << 8) + cmd[1],
            cmd[2],
            cmd[3],
            1,
            cmd[4],
            cmd[5],
            cmd[6],
            0
        )
        print(date_time)
        self.uart.write(bytes([0x76, 0x00, 0x29, 0x00]))
        rtc.datetime(date_time)

    def capture_image(self, cmd):
        self.uart.write(bytes([0x76, 0x00, 0x36, 0x01, 0x00, 0x05]))
        self.camera_handler.capture_image()

    def capture_video(self, cmd):
        self.uart.write(bytes([0x76, 0x00, 0x36, 0x01, 0x00, 0x00]))
        self.camera_handler.begin_video_capture(self.uart)


cameraHandler = CameraHandler()

commandProcessor = CommandProcessor(cameraHandler)


def testing():
    '''
    cmd = [0x56, 0x00, 0x26, 0x00]
    commandProcessor.process_command(cmd)

    '''
    cmd = [0x56, 0x00, 0x29, 0x05, 0x07, 0xE7, 0x07, 0x0E, 0x05, 0x02, 0x00]
    commandProcessor.process_command(cmd)

    cmd = [0x56, 0x00, 0x32, 0x0C, 0x00, 0x0A, 0x00, 0x00,
           0x12, 0x34, 0x00, 0x00, 0x56, 0x78, 0x00, 0x0A]
    commandProcessor.process_command(cmd)

    # set color mode
    cmd = [0x56, 0x00, 0x30, 0x04, 0x00]
    commandProcessor.process_command(cmd)

    # capture image
    cmd = [0x56, 0x00, 0x36, 0x01, 0x00, 0x05]
    commandProcessor.process_command(cmd)

    # capture image
    cmd = [0x56, 0x00, 0x36, 0x01, 0x00, 0x05]
    commandProcessor.process_command(cmd)

    # capture video
    cmd = [0x56, 0x00, 0x36, 0x01, 0x00, 0x0C]
    commandProcessor.process_command(cmd)


testing()

# Main LOOP WOOOOOO
'''
while (protocol.is_running()):
    try:
        protocol.command()
    except OSError as e:
        print(str(e))
'''
