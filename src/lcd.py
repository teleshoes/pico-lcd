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

MADCTL_ML  = 0 #0:refresh-top-to-bottom  1:refresh-bottom-to-top
MADCTL_MH  = 0 #0:refresh-left-to-right  1:refresh-right-to-left
MADCTL_RGB = 0 #0:RGB                    1:BGR

class LCD():
  def __init__(self, conf):
    self.conf = conf
    self.rotationIdx = 0
    self.rotCfg = self.conf[self.rotationIdx]

    self.rotationsArr = []
    for i in range(0, len(self.conf)):
      rot = self.conf[i]
      rot['MADCTL'] = (0
        | rot['MY']  << 7 #0:nothing  1:mirror row address
        | rot['MX']  << 6 #0:nothing  1:mirror col address
        | rot['MV']  << 5 #0:nothing  1:swap row and col address
        | MADCTL_ML  << 4
        | MADCTL_RGB << 3
        | MADCTL_MH  << 2
      )
      self.rotationsArr.append((rot['MADCTL'], rot['W'], rot['H'], rot['X'], rot['Y']))

    self.spi = machine.SPI(1, 100000_000, polarity=0, phase=0,
      sck=machine.Pin(SCK), mosi=machine.Pin(MOSI), miso=None)

    self.dc = machine.Pin(DC, machine.Pin.OUT)
    self.cs = machine.Pin(CS, machine.Pin.OUT)
    self.backlight = machine.Pin(CS, machine.Pin.OUT)
    self.reset = machine.Pin(RST, machine.Pin.OUT)

    self.lcd = st7789.ST7789(
      self.spi, self.rotCfg['H'], self.rotCfg['W'],
      rotation=self.rotationIdx, rotations=self.rotationsArr,
      reset=self.reset, dc=self.dc, cs=self.cs, backlight=self.backlight)

    self.lcd.init()

    self.initFramebufMaybe()

  def initFramebufMaybe(self):
    try:
      self.buffer = None
      self.framebuf = None

      gc.collect()

      self.buffer = bytearray(self.rotCfg['W'] * self.rotCfg['H'] * 2)
      self.framebuf = framebuf.FrameBuffer(
        self.buffer, self.rotCfg['W'], self.rotCfg['H'], framebuf.RGB565)
    except:
      print("WARNING: COULD NOT ALLOCATE BUFFER, SKIPPING FRAME BUFFER\n")
      self.buffer = None
      self.framebuf = None

    if self.framebuf != None:
      self.set_full_window()

    self.initColors()

  def initColors(self):
    if self.framebuf == None:
      #RGB565
      self.red   = st7789.RED
      self.green = st7789.GREEN
      self.blue  = st7789.BLUE
      self.white = st7789.WHITE
      self.black = st7789.BLACK
    else:
      #byte order swapped in framebuf
      self.red   = self.swapHiLoByteOrder(st7789.RED)
      self.green = self.swapHiLoByteOrder(st7789.GREEN)
      self.blue  = self.swapHiLoByteOrder(st7789.BLUE)
      self.white = self.swapHiLoByteOrder(st7789.WHITE)
      self.black = self.swapHiLoByteOrder(st7789.BLACK)

  def swapHiLoByteOrder(self, h):
    bHi = h >> 8
    bLo = h & 0xff
    return (bLo << 8) | (bHi & 0xff)

  def setRotationDegrees(self, degrees):
    for rotationIdx in range(0, len(self.conf)):
      if self.conf[rotationIdx]['DEG'] == degrees:
        self.setRotationIdx(rotationIdx)
        break

  def setRotationIdx(self, rotationIdx):
    (oldW, oldH) = (self.rotCfg['W'], self.rotCfg['H'])
    self.rotationIdx = rotationIdx
    self.rotCfg = self.conf[rotationIdx]
    self.lcd.rotation(self.rotationIdx)
    (newW, newH) = (self.rotCfg['W'], self.rotCfg['H'])

    if self.framebuf != None and (oldW != newW or oldH != newH):
      self.initFramebufMaybe()

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
        self.lcd.rect(x, y, w, h, color)
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

  def write_data(self, data):
    self.cs(1)
    self.dc(1)
    self.cs(0)
    self.spi.write(data)
    self.cs(1)

  def set_full_window(self):
    xStart = self.rotCfg['X']
    xEnd = self.rotCfg['W'] + self.rotCfg['X']
    yStart = self.rotCfg['Y']
    yEnd = self.rotCfg['H'] + self.rotCfg['Y']

    self.write_cmd(0x2A)
    self.write_data(bytearray([xStart >> 8, xStart & 0xff, xEnd >> 8, xEnd & 0xff]))

    self.write_cmd(0x2B)
    self.write_data(bytearray([yStart >> 8, yStart & 0xff, yEnd >> 8, yEnd & 0xff]))

  def show(self):
    if self.framebuf != None:
      self.write_cmd(0x2C)
      self.write_data(self.buffer)
