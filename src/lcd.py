import machine
import st7789

import framebuf
import gc
import os
import time

BL = 13
DC = 8
RST = 12
MOSI = 11
SCK = 10
CS = 9

class LCD():
  MODE_ROTATION_NORMAL = 1
  MODE_ROTATION_ROT90  = 0
  MODE_ROTATION_ROT180 = 3
  MODE_ROTATION_ROT270 = 2

  def __init__(self, width, height, rotation):
    self.width = width
    self.height = height
    self.rotation = rotation

    self.spi = machine.SPI(1, 100000_000, polarity=0, phase=0,
      sck=machine.Pin(SCK), mosi=machine.Pin(MOSI), miso=None)

    self.dc = machine.Pin(DC, machine.Pin.OUT)
    self.cs = machine.Pin(CS, machine.Pin.OUT)
    self.backlight = machine.Pin(CS, machine.Pin.OUT)
    self.reset = machine.Pin(RST, machine.Pin.OUT)

    self.lcd = st7789.ST7789(self.spi,
      self.height, self.width, rotation=self.rotation,
      reset=self.reset, dc=self.dc, cs=self.cs, backlight=self.backlight)

    self.lcd.init()

    #something is allocating memory GC is not aware of, so be explicit
    gc.collect()

    self.colorProfile = framebuf.RGB565

    try:
      self.buffer = bytearray(self.height * self.width * 2)
      self.framebuf = framebuf.FrameBuffer(
        self.buffer, self.width, self.height, self.colorProfile)
    except:
      print("WARNING: COULD NOT ALLOCATE BUFFER, SKIPPING FRAME BUFFER\n")
      self.buffer = None
      self.framebuf = None

    if self.framebuf == None:
      self.red = st7789.RED
      self.green = st7789.GREEN
      self.blue = st7789.BLUE
      self.white = st7789.WHITE
      self.black = st7789.BLACK
    else:
      #RGB565      RRRRRGGG      GGGBBBBB
      self.red   = 0b11111000 | (0b00000000 << 8)
      self.green = 0b00000111 | (0b11100000 << 8)
      self.blue  = 0b00000000 | (0b00011111 << 8)
      self.white = 0b11111111 | (0b11111111 << 8)
      self.black = 0b00000000 | (0b00000000 << 8)

  def setRotation(self, rotation):
    self.rotation = rotation
    self.lcd.rotation(self.rotation)
    self.show()

  def fill(self, color):
    if self.framebuf == None:
      self.lcd.fill(color)
    else:
      self.framebuf.fill(color)

  def rect(self, x, y, w, h, color, fill=True):
    if self.framebuf == None:
      if fill:
        self.lcd.fill_rect(x, y, w, h, color)
      else:
        self.lcd.rect(x, y, w, h)
    else:
      self.framebuf.rect(x, y, w, h, color, fill)

  def fillShow(self, color):
    self.lcd.fill(color)

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
    self.spi.write(buf)
    self.cs(1)

  def show(self):
    if self.framebuf == None:
      #nothing to show
      pass
    else:
      self.lcd.set_window(0, 0, self.width, self.height)
      self.write_cmd(0x2C)
      self.write_data(self.buffer)
