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
  def __init__(self, landscapeWidth, landscapeHeight, rotationLayouts):
    self.lcdLandscapeWidth = landscapeWidth
    self.lcdLandscapeHeight = landscapeHeight

    self.rotationLayouts = rotationLayouts
    self.rotationIdx = 0
    self.curRotationLayout = self.rotationLayouts[self.rotationIdx]

    self.buffer = None
    self.framebuf = None
    self.fbConf = FramebufConf(enabled=False)

    try:
      #used only in framebuf, st7789 is RGB565 only
      self.framebufColorProfile = framebuf.RGB444
    except AttributeError:
      print("WARNING: framebuf compiled without RGB444")
      self.framebufColorProfile = framebuf.RGB565

    self.rotationsArr = []
    for i in range(0, len(self.rotationLayouts)):
      rot = self.rotationLayouts[i]
      rot['MADCTL'] = (0
        | rot['MY']  << 7 #0:nothing  1:mirror row address
        | rot['MX']  << 6 #0:nothing  1:mirror col address
        | rot['MV']  << 5 #0:nothing  1:swap row and col address
        | MADCTL_ML  << 4
        | MADCTL_RGB << 3
        | MADCTL_MH  << 2
      )
      if rot['LANDSCAPE']:
        (w, h) = (self.lcdLandscapeWidth, self.lcdLandscapeHeight)
      else:
        (h, w) = (self.lcdLandscapeHeight, self.lcdLandscapeWidth)
      self.rotationsArr.append((rot['MADCTL'], w, h, rot['X'], rot['Y']))

    self.spi = machine.SPI(1, 100000_000, polarity=0, phase=0,
      sck=machine.Pin(SCK), mosi=machine.Pin(MOSI), miso=None)

    self.dc = machine.Pin(DC, machine.Pin.OUT)
    self.cs = machine.Pin(CS, machine.Pin.OUT)
    self.backlight = machine.Pin(CS, machine.Pin.OUT)
    self.reset = machine.Pin(RST, machine.Pin.OUT)

    self.tft = st7789.ST7789(
      self.spi, self.lcdLandscapeHeight, self.lcdLandscapeWidth,
      rotation=self.rotationIdx, rotations=self.rotationsArr,
      reset=self.reset, dc=self.dc, cs=self.cs, backlight=self.backlight)

    self.tft.init()

    # blank entire memory, not just display size
    self.fill_mem_blank()

  def get_width(self):
    if self.curRotationLayout['LANDSCAPE']:
      return self.lcdLandscapeWidth
    else:
      return self.lcdLandscapeHeight
  def get_height(self):
    if self.curRotationLayout['LANDSCAPE']:
      return self.lcdLandscapeHeight
    else:
      return self.lcdLandscapeWidth

  def get_target_window_size(self):
    if self.is_framebuf_enabled():
      (winX, winY) = self.get_framebuf_size()
    else:
      (winX, winY) = (self.get_width(), self.get_height())
    return (winX, winY)

  def is_framebuf_enabled(self):
    return self.fbConf.enabled

  def get_framebuf_conf(self):
    return self.fbConf
  def set_framebuf_conf(self, fbConf):
    if fbConf == None:
      self.fbConf = FramebufConf(enabled=False)
    else:
      self.fbConf = fbConf

    if not self.is_framebuf_enabled():
      self.buffer = None
    else:
      self.create_buffer()

    self.init_framebuf()

  def get_framebuf_size(self):
    bufW = self.get_width()
    bufH = self.get_height()
    if not self.fbConf.enabled:
      return (bufW, bufH)

    (fbW, fbH) = (self.fbConf.fbW, self.fbConf.fbH)

    if bufW < bufH:
      (fbW, fbH) = (fbH, fbW)

    if bufW > fbW:
      bufW = fbW
    if bufH > fbH:
      bufH = fbH
    return (bufW, bufH)

  def get_framebuf_offset(self):
    bufW = self.get_width()
    bufH = self.get_height()
    (fbX, fbY) = (self.fbConf.fbX, self.fbConf.fbY)

    if bufW < bufH:
      (fbX, fbY) = (fbY, fbX)

    return (fbX, fbY)

  def is_landscape(self):
    return self.get_width() >= self.get_height()

  def create_buffer(self):
    (bufW, bufH) = self.get_framebuf_size()
    framebufSizeBytes = bufW * bufH * self.bits_per_px() // 8

    if self.buffer == None or len(self.buffer) != framebufSizeBytes:
      self.framebuf = None
      self.buffer = None
      gc.collect()

      try:
        self.buffer = bytearray(framebufSizeBytes)
      except Exception as e:
        print(str(e))
        print("WARNING: COULD NOT ALLOCATE BUFFER, DISABLING FRAMEBUF\n")
        self.set_framebuf_conf(None)

  def init_framebuf(self):
    if self.buffer != None:
      (bufW, bufH) = self.get_framebuf_size()
      self.framebuf = framebuf.FrameBuffer(
        self.buffer, bufW, bufH, self.framebufColorProfile)

      self.set_window_to_framebuf()
    else:
      self.framebuf = None

    self.init_colors()

  def init_colors(self):
    if not self.is_framebuf_enabled():
      #RGB565
      self.set_lcd_RGB565()
      self.red   = st7789.RED
      self.green = st7789.GREEN
      self.blue  = st7789.BLUE
      self.white = st7789.WHITE
      self.black = st7789.BLACK
    elif self.framebufColorProfile == framebuf.RGB565:
      #RGB565 (byte order swapped st7789 vs framebuf)
      self.set_lcd_RGB565()
      self.red   = self.swap_hi_lo_byte_order(st7789.RED)
      self.green = self.swap_hi_lo_byte_order(st7789.GREEN)
      self.blue  = self.swap_hi_lo_byte_order(st7789.BLUE)
      self.white = self.swap_hi_lo_byte_order(st7789.WHITE)
      self.black = self.swap_hi_lo_byte_order(st7789.BLACK)
    elif self.framebufColorProfile == framebuf.RGB444:
      #RGB444
      self.set_lcd_RGB444()
      self.red   = 0b111100000000
      self.green = 0b000011110000
      self.blue  = 0b000000001111
      self.white = 0b111111111111
      self.black = 0b000000000000

  def bits_per_px(self):
    if not self.is_framebuf_enabled():
      return 16 #RGB565
    elif self.framebufColorProfile == framebuf.RGB565:
      return 16 #RGB565
    elif self.framebufColorProfile == framebuf.RGB444:
      return 12 #RGB444
    else:
      return None

  def set_lcd_RGB565(self):
      self.write_cmd(0x3a)
      self.write_data(bytearray([0x05]))
  def set_lcd_RGB444(self):
      self.write_cmd(0x3a)
      self.write_data(bytearray([0x03]))


  def get_color_by_name(self, colorName):
    if colorName == "red":
      return self.red
    elif colorName == "green":
      return self.green
    elif colorName == "blue":
      return self.blue
    elif colorName == "white":
      return self.white
    elif colorName == "black":
      return self.black
    else:
      return None

  def swap_hi_lo_byte_order(self, h):
    bHi = h >> 8
    bLo = h & 0xff
    return (bLo << 8) | (bHi & 0xff)

  def get_rotation_degrees(self):
    return self.curRotationLayout['DEG']

  def set_rotation_degrees(self, degrees):
    for rotationIdx in range(0, len(self.rotationLayouts)):
      if self.rotationLayouts[rotationIdx]['DEG'] == degrees:
        self.set_rotation_index(rotationIdx)
        break

  def set_rotation_next(self):
    self.set_rotation_index((self.rotationIdx + 1) % len(self.rotationLayouts))

  def set_rotation_index(self, rotationIdx):
    wasLandscape = self.is_landscape()
    self.rotationIdx = rotationIdx
    self.curRotationLayout = self.rotationLayouts[rotationIdx]
    self.tft.rotation(self.rotationIdx)

    (lcdW, lcdH) = (self.get_width(), self.get_height())
    if lcdW < lcdH:
      (lcdW, lcdH) = (lcdH, lcdW)

    # if framebuf is not the entire screen, blank the entire screen
    if not self.fbConf.enabled or self.fbConf.fbW != lcdW or self.fbConf.fbH != lcdH:
      self.fill_mem_blank()

    if wasLandscape != self.is_landscape() and self.buffer != None:
      # if framebuf is not a square, transpose row/col count (cut off right or bottom)
      (bufW, bufH) = self.get_framebuf_size()
      if bufW != bufH:
        if bufW % 2 == 1 or bufH % 2 == 1:
          # skip transpose of odd-width or odd-height framebuffers
          self.fill(0)
        else:
          self.transposeBufferRowColCount()

    self.init_framebuf()
    self.show()

  # transpose row count and column count, blanking the cut-off region
  #   e.g.:
  #     2x4 to 4x2 (chop off bottom px 5,6,7,8)
  #     [1, 2, 3, 4, 5, 6, 7, 8] => [1, 2, 0, 0, 3, 4, 0, 0]
  #        _____    _________
  #        |1 2|    |1 2    |
  #        |3 4| => |3 4    |
  #        |5 6|    ---------
  #        |7 8|
  #        -----
  #
  #     4x2 to 2x4 (chop off right px 3,4,7,8)
  #     [1, 2, 3, 4, 5, 6, 7, 8] => [1, 2, 5, 6, 0, 0, 0, 0]
  #        _________     _____
  #        |1 2 3 4|     |1 2|
  #        |5 6 7 8|  => |5 6|
  #        ---------     |   |
  #                      |   |
  #                      -----
  #  (python => viper yields 26x faster performance, 1624ms => 62ms)
  @micropython.viper
  def transposeBufferRowColCount(self):
    buf = ptr8(self.buffer)
    (bufWObj, bufHObj) = self.get_framebuf_size()
    bufW = int(bufWObj)
    bufH = int(bufHObj)
    bitsPerPx = int(self.bits_per_px())

    bytesPer2Px = 2*bitsPerPx // 8 # 2px = 4 bytes for RGB565, 3 bytes for RGB444

    diff = bufW - bufH
    if diff < 0:
      diff = 0 - diff
    bufferSize = bufW * bufH * bitsPerPx // 8
    if bufW >= bufH:
      #was portrait, now landscape, chop off pixels on the bottom
      for y in range(0, bufH):
        y = bufH - y - 1 #reversed(range())
        for x in range(0, bufW, 2): #even X only, 2px at a time
          x = bufW - x - 2 #reversed(range())
          pxIdx1 = y*bufW + x
          pxIdx2 = pxIdx1 - (pxIdx1 // bufW)*diff

          bIdx1 = pxIdx1*bitsPerPx//8
          bIdx2 = pxIdx2*bitsPerPx//8

          #copy 2 pixels, x and x+1
          for i in range(0, bytesPer2Px):
            if x >= bufH:
              #old y (aka x) is outside of new height
              buf[bIdx1 + i] = 0
            else:
              buf[bIdx1 + i] = buf[bIdx2 + i]
    else:
      #was landscape, now portrait, chop off pixels on the right
      for y in range(0, bufH):
        for x in range(0, bufW, 2): #even X only, 2px at a time
          pxIdx1 = y*bufW + x
          pxIdx2 = pxIdx1 + (pxIdx1 // bufW)*diff

          bIdx1 = pxIdx1*bitsPerPx//8
          bIdx2 = pxIdx2*bitsPerPx//8

          #copy 2 pixels, x and x+1
          for i in range(0, bytesPer2Px):
            if y >= bufW:
              #old x (aka y) is outside of new width
              buf[bIdx1 + i] = 0
            else:
              buf[bIdx1 + i] = buf[bIdx2 + i]

  def fill(self, color):
    if not self.is_framebuf_enabled():
      self.tft.fill(color)
    else:
      self.framebuf.fill(color)

  def rect(self, x, y, w, h, color, fill=True):
    if not self.is_framebuf_enabled():
      if fill:
        self.tft.fill_rect(x, y, w, h, color)
      else:
        self.tft.rect(x, y, w, h, color)
    else:
      self.framebuf.rect(x, y, w, h, color, fill)

  def fill_rect(self, x, y, w, h, color):
    self.rect(x, y, w, h, color, True)

  def pixel(self, x, y, color):
    if not self.is_framebuf_enabled():
      self.tft.pixel(x, y, color)
    else:
      self.framebuf.pixel(x, y, color)

  def hline(self, x, y, w, c):
    if not self.is_framebuf_enabled():
      self.tft.hline(x, y, w, c)
    else:
      self.framebuf.hline(x, y, w, c)

  def vline(self, x, y, w, c):
    if not self.is_framebuf_enabled():
      self.tft.vline(x, y, w, c)
    else:
      self.framebuf.vline(x, y, w, c)

  def line(self, x1, y1, x2, y2, c):
    if not self.is_framebuf_enabled():
      self.tft.line(x1, y1, x2, y2, c)
    else:
      self.framebuf.line(x1, y1, x2, y2, c)

  def circle(self, centerX, centerY, radius, color, fill=True, quadrantMask=0b1111):
    self.ellipse(centerX, centerY, radius, radius, color, fill, quadrantMask)

  def ellipse(self, centerX, centerY, radiusX, radiusY, color, fill=True, quadrantMask=0b1111):
    if self.is_framebuf_enabled():
      self.framebuf.ellipse(centerX, centerY, radiusX, radiusY, color, fill, quadrantMask)
      return

    #adapted from micropython mod_framebuf.c
    two_xrsq = 2 * radiusX * radiusX
    two_yrsq = 2 * radiusY * radiusY

    #first set of points, y' > -1
    curX = radiusX
    curY = 0
    xchange = radiusY * radiusY * (1 - 2 * radiusX)
    ychange = radiusX * radiusX
    ellipse_error = 0
    stoppingx = two_yrsq * radiusX
    stoppingy = 0
    while stoppingx >= stoppingy:
      self.draw_ellipse_points(centerX, centerY, curX, curY, color, fill, quadrantMask)
      curY += 1
      stoppingy += two_xrsq
      ellipse_error += ychange
      ychange += two_xrsq
      if 2 * ellipse_error + xchange > 0:
        curX -= 1
        stoppingx -= two_yrsq
        ellipse_error += xchange
        xchange += two_yrsq

    #second set of points, y' < -1
    curX = 0
    curY = radiusY
    xchange = radiusY * radiusY
    ychange = radiusX * radiusX * (1 - 2 * radiusY)
    ellipse_error = 0
    stoppingx = 0
    stoppingy = two_xrsq * radiusY
    while stoppingx <= stoppingy:
      self.draw_ellipse_points(centerX, centerY, curX, curY, color, fill, quadrantMask)
      curX += 1
      stoppingx += two_yrsq
      ellipse_error += xchange
      xchange += two_yrsq
      if 2 * ellipse_error + ychange > 0:
        curY -= 1
        stoppingy -= two_xrsq
        ellipse_error += ychange
        ychange += two_xrsq

  def draw_ellipse_points(self, centerX, centerY, x, y, color, fill, quadrantMask):
    #adapted from micropython mod_framebuf.c
    q1 = 0b0001 & quadrantMask
    q2 = 0b0010 & quadrantMask
    q3 = 0b0100 & quadrantMask
    q4 = 0b1000 & quadrantMask
    if q1 and fill:
      self.fill_rect(centerX, centerY - y, x + 1, 1, color)
    if q2 and fill:
      self.fill_rect(centerX - x, centerY - y, x + 1, 1, color)
    if q3 and fill:
      self.fill_rect(centerX - x, centerY + y, x + 1, 1, color)
    if q4 and fill:
      self.fill_rect(centerX, centerY + y, x + 1, 1, color)

    if q1 and not fill:
      self.pixel(centerX + x, centerY - y, color)
    if q2 and not fill:
      self.pixel(centerX - x, centerY - y, color)
    if q3 and not fill:
      self.pixel(centerX - x, centerY + y, color)
    if q4 and not fill:
      self.pixel(centerX + x, centerY + y, color)

  # coords is an even-sized flat array of points describing closed, convex polygon
  #       e.g.: array('h', [x0, y0, x1, y1...])
  # NOTE:
  #   fill=True is implemented only WITH framebuf
  #   rotateRad/rotateCX/rotateCY is implemented only WITHOUT framebuf
  def poly(self, coords, x, y, color, fill=False, rotateRad=0, rotateCX=0, rotateCY=0):
    if not self.is_framebuf_enabled():
      if fill:
        print("WARNING: 'fill' is not implemented in poly() for st7789_mpy")
      polygonXYPairs = []
      for i in range(0, len(coords), 2):
        polygonXYPairs.append((coords[i], coords[i+1]))

      self.tft.polygon(polygonXYPairs, x, y, color, rotateRad, rotateCX, rotateCY)
    else:
      if rotateRad != 0:
        print("WARNING: 'rotateRad' is not implemented in poly() for framebuf")
      self.framebuf.poly(x, y, coords, color, fill)

  def fill_show(self, color):
    self.fill(color)
    self.show()

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

  def fill_mem_blank(self):
    numberOfChunks = 256
    memWidth = 320
    memHeight = 320

    self.set_window(0, memWidth, 0, memHeight)
    self.write_cmd(0x2C)

    buf = bytearray(memWidth*memHeight*self.bits_per_px()//8 // numberOfChunks)
    for i in range(0, numberOfChunks):
      self.write_data(buf)
    buf = None

    if self.is_framebuf_enabled():
      self.set_window_to_framebuf()

  def set_window_to_framebuf(self):
    (bufW, bufH) = self.get_framebuf_size()
    (fbX, fbY) = self.get_framebuf_offset()
    self.set_window_with_rotation_offset(fbX, fbY, bufW, bufH)

  def set_window_with_rotation_offset(self, x, y, w, h):
    xStart = self.curRotationLayout['X'] + x
    xEnd = w + self.curRotationLayout['X'] + x - 1
    yStart = self.curRotationLayout['Y'] + y
    yEnd = h + self.curRotationLayout['Y'] + y - 1

    self.set_window(xStart, xEnd, yStart, yEnd)

  def set_window(self, xStart, xEnd, yStart, yEnd):
    self.write_cmd(0x2A)
    self.write_data(bytearray([xStart >> 8, xStart & 0xff, xEnd >> 8, xEnd & 0xff]))

    self.write_cmd(0x2B)
    self.write_data(bytearray([yStart >> 8, yStart & 0xff, yEnd >> 8, yEnd & 0xff]))

  def show(self):
    if self.is_framebuf_enabled():
      self.write_cmd(0x2C)
      self.write_data(self.buffer)


class FramebufConf():
  def __init__(self, enabled=False, fbW=0, fbH=0, fbX=0, fbY=0):
    self.enabled = enabled
    self.fbW = fbW
    self.fbH = fbH
    self.fbX = fbX
    self.fbY = fbY

  @classmethod
  def parseFramebufConfStr(cls, fbConfStr):
    if fbConfStr == None:
      return None

    fbConf = None
    fbConfStr = fbConfStr.lower()
    if fbConfStr == "off" or fbConfStr == "disabled" or fbConfStr == "false":
      fbConf = None
    else:
      nums = []
      curNum = ""
      for c in fbConfStr:
        if c.isdigit():
          curNum += c
        elif (len(nums) == 0 and c == "x") or (len(nums) > 0 and c == "+"):
          if len(curNum) == 0:
            return None
          nums.append(int(curNum))
          curNum = ""
      if len(curNum) > 0:
        nums.append(int(curNum))

      if len(nums) == 2:
        fbConf = FramebufConf(enabled=True, fbW=nums[0], fbH=nums[1], fbX=0, fbY=0)
      elif len(nums) == 4:
        fbConf = FramebufConf(enabled=True, fbW=nums[0], fbH=nums[1], fbX=nums[2], fbY=nums[3])
      else:
        fbConf = None

    if fbConf == None:
      fbConf = FramebufConf(enabled=False)

    return fbConf

  def __str__(self) -> str:
    return self.format()

  def format(self):
    if not self.enabled:
      return "off"
    elif self.fbX == 0 and self.fbY == 0:
      return '%dx%d' % (self.fbW, self.fbH)
    else:
      return '%dx%d+%d+%d' % (self.fbW, self.fbH, self.fbX, self.fbY)
