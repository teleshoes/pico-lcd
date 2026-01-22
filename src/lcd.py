import machine
import st7789

import framebuf
import gc
import os
import time

#pins = {'BL':13, 'DC':8, 'RST':15, 'MOSI':11, 'SCK':10, 'CS':9}

MADCTL_ML  = 0 #0:refresh-top-to-bottom  1:refresh-bottom-to-top
MADCTL_MH  = 0 #0:refresh-left-to-right  1:refresh-right-to-left
MADCTL_RGB = 0 #0:RGB                    1:BGR

COLOR_PROFILE_RGB565 = "RGB565"
COLOR_PROFILE_RGB444 = "RGB444"

class LCD():
  def __init__(self, pins, landscapeWidth, landscapeHeight, rotationLayouts):
    self.pins = pins
    self.lcdLandscapeWidth = landscapeWidth
    self.lcdLandscapeHeight = landscapeHeight

    self.rotationLayouts = rotationLayouts
    self.curRotationIdx = 0
    self.curRotationLayout = self.rotationLayouts[self.curRotationIdx]

    self.buffer = None
    self.framebuf = None
    self.fbConf = FramebufConf(enabled=False)
    self.isWindowSetToFramebuf = False

    self.colorProfile = None
    self.isColorProfileBigEndian = True

    try:
      #used only in framebuf, st7789 is RGB565 only
      self.framebufColorProfile = framebuf.RGB444
    except AttributeError:
      print("WARNING: framebuf compiled without RGB444")
      self.framebufColorProfile = framebuf.RGB565

    tftRotationTuples = []
    for rotationLayout in self.rotationLayouts:
      tftRotationTuples.append(self.convert_rotation_layout_to_tft_tuple(
        self.lcdLandscapeWidth, self.lcdLandscapeHeight, rotationLayout))

    self.spi = machine.SPI(1, 100000_000, polarity=0, phase=0,
      sck=machine.Pin(self.pins['SCK']), mosi=machine.Pin(self.pins['MOSI']), miso=None)

    self.dc = machine.Pin(self.pins['DC'], machine.Pin.OUT)
    self.cs = machine.Pin(self.pins['CS'], machine.Pin.OUT)
    self.backlight = machine.Pin(self.pins['BL'], machine.Pin.OUT)
    self.reset = machine.Pin(self.pins['RST'], machine.Pin.OUT)

    self.tft = st7789.ST7789(
      self.spi, self.lcdLandscapeHeight, self.lcdLandscapeWidth,
      rotation=self.curRotationIdx, rotations=tftRotationTuples,
      reset=self.reset, dc=self.dc, cs=self.cs, backlight=self.backlight)

    self.tft.init()

    # blank entire memory, not just display size
    self.fill_mem_blank()

  def convert_rotation_layout_to_tft_tuple(self, width, height, rotationLayout):
    madctl = (0
      | rotationLayout['MY']  << 7 #0:nothing  1:mirror row address
      | rotationLayout['MX']  << 6 #0:nothing  1:mirror col address
      | rotationLayout['MV']  << 5 #0:nothing  1:swap row and col address
      | MADCTL_ML             << 4
      | MADCTL_RGB            << 3
      | MADCTL_MH             << 2
    )
    if not rotationLayout['LANDSCAPE']:
      (width, height) = (height, width)
    (layoutOffsetX, layoutOffsetY) = (rotationLayout['X'], rotationLayout['Y'])
    return (madctl, width, height, layoutOffsetX, layoutOffsetY)

  #physical LCD size, un-rotated (width is the dimension that is longer on the physical LCD)
  def get_lcd_landscape_size(self):
    return (self.lcdLandscapeWidth, self.lcdLandscapeHeight)
  def get_lcd_landscape_width(self):
    return self.get_lcd_landscape_size()[0]
  def get_lcd_landscape_height(self):
    return self.get_lcd_landscape_size()[1]

  #physical LCD size, rotated (width is current horizontal dimension)
  def get_lcd_rotated_size(self):
    return self.swapIfNotLandscape(self.get_lcd_landscape_size())
  def get_lcd_rotated_width(self):
    return self.get_lcd_rotated_size()[0]
  def get_lcd_rotated_height(self):
    return self.get_lcd_rotated_size()[1]

  #framebuf size, un-rotated (width is the dimension that is longer on the physical LCD)
  def get_framebuf_landscape_size(self):
    return (self.fbConf.fbW, self.fbConf.fbH)
  def get_framebuf_landscape_width(self):
    return self.get_framebuf_landscape_size()[0]
  def get_framebuf_landscape_height(self):
    return self.get_framebuf_landscape_size()[1]

  #framebuf size, rotated (width is current horizontal dimension)
  def get_framebuf_rotated_size(self):
    return self.swapIfNotLandscape(self.get_framebuf_landscape_size())
  def get_framebuf_rotated_width(self):
    return self.get_framebuf_rotated_size()[0]
  def get_framebuf_rotated_height(self):
    return self.get_framebuf_rotated_size()[1]

  #framebuf if enabled, LCD otherwise, rotated (width is current horizontal dimension)
  def get_target_window_size(self):
    if self.is_framebuf_enabled():
      return self.get_framebuf_rotated_size()
    else:
      return self.get_lcd_rotated_size()
  def get_target_window_width(self):
    return self.get_target_window_size()[0]
  def get_target_window_height(self):
    return self.get_target_window_size()[1]

  def get_framebuf_landscape_offset(self):
    return (self.fbConf.fbX, self.fbConf.fbY)
  def get_framebuf_rotated_offset(self):
    return self.swapIfNotLandscape(self.get_framebuf_landscape_offset())

  def swapIfNotLandscape(self, pair):
    return (pair[0], pair[1]) if self.is_landscape() else (pair[1], pair[0])

  #either no framebuf, or framebuf is the same size as LCD
  def is_fullscreen(self):
    return self.get_target_window_size() == self.get_lcd_rotated_size()

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

  def is_landscape(self):
    return self.curRotationLayout['LANDSCAPE']

  def create_buffer(self):
    (fbW, fbH) = self.get_framebuf_landscape_size()
    framebufSizeBytes = fbW * fbH * self.bits_per_px() // 8

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
    self.isWindowSetToFramebuf = False
    if self.buffer != None:
      (rotFBW, rotFBH) = self.get_framebuf_rotated_size()
      self.framebuf = framebuf.FrameBuffer(
        self.buffer, rotFBW, rotFBH, self.framebufColorProfile)

      self.ensure_framebuf_window()
    else:
      self.framebuf = None

    self.init_colors()

  def ensure_framebuf_window(self):
    if self.is_framebuf_enabled() and not self.isWindowSetToFramebuf:
      self.set_window_to_rotated_framebuf()
      self.isWindowSetToFramebuf = True

  def init_colors(self):
    if not self.is_framebuf_enabled():
      #RGB565, big-endian in st7789
      self.colorProfile = COLOR_PROFILE_RGB565
      self.isColorProfileBigEndian = True
      self.set_lcd_RGB565()
    elif self.framebufColorProfile == framebuf.RGB565:
      #RGB565, little-endian in framebuf
      self.colorProfile = COLOR_PROFILE_RGB565
      self.isColorProfileBigEndian = False
      self.set_lcd_RGB565()
    elif self.framebufColorProfile == framebuf.RGB444:
      #RGB444 for framebuf
      self.colorProfile = COLOR_PROFILE_RGB444
      self.isColorProfileBigEndian = True
      self.set_lcd_RGB444()

    self.red     = self.get_color(0xFF, 0x00, 0x00)
    self.green   = self.get_color(0x00, 0xFF, 0x00)
    self.blue    = self.get_color(0x00, 0x00, 0xFF)
    self.cyan    = self.get_color(0x00, 0xFF, 0xFF)
    self.magenta = self.get_color(0xFF, 0x00, 0xFF)
    self.yellow  = self.get_color(0xFF, 0xFF, 0x00)
    self.white   = self.get_color(0xFF, 0xFF, 0xFF)
    self.black   = self.get_color(0x00, 0x00, 0x00)

  def get_color(self, r, g, b):
    color = None
    if self.colorProfile == COLOR_PROFILE_RGB565:
      r5 = int(0b11111  * r/255 + 0.5)
      g6 = int(0b111111 * g/255 + 0.5)
      b5 = int(0b11111  * b/255 + 0.5)
      color = (r5<<11) + (g6<<5) + (b5<<0)
    elif self.colorProfile == COLOR_PROFILE_RGB444:
      r4 = int(0b1111 * r/255 + 0.5)
      g4 = int(0b1111 * g/255 + 0.5)
      b4 = int(0b1111 * b/255 + 0.5)
      color = (r4<<8) + (g4<<4) + (b4<<0)
    else:
      color = 0
      print("WARNING: no color profile available")

    if not self.isColorProfileBigEndian:
      #RGB565 byte order is swapped in framebuf vs st7789
      color = self.swap_hi_lo_byte_order(color)

    return color

  def swap_hi_lo_byte_order(self, h):
    bHi = h >> 8
    bLo = h & 0xff
    return (bLo << 8) | (bHi & 0xff)

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
    elif colorName == "cyan" or colorName == "aqua":
      return self.cyan
    elif colorName == "magenta" or colorName == "purple":
      return self.magenta
    elif colorName == "yellow":
      return self.yellow
    elif colorName == "white":
      return self.white
    elif colorName == "black":
      return self.black
    else:
      return None

  def get_color_hex_rgb(self, hex_rgb):
    try:
      hex_rgb = hex_rgb.replace("#", "")
      if len(hex_rgb) != 6:
        print("WARNING: failed to parse color " + str(hex_rgb))
        return None
      r = int(hex_rgb[0:2], 16)
      g = int(hex_rgb[2:4], 16)
      b = int(hex_rgb[4:6], 16)
      return self.get_color(r, g, b)
    except Exception as e:
      print("WARNING: failed to parse color " + str(hex_rgb) + "\n" + str(e))
      return None

  def get_rotation_degrees(self):
    return self.curRotationLayout['DEG']

  def set_rotation_degrees(self, degrees):
    for rotationIdx in range(0, len(self.rotationLayouts)):
      if self.rotationLayouts[rotationIdx]['DEG'] == degrees:
        self.set_rotation_index(rotationIdx)
        break

  def set_rotation_next(self):
    self.set_rotation_index((self.curRotationIdx + 1) % len(self.rotationLayouts))

  def set_rotation_index(self, rotationIdx):
    wasLandscape = self.is_landscape()

    self.curRotationIdx = rotationIdx
    self.curRotationLayout = self.rotationLayouts[rotationIdx]
    self.tft.rotation(rotationIdx)

    # if framebuf is not the entire screen, blank the entire screen
    if not self.is_fullscreen():
      self.fill_mem_blank()

    if wasLandscape != self.is_landscape() and self.buffer != None:
      # if framebuf is not a square, transpose row/col count (cut off right or bottom)
      (fbW, fbH) = self.get_framebuf_landscape_size()
      if fbW != fbH:
        if fbW % 2 == 1 or fbH % 2 == 1:
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
    (bufWObj, bufHObj) = self.get_framebuf_rotated_size()
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

  def png(self, filename, x, y):
    if self.is_framebuf_enabled():
      print("WARNING: PNG not supported by framebuf"
        + " (drawing on top of framebuf,"
        + " and disabling show until window reset)"
      )
      self.isWindowSetToFramebuf = False

    #st7789 supports RGB565 only
    if self.colorProfile == COLOR_PROFILE_RGB444:
      self.set_lcd_RGB565()

    try:
      self.tft.png(filename, x, y)
    except Exception as e:
      print("WARNING: png render failed\n" + str(e))

    if self.colorProfile == COLOR_PROFILE_RGB444:
      self.set_lcd_RGB444()

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
      self.set_window_to_rotated_framebuf()

  def set_window_to_rotated_framebuf(self):
    (rotFBW, rotFBH) = self.get_framebuf_rotated_size()
    (rotFBX, rotFBY) = self.get_framebuf_rotated_offset()
    self.set_window_with_rotation_offset(rotFBW, rotFBH, rotFBX, rotFBY)

  def set_window_with_rotation_offset(self, w, h, x, y):
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
      self.ensure_framebuf_window()
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
  def getNamedConfs(self, width, height):
    return {
      "full":   FramebufConf(True, width,    height,    0,        0),
      "left":   FramebufConf(True, width//2, height,    0,        0),
      "right":  FramebufConf(True, width//2, height,    width//2, 0),
      "top":    FramebufConf(True, width,    height//2, 0,        0),
      "bottom": FramebufConf(True, width,    height//2, 0,        height//2),
      "square": FramebufConf(True, height,   height,    0,        0),
    }

  @classmethod
  def parseFramebufConfStr(cls, fbConfStr, lcdLandscapeWidth, lcdLandscapeHeight):
    if fbConfStr == None:
      return None

    namedConfs = cls.getNamedConfs(lcdLandscapeWidth, lcdLandscapeHeight)

    fbConf = None
    fbConfStr = fbConfStr.lower()
    if fbConfStr == "off":
      fbConf = None
    elif fbConfStr in namedConfs:
      return namedConfs[fbConfStr]
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
