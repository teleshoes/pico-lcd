from machine import Pin,SPI,PWM
import framebuf
import time
import os

from rgb332_to_rgb565 import RGB332_TO_RGB565

BL = 13
DC = 8
RST = 12
MOSI = 11
SCK = 10
CS = 9

class LCD(framebuf.FrameBuffer):
    # mode bits
    #  0x08 RGB/BGR
    #  0x20 rotate 90 degrees
    #  0x40 mirror X
    #  0x80 mirror Y
    MODE_PX_RGB        = 0b00000000
    MODE_PX_BGR        = 0b00001000
    MODE_ORIENT_NORMAL = 0b01100000
    MODE_ORIENT_ROT90  = 0b00000000
    MODE_ORIENT_ROT180 = 0b10100000
    MODE_ORIENT_ROT270 = 0b11000000

    def INIT_PWM(brightness):
        pwm = PWM(Pin(BL))
        pwm.freq(1000)
        pwm.duty_u16(brightness) #max 65535

    def __init__(self, width, height,
                 orient=MODE_ORIENT_NORMAL, pixelOrder=MODE_PX_RGB, lowRam=False):
        self.width = width
        self.height = height
        self.orient = orient
        self.pixelOrder = pixelOrder
        self.lowRam = lowRam

        self.cs = Pin(CS,Pin.OUT)
        self.rst = Pin(RST,Pin.OUT)

        self.cs(1)
        self.spi = SPI(1)
        self.spi = SPI(1,1000_000)
        self.spi = SPI(1,100000_000,polarity=0, phase=0,sck=Pin(SCK),mosi=Pin(MOSI),miso=None)
        self.dc = Pin(DC,Pin.OUT)
        self.dc(1)

        if self.lowRam:
            #1) limit colors to RGB332 color profile, pretending to use framebuf GS8
            #2) convert chunks of the screen on the fly when writing data
            #3) cuts RAM usage by 37.5%
            #4) MUCH MUCH MUCH slower
            self.lowRamChunkCount = 8
            self.buffer = bytearray(self.height * self.width)
            self.lowRamBuffer = bytearray(int(len(self.buffer)*2/self.lowRamChunkCount))
            self.colorProfile = framebuf.GS8
        else:
            self.buffer = bytearray(self.height * self.width * 2)
            self.colorProfile = framebuf.RGB565

        super().__init__(self.buffer, self.width, self.height, self.colorProfile)

        self.init_display()

        if self.lowRam:
            #RGB332        RRRGGGBB
            self.red   = 0b11100000
            self.green = 0b00011100
            self.blue  = 0b00000011
            self.white = 0b11111111
            self.black = 0b00000000
        else:
            #RGB565        RRRRRGGG      GGGBBBBB
            self.red   = 0b11111000 | (0b00000000 << 8)
            self.green = 0b00000111 | (0b11100000 << 8)
            self.blue  = 0b00000000 | (0b00011111 << 8)
            self.white = 0b11111111 | (0b11111111 << 8)
            self.black = 0b00000000 | (0b00000000 << 8)

    def setOrient(self, orient):
        self.orient = orient
        self.write_cmd(0x36)
        self.write_data(self.orient | self.pixelOrder)

    def write_cmd(self, cmd):
        self.cs(1)
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def write_data(self, buf):
        self.cs(1)
        self.dc(1)
        self.cs(0)
        self.spi.write(bytearray([buf]))
        self.cs(1)

    def init_display(self):
        """Initialize dispaly"""
        self.rst(1)
        self.rst(0)
        self.rst(1)

        self.write_cmd(0x36)
        self.write_data(self.orient | self.pixelOrder)

        self.write_cmd(0x3A)
        self.write_data(0x05)

        self.write_cmd(0xB2)
        self.write_data(0x0C)
        self.write_data(0x0C)
        self.write_data(0x00)
        self.write_data(0x33)
        self.write_data(0x33)

        self.write_cmd(0xB7)
        self.write_data(0x35)

        self.write_cmd(0xBB)
        self.write_data(0x19)

        self.write_cmd(0xC0)
        self.write_data(0x2C)

        self.write_cmd(0xC2)
        self.write_data(0x01)

        self.write_cmd(0xC3)
        self.write_data(0x12)

        self.write_cmd(0xC4)
        self.write_data(0x20)

        self.write_cmd(0xC6)
        self.write_data(0x0F)

        self.write_cmd(0xD0)
        self.write_data(0xA4)
        self.write_data(0xA1)

        self.write_cmd(0xE0)
        self.write_data(0xD0)
        self.write_data(0x04)
        self.write_data(0x0D)
        self.write_data(0x11)
        self.write_data(0x13)
        self.write_data(0x2B)
        self.write_data(0x3F)
        self.write_data(0x54)
        self.write_data(0x4C)
        self.write_data(0x18)
        self.write_data(0x0D)
        self.write_data(0x0B)
        self.write_data(0x1F)
        self.write_data(0x23)

        self.write_cmd(0xE1)
        self.write_data(0xD0)
        self.write_data(0x04)
        self.write_data(0x0C)
        self.write_data(0x11)
        self.write_data(0x13)
        self.write_data(0x2C)
        self.write_data(0x3F)
        self.write_data(0x44)
        self.write_data(0x51)
        self.write_data(0x2F)
        self.write_data(0x1F)
        self.write_data(0x1F)
        self.write_data(0x20)
        self.write_data(0x23)

        self.write_cmd(0x21)

        self.write_cmd(0x11)

        self.write_cmd(0x29)


    def show(self):
        self.write_cmd(0x2A)
        self.write_data(0x00)
        self.write_data(0x00)
        self.write_data(int((self.width-1) >> 8))
        self.write_data(int((self.width-1) & 0xff))

        self.write_cmd(0x2B)
        self.write_data(0x00)
        self.write_data(0x00)
        self.write_data(int((self.height-1) >> 8))
        self.write_data(int((self.height-1) & 0xff))

        self.write_cmd(0x2C)

        self.cs(1)
        self.dc(1)
        self.cs(0)

        if self.lowRam:
          chunkSize = len(self.buffer) / self.lowRamChunkCount
          for chunkIdx in range(self.lowRamChunkCount):
            chunkStart = int(chunkIdx*chunkSize)
            for i in range(chunkSize):
              rgb332 = self.buffer[chunkStart + i]
              rgb565 = RGB332_TO_RGB565[rgb332]

              self.lowRamBuffer[i*2+0] = rgb565 >> 8
              self.lowRamBuffer[i*2+1] = rgb565 & 0x00ff
            self.spi.write(self.lowRamBuffer)
        else:
          self.spi.write(self.buffer)
        self.cs(1)
