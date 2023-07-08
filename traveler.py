# hacking prototype - By: justin - Fri Mar 10 2023

import sensor
import mjpeg
import time
from pyb import UART


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


'''
    def set_sensor_mode(self, cmd):
        if cmd[0] == 0:
            self.setup_sensor(sensor.RGB565)
        elif cmd[0] == 1:
            self.setup_sensor(sensor.GRAYSCALE)

    def capture_image(self):
        image = sensor.snapshot()
        self.mjpeg.add_frame(image)
        if self.resolution == Protocol.VGA:
            image.scale(x_size=640, y_size=480)
        elif self.resolution == Protocol.QVGA:
            image.scale(x_size=320, y_size=240)
        elif self.resolution == Protocol.QQVGA:
            image.scale(x_size=160, y_size=120)

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
                if line == bytes([0x56, 0x00, 0x5A]):
                    self.uart.write(bytes([0x76, 0x00, 0x5A]))
                    watch_dog = 0
                    self.mjpeg.sync(clock.fps())
            else:
                watch_dog += 1

        self.mjpeg.close(clock.fps())

    def close(self):
        self.mjpeg.close(1)
        self.uart.deinit()
        self.running = False
'''


class CommandProcessor():
    def __init__(self, cameraHandler: CameraHandler):
        self.camera_handler = cameraHandler
        self.current_state = 'start'
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
                return ''

            self.process_command(cmd[2:], state)
        except KeyError:
            return 'Invalid State'

    def reset(self, cmd):
        pass

    def tx_data_len(self, cmd: list[int]) -> str:
        return 'end'

    def tx_image_data(self, cmd):
        start_address = (cmd[4] << 8) + cmd[5]
        data_length = (cmd[8] << 8) + cmd[9]
        print(cmd)
        print(start_address)
        print(data_length)

    def set_resolution(self, cmd):
        print(cmd)
        resolution = 0
        if cmd[0] == 0x00:
            resolution = CameraHandler.VGA
        elif cmd[0] == 0x11:
            resolution = CameraHandler.QVGA
        elif cmd[0] == 0x22:
            resolution = CameraHandler.QQVGA

        self.camera_handler.set_image_resolution(resolution)

    def set_color_mode(self, cmd):
        print(cmd)
        mode = sensor.RGB565
        if cmd[0] == 0x01:
            mode = sensor.GRAYSCALE

        self.camera_handler.setup_sensor(mode)

    def set_rtc(self, cmd):
        return 'end'

    def capture_image(self, cmd):
        return 'end'

    def capture_video(self, cmd):
        return 'end'


'''
class Protocol():
    def __init__(self, camera_handler, command_processor):
        self.command_processor = command_processor
        self.camera_handler = camera_handler

        self.uart = UART(3, 115200, timeout=150, timeout_char=150)
        self.uart.write("start up\n")
        self.start_byte = 0
        self.length_to_read = -1
        self.running = True
        self.file_count = 0
        try:
            self.mjpeg = mjpeg.Mjpeg("video0.mjpeg")
        except TypeError as e:
            print(str(e))

        # self.open_new_mjpeg()

    def is_running(self):
        return self.running

    def send_photo(self, image):
        compressed_image = image.compress(
            quality=Protocol.IMAGE_COMPRESSION_QUALITY
        )
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
        image_size = sensor.get_fb().compress(
            quality=Protocol.IMAGE_COMPRESSION_QUALITY
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

    def command(self):
        cmd = self.uart.read()
        if cmd is not None:
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
        elif cmd[0] == 0x31 and cmd[1] == 0x05:
            self.set_image_resolution(cmd[2:])
        elif cmd[0] == 0x30 and cmd[1] == 0x04:
            self.set_sensor_mode(cmd[2:])
        else:
            print([hex(x) for x in cmd])
            raise OSError("command corrupted did not recognize command prefix")

    def command_read_image_data(self, cmd):
        if len(cmd) < 9:
            raise OSError(
                "command corrupted - command length too short for image data"
            )
        self.start_byte = cmd[4] << 8 | cmd[5]
        self.length_to_read = cmd[8] << 8 | cmd[9]

        if self.length_to_read == 0:
            self.length_to_read = -1

        self.send_photo(sensor.get_fb())

    def open_new_mjpeg(self):
        if self.mjpeg is None or self.mjpeg.is_closed():
            self.mjpeg = mjpeg.Mjpeg("video" + str(self.file_count) + ".mjpeg")
            self.file_count += 1

    def cmd_image(self, cmd):
        if cmd[0] == 0x00:
            self.uart.write(bytes([0x76, 0x00, 0x36, 0x00, 0x00]))
            self.capture_image()
            return

        if cmd[0] == 0x01:
            self.uart.write(bytes([0x76, 0x00, 0x36, 0x00, 0x01]))
            self.capture_video()
            return

        if cmd[0] == 0x03:
            self.uart.write(bytes([0x76, 0x00, 0x36, 0x00, 0x00]))
            self.close()
            return

        raise OSError("command corrupted -- did not recognize image command")
'''

# protocol = Protocol()

cameraHandler = CameraHandler()

commandProcessor = CommandProcessor(cameraHandler)


def testing():
    '''
    cmd = [0x56, 0x00, 0x26, 0x00]
    commandProcessor.process_command(cmd)

    cmd = [0x56, 0x00, 0x32, 0x0C, 0x00, 0x0A, 0x00, 0x00, 0x12, 0x34, 0x00, 0x00, 0x56, 0x78, 0x00, 0x0A]
    commandProcessor.process_command(cmd)
    '''

    # set color mode
    cmd = [0x56, 0x00, 0x30, 0x04, 0x00]
    commandProcessor.process_command(cmd)

    # capture image
    cmd = [0x56, 0x00, 0x36, 0x01, 0x00, 0x05]
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
