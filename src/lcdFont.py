#LCD Font - simple wrapper around adafruit GFX font and waveshare LCD framebuf
#  support for font sizes and colors with simple markup language
#Copyright 2023 Elliot Wolk
#License: GPLv2

import time
import ustruct

class LcdFont:
  def __init__(self, fontFileName, lcd, rtc=None):
    self.fontFileName = fontFileName
    self.lcd = lcd
    self.rtc = rtc
    self.defaultColorName = 'white'
    self.fontHandle = None
    self.fontWidth = None
    self.fontHeight = None
    self.bitsPerChar = None
    self.bytesPerChar = None
    self.fontReady = False
    self.cursor = None
    self.pngInfosToShow = []

  def setup(self):
    if not self.fontReady:
      try:
        self.fontHandle = open(self.fontFileName, 'rb')
        self.fontWidth, self.fontHeight = ustruct.unpack('BB', self.fontHandle.read(2))
        self.bitsPerChar = self.fontWidth * self.fontHeight
        self.bytesPerChar = int(self.bitsPerChar/8 + 0.5)
        self.fontReady = True
      except OSError as e:
        print("ERROR LOADING FONT: " + str(self.fontFileName))
        self.fontReady = False

  def close(self):
    if self.fontReady:
      self.fontHandle.close()
      self.fontHandle = None
      self.fontWidth = None
      self.fontHeight = None
      self.bitsPerChar = None
      self.bytesPerChar = None
      self.fontReady = False

  def setLCD(self, lcd):
    self.lcd = lcd

  def setRTC(self, rtc):
    self.rtc = rtc

  def getCharGridSize(self, size):
    (winW, winH) = self.lcd.get_target_window_size()
    charW = int(winW / ((self.fontWidth+1)*size))
    charH = int(winH / ((self.fontHeight+1)*size))
    return (charW, charH)

  def getFontCharBytes(self, charStr):
    asciiIndex = ord(charStr)
    self.fontHandle.seek(asciiIndex * self.bytesPerChar + 2)
    return ustruct.unpack('B'*self.bytesPerChar, self.fontHandle.read(self.bytesPerChar))

  def getCursorColor(self):
    return self.getOptColor(self.cursor['color'])
  def getOptColor(self, color):
    if color == None:
      color = self.lcd.get_color_by_name(self.defaultColorName)
    return color

  def cursorSet(self, startX, startY, x, y, size, color, hspace, vspace):
    self.cursor = {
      "startX": startX,
      "startY": startY,
      "x" : x,
      "y" : y,
      "size": size,
      "color": color,
      "hspace": hspace,
      "vspace": vspace
    }
  def cursorDrawChar(self, charStr):
    self.drawChar(charStr,
      self.cursor['x'], self.cursor['y'], self.cursor['size'], self.cursor['color'])
    self.cursor['x'] += self.cursor['size'] * self.fontWidth
    self.cursorIndentHspace()
  def cursorIndentHspace(self):
    self.cursor['x'] += int(self.cursor['size'] * self.cursor['hspace'])
  def cursorDrawPNG(self, filename):
    if self.lcd.is_framebuf_enabled():
      #delay drawing PNGs until after framebuf is shown
      self.pngInfosToShow.append({
        "filename":filename,
        "x":self.cursor['x'],
        "y":self.cursor['y'],
      })
    else:
      self.lcd.png(filename, self.cursor['x'], self.cursor['y'])
  def cursorDrawPNM(self, filename):
    (w, h) = self.lcd.pnm(filename, self.cursor['x'], self.cursor['y'])
    self.cursor['x'] += w
  def cursorDrawRect(self, w, h, fill=True):
    self.lcd.rect(self.cursor['x'], self.cursor['y'], w, h, self.getCursorColor(), fill)
    self.cursor['x'] += w
  def cursorDrawEllipse(self, radX, radY, fill=True):
    self.lcd.ellipse(self.cursor['x'] + radX, self.cursor['y'] + radY, radX, radY, self.getCursorColor(), fill)
    self.cursor['x'] += radX * 2 + 1
  def cursorDrawBar(self, w, h, pct, fillColor, emptyColor):
    x = self.cursor['x']
    y = self.cursor['y']
    (emptyX, emptyY, emptyW, emptyH) = (x,y,w,h)
    (fillX, fillY, fillW, fillH) = (x,y,w,h)
    if w > h:
      fillW = int(fillW * pct / 100.0)
    else:
      fillH = int(fillH * pct / 100.0)
      fillY += h-fillH

    self.lcd.rect(emptyX, emptyY, emptyW, emptyH, self.getOptColor(emptyColor), True)
    self.lcd.rect(fillX, fillY, fillW, fillH, self.getOptColor(fillColor), True)
    self.cursor['x'] += w
  def cursorNewLine(self):
    self.cursor['x'] = self.cursor['startX']
    self.cursor['y'] += int(self.cursor['size'] * (self.fontHeight + self.cursor['vspace']))
  def cursorHline(self):
    color = self.getCursorColor()
    (winW, winH) = self.lcd.get_target_window_size()
    self.lcd.hline(self.cursor['startX'], self.cursor['y'], winW, color)
    self.cursor['x'] = self.cursor['startX']
    self.cursor['y'] += 1
  def cursorDrawText(self, text):
    for ch in text:
      if ch == "\n":
        self.cursorNewLine()
      else:
        self.cursorDrawChar(ch)

  # charStr    a string containing a single character
  # (x, y)     the top-left corner of the character in pixels
  # size       pixels-per-dot of the font (characterHeight = fontHeight * pxPerDot)
  # color      color in the colorspace of the lcd
  def drawChar(self, charStr, x, y, size, color):
    fontCharBytes = self.getFontCharBytes(charStr)
    byteIndex = 0
    bitIndex = 0
    byte = fontCharBytes[byteIndex]
    color = self.getOptColor(color)
    for chX in range(self.fontWidth):
      for chY in range(self.fontHeight):
        if bitIndex >= 8:
          bitIndex = 0
          byteIndex += 1
          byte = fontCharBytes[byteIndex]
        dotBit = byte >> bitIndex & 0x1
        bitIndex += 1
        if dotBit == 1:
          self.lcd.rect(x + chX*size, y + chY*size, size, size, color, True)

  def drawText(self, text, x=0, y=0, size=5, color=None, hspace=1.0, vspace=1.0):
    self.cursorSet(x, y, x, y, size, color, hspace, vspace)
    self.cursorDrawText(text)

  def text(self, text, x=0, y=0, size=5, color=None, hspace=1.0, vspace=1.0):
    self.lcd.fill(0)
    self.drawText(text, x, y, size, color, hspace, vspace)
    self.show()

  def maybeReadCmdVal(self, cmd, valStr, defaultVal):
    if cmd == "color":
      return self.maybeReadColor(valStr, defaultVal)
    elif cmd == "size" or cmd == "x" or cmd == "y":
      return self.maybeReadInt(valStr, defaultVal)
    elif cmd == "hspace" or cmd == "vspace":
      return self.maybeReadFloat(valStr, defaultVal)
    else:
      return defaultVal
  def maybeReadColor(self, valStr, defaultVal):
    color = self.lcd.get_color_by_name(valStr)
    if color == None:
      color = self.lcd.get_color_hex_rgb(valStr)
    if color == None:
      color = defaultVal
    return color
  def maybeReadInt(self, valStr, defaultVal):
    try:
      return int(valStr)
    except:
      return defaultVal
  def maybeReadFloat(self, valStr, defaultVal):
    try:
      return float(valStr)
    except:
      return defaultVal
  def maybeReadBool(self, valStr, defaultVal):
    if valStr.lower() in ["true", "1", "y"]:
      return True
    elif valStr.lower() in ["false", "0", "n"]:
      return False
    else:
      return defaultVal

  def formatTime(self, formatSpec, epoch):
    val = ""
    i = 0
    tspec = time.gmtime(epoch)

    while i < len(formatSpec):
      ch = formatSpec[i]
      i += 1
      if ch == "%" and i<len(formatSpec):
        formatCh = formatSpec[i]
        i += 1

        if formatCh == "%":
          val += "%"
        elif formatCh == "s":
          val += str(epoch)
        elif formatCh == "Y":
          val += "%04d" % tspec[0]
        elif formatCh == "m":
          val += "%02d" % tspec[1]
        elif formatCh == "d":
          val += "%02d" % tspec[2]
        elif formatCh == "H":
          val += "%02d" % tspec[3]
        elif formatCh == "I":
          hr = tspec[3] % 12
          hr = 12 if hr == 0 else hr
          val += "%02d" % hr
        elif formatCh == "p":
          val += "AM" if tspec[3] < 12 else "PM"
        elif formatCh == "M":
          val += "%02d" % tspec[4]
        elif formatCh == "S":
          val += "%02d" % tspec[5]
        elif formatCh == "a":
          weekDays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
          val += weekDays(tspec[6] % 6)
        elif formatCh == "b":
          months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
          val += months((tspec[1] - 1) % 12)
        else:
          #invalid format char, treat as literal
          val += "%" + ch
      else:
        val += ch
    return val

  def show(self):
    self.lcd.show()
    for pngInfo in self.pngInfosToShow:
      self.lcd.png(pngInfo['filename'], pngInfo['x'], pngInfo['y'])

  def clear(self):
    self.lcd.fill(self.lcd.black)
    self.clearPNG()

  def clearFullLCD(self):
    self.lcd.fill_mem_blank()
    self.clearPNG()

  def clearPNG(self):
    self.pngInfosToShow = []

  def markup(self, markup, isClear=True, isShow=True,
    x=0, y=0, size=5, color=None, hspace=1.0, vspace=1.0
  ):
    if isClear:
      self.clear()
    self.drawMarkup(markup, x, y, size, color, hspace, vspace)
    if isShow:
      self.show()

  def drawMarkup(self, markup, x, y, size, color, hspace, vspace):
    #  ### MARKUP_SYNTAX ###
    #  markup syntax is:
    #    [CURSOR_CMD=VAL]
    #      CURSOR_CMD = color|size|x|y|hspace|vspace
    #        [color=<COLOR>]
    #          set the cursor color to COLOR
    #          COLOR = either a NAMED_COLOR or a HEX_COLOR
    #          NAMED_COLOR = one of white black red green blue cyan magenta yellow aqua purple
    #          HEX_COLOR   = rgb hex color formatted '#RRGGBB' e.g.: '#C0C0C0'
    #        [size=<SIZE>]
    #          set the pixels-per-dot to SIZE
    #          for 5x8 font, font size in px is: 8*SIZE
    #        [x=<X>]
    #          set the left position of cursor <CURSOR_X> to <X>, as absolute px on LCD
    #        [y=<Y>]
    #          set the top position of cursor <CURSOR_Y> to <Y>, as absolute px on LCD
    #        [hspace=<HSPACE>]
    #          leave floor(HSPACE*SIZE) dots between each character
    #            any non-negative number, 1.0=default, 0=no space, 2.0=wide
    #            for 5x8 font, total width of a char in px is: SIZE*(5+HSPACE)
    #        [vspace=<VSPACE>]
    #          leave floor(VSPACE*SIZE) dots between lines
    #            any non-negative number, 1.0=default, 0=no space, 2.0=wide
    #            for 5x8 font, total height of a line in px is: SIZE*(8+VSPACE)
    #
    #    [CURSOR_CMD=prev]
    #      CURSOR_CMD = color|size|x|y|hspace|vspace
    #        if VAL is 'prev', restore the value of CURSOR_CMD before the last change
    #        e.g.:   [color=white] A [color=blue] B [color=prev] C
    #                  is the same as:
    #                [color=white] A [color=blue] B [color=white] C
    #
    #    [pnm=FILENAME]
    #      draw the Netpbm image, already present in the filesystem, at FILENAME
    #      top-left corner of the image is at cursor (<CURSOR_X>,<CURSOR_Y>)
    #        -cursor is shifted to the right by the image size
    #        -writing to framebuf is supported
    #        -NOTE: fairly RAM efficient, reads 1KiB of file at a time to render
    #               moderately fast impl using micropython.viper
    #        -only the following formats are implemented:
    #            FILETYPE | COLORSPACE/TUPLTYPE | MAXVAL | DEPTH
    #            =========|=====================|========|======
    #            P4 [PBM] | BLACKANDWHITE       | 1      | 1/8  (1bit per px, 0 for white)
    #            P5 [PGM] | GRAYSCALE           | 255    | 1
    #            P6 [PPM] | RGB                 | 255    | 3
    #            P7 [PAM] | BLACKANDWHITE       | 1      | 1    (1byte per px, 0x00 for black)
    #            P7 [PAM] | BLACKANDWHITE_ALPHA | 1      | 2    (1byte for bw, one byte for alpha)
    #            P7 [PAM] | GRAYSCALE           | 255    | 1    (same as PGM)
    #            P7 [PAM] | GRAYSCALE_ALPHA     | 255    | 2
    #            P7 [PAM] | RGB                 | 255    | 3    (same as PPM)
    #            P7 [PAM] | RGB_ALPHA           | 255    | 4
    #         -P1, P2, and P3 (the ASCII/plaintext versions of PBM/PGM/PPM) are *not* implemented
    #         -MAXVAL above 256 (e.g.: for 48bit RGB) are not implemented for any type
    #         -alpha channels are removed (with a black background) before rendering
    #
    #      e.g.: draw one 16x16 icon twice, with a label,
    #              and then another 16x16 icon with another label beneath it,
    #              formatted like this:
    #                Ax2:|a||a|
    #                Bx1:|b|
    #            [size=2][color=red]
    #            Ax2:[pnm=icon_a_16x16.pam][pnm=icon_a_16x16.pam]
    #            [n]
    #            Bx1:[pnm=icon_b_16x16.pam]
    #
    #    [png=FILENAME]
    #      draw the PNG image, already present in the filesystem, at FILENAME
    #      top-left corner of the image is at cursor (<CURSOR_X>,<CURSOR_Y>)
    #      NOTE:
    #        A) file must already be on the filesystem, uploaded beforehand with upload command
    #        B) does not move the cursor, use [shift=<W>x0] to do so, where <W> is the PNG width
    #        C) framebuf does not support PNG:
    #             if framebuf is enabled:
    #               -PNGs are drawn directly on the LCD, not the framebuf
    #               -PNGs are offset by the same amount as the framebuf,
    #                 but they may extend past the area of the framebuf
    #               -PNGs are drawn only after building and showing the framebuf
    #                  -PNGs are always 'on top' of any other markup in framebuf
    #                  -PNGs will 'flicker' when being redrawn, if they overlap the framebuf
    #               -PNGs are re-drawn on each show until clear() is called
    #
    #      e.g.: draw one 16x16 icon twice, with a label,
    #              and then another 16x16 icon with another label beneath it,
    #              formatted like this:
    #                Ax2:|a||a|
    #                Bx1:|b|
    #            [size=2][color=red]
    #            Ax2:[png=icon_a_16x16.png][shift=16x0][png=icon_a_16x16.png]
    #            [n]
    #            Bx1:[png=icon_b_16x16.png]
    #
    #    [rect=<W>x<H>,<IS_FILL>,<IS_SYMBOL>]
    #    [rect=<W>,<H>,<IS_FILL>,<IS_SYMBOL>]
    #       -draw a rectangle from top-left at (<CURSOR_X>,<CURSOR_Y>) to bottom-right at (<W>,<H>)
    #       -move the cursor to the right exactly <W> px
    #       -fill pixels if <IS_FILL>
    #          -if <IS_FILL> is 'true' or '1' or 'y':
    #            -set fill=True, draw pixels contained by the rectangle
    #            (True is the default if omitted)
    #          -if <IS_FILL> is 'false' or '0' or 'n':
    #            -set fill=False, draw only the outline of the rectangle
    #       -scale and indent if <IS_SYMBOL>
    #          -if <IS_SYMBOL> is 'true' or '1' or 'y':
    #            -scale rectangle by <SIZE>, i.e.: [rect=<W>*<SIZE>,<H>*<SIZE>]
    #            -shift to the right by <HSPACE>*<SIZE>, i.e.: [shift=<HSPACE>*<SIZE>x0]
    #          -if <IS_SYMBOL> is 'false' or '0' or 'n':
    #             -do not scale <W> or <H>
    #             -do not shift by <HSPACE>
    #            (False is the default if omitted)
    #       e.g.:
    #          [rect=10x10,n,n]           empty square 10x10
    #          [size=3]A[rect=6x10,y,y]B  'A', solid rectangle 18x30 with 3px indent, 'B'
    #          [size=5]A[rect=5x8,n,y]B   'A', placeholder char, 'B', same spacing as 'A_B'
    #
    #    [rect=<W>x<H>]
    #    [rect=<W>,<H>]
    #       same as: [rect=<W>x<H>,True,False]
    #
    #    [ellipse=<RAD_X>x<RAD_Y>,<IS_FILL>,<IS_SYMBOL>]
    #    [ellipse=<RAD_X>,<RAD_Y>,<IS_FILL>,<IS_SYMBOL>]
    #       -draw an ellipse with x-radius=<RAD_X> and y-radius=<RAD_Y>,
    #         centered at (<CURSOR_X> + <RAD_X>, <CURSOR_Y> + <RAD_Y>)
    #         (left-most point is at <CURSOR_X>, top-most point is at <CURSOR_Y>)
    #       -<RAD_X> and <RAD_Y> can be fractional, to be scaled by <IS_SYMBOL>
    #       -move the cursor to the right exactly 2*<RAD_X>+1 px
    #       -fill pixels if <IS_FILL>
    #          -if <IS_FILL> is 'true' or '1' or 'y':
    #            -set fill=True, draw pixels contained by the ellipse
    #            (True is the default if omitted)
    #          -if <IS_FILL> is 'false' or '0' or 'n':
    #            -set fill=False, draw only the outline of the ellipse
    #       -scale and indent if <IS_SYMBOL>
    #          -if <IS_SYMBOL> is 'true' or '1' or 'y':
    #            -scale ellipse diameters by <SIZE>
    #                <RAD_X> = floor( (<RAD_X>*2+1)*<SIZE>) / 2)
    #                <RAD_Y> = floor( (<RAD_Y>*2+1)*<SIZE>) / 2)
    #            -shift to the right by <HSPACE>*<SIZE>, i.e.: [shift=<HSPACE>*<SIZE>x0]
    #          -if <IS_SYMBOL> is 'false' or '0' or 'n':
    #             -do not scale <RAD_X> or <RAD_Y>
    #             -do not shift by <HSPACE>
    #            (False is the default if omitted)
    #
    #       NOTE:
    #         -all horizontal/vertical diameters are always an odd number of pixels
    #
    #         -if xR=0 or yR=0, the result is a line segment and <IS_FILL> has no effect
    #
    #         -with <CURSOR> = (<CURSOR_X>,<CURSOR_Y>)
    #           [ellipse=0,0,n,n] => 1px single pixel at <CURSOR>+(0,0)
    #           [ellipse=1,0,n,n] => 3px horizontal line from <CURSOR>+(0,0) to <CURSOR>+(2,0)
    #           [ellipse=0,1,n,n] => 3px vertical line from <CURSOR>+(0,0) to <CURSOR>+(0,2)
    #           [ellipse=1,1,n,n] => 3px cross centered at <CURSOR>+(1,1),
    #                                with the point <CURSOR>+(0,0) omitted for fill=False,
    #                                made of two 3px lines:
    #                                  3px horizontal line from <CURSOR>+(0,1) to <CURSOR>+(2,1)
    #                                  3px vertical line from <CURSOR>+(1,0) to <CURSOR>+(1,2)
    #           [ellipse=2,2] => a 5px diameter circle centered at <CURSOR>+(2,2)
    #
    #       e.g.:
    #          [ellipse=5x5,n,n]                 empty circle 10px diameter
    #          [size=3]A[ellipse=5.1x4.9,y,y]B   'A', solid circle 33px diameter, 3px indent, 'B'
    #                                            same as: [size=3]A[ellipse=16x16,y,n][shift=3x0]B
    #          [size=5]25[ellipse=0.4x0.7,n,y]C  '25', stylized degree symbol, 3px indent, 'C'
    #                                            same as: [size=5]25[ellipse=4,6,n,n][shift=5x0]C
    #
    #    [ellipse=<RAD_X>x<RAD_Y>]
    #    [ellipse=<RAD_X>,<RAD_Y>]
    #      same as: [ellipse=<RAD_X>x<RAD_Y>,True,False]
    #
    #    [bar=<W>x<H>,<PCT>,<FILL_COLOR>,<EMPTY_COLOR>]
    #    [bar=<W>,<H>,<PCT>,<FILL_COLOR>,<EMPTY_COLOR>]
    #       draw two rectangles, to make a progress/status bar
    #         W           = the full outer width of the bar in pixels
    #         H           = the full outer height of the bar in pixels
    #         PCT         = an *integer* percentage of the fill state of the bar
    #         FILL_COLOR  = the color of the filled-in part of the bar
    #         EMPTY_COLOR = the color of the outer rectangle of the bar
    #       -draw empty rectangle
    #           -draw one rectangle, without moving the cursor, as in:
    #             [color=<EMPTY_COLOR>][rect=<W>x<H>]
    #           -move the cursor back and restore previous color, as in:
    #             [shift=-<W>x0][color=prev]
    #       -calculate filled-in rectangle
    #         -if <W> is bigger than <H> (horizontal bar):
    #            -calculate <FILL_W> as floor(<W>*<PCT>/100.0)
    #            -calculate <FILL_H> as just <H>
    #            -calculate <FILL_SHIFT_Y> as 0
    #         -otherwise (vertical bar):
    #            -calculate <FILL_W> as just <W>
    #            -calculate <FILL_H> as floor(<H>*<PCT>/100.0)
    #            -calculate <FILL_SHIFT_Y> as <H> - <FILL_H>
    #       -draw filled-in rectangle
    #          -move the cursor down for vertical bars (filled-in on bottom), as in:
    #            [shift=0x<FILL_SHIFT_Y>]
    #          -draw filled-in rectangle on top of empty rectangle as in:
    #            [color=<FILL_COLOR>][rect=<FILL_W>x<FILL_H>]
    #           -move the cursor back and restore previous color, as in:
    #             [shift=-<W>x-<FILL_SHIFT_Y>][color=prev]
    #       -move the cursor to the right of the outer empty rect, as in:
    #          [shift=<X>x0]
    #       e.g.: [bar=20,100,65,green,red]   vertical 20x100 green-on-red bar 65% full
    #                                          same as:
    #                                             [color=red][rect=20x100]
    #                                             [shift=-20x0][color=prev]
    #                                             [shift=0x35]
    #                                             [color=green][rect=20x65]
    #                                             [shift=-20x-35][color=prev]
    #                                             [shift=20x0]
    #
    #    [shift=<W>x<H>]
    #    [shift=<W>,<H>]
    #       add <W> to <CURSOR_X> (move the cursor <W> pixels to the right, negative <W> for left)
    #       add <H> to <CURSOR_Y> (move the cursor <Y> pixels down, negative <H> for up)
    #       e.g.: [shift=0x-20]    move the cursor up 20 pixels
    #
    #    [rtc=FORMAT]
    #        use time from DS3231 rtc clock (if supported) and format with FORMAT string
    #        NOTE: all [rtc=FORMAT] entries in markup share a single epoch time,
    #              multiple entries cannot show different times due to race conditions
    #
    #        FORMAT is any string, with the following replacements:
    #          %s   EPOCH number of seconds since
    #          %Y   year, formatted as YYYY
    #          %m   month 1-12, formatted as MM
    #          %d   day 1-31, formatted as DD
    #          %H   hour 0-23, formatted as HH
    #          %I   hour 1-12, formatted as II
    #          %p   'AM' if %H is less than 12, otherwise 'PM'
    #          %M   minute, 0-59
    #          %S   second, 0-59
    #          %a   abbreviated day of week Mon/Tue/Wed/Thu/Fri/Sat/Sun
    #          %b   abbreviated month Jan/Feb/Mar/Apr/May/Jun/Jul/Aug/Sep/Oct/Nov/Dec
    #          %%   literal '%' character
    #    [n]
    #        treated the same as a newline literal
    #          moves the cursor down (8+vspace)*size px,
    #          and resets the left to initial
    #    [hline]
    #    [hl]
    #    [hr]
    #        draw a horizontal line at cursor
    #    [[
    #    [bracket]
    #        literal '[' character
    #  e.g.:
    #      hello[n][size=6][color=red]world[[]]
    #        looks similar to the following HTML:
    #      hello<br/><span style="font-size:48px; color:red">world[]]</span>
    #  ### MARKUP_SYNTAX ###

    if not self.fontReady:
      print("ERROR: no font loaded")
      return

    self.cursorSet(x, y, x, y, size, color, hspace, vspace)
    prevVals = {}

    #calculate once, but only if [rtc] command present
    rtcEpoch = None

    markupLen = len(markup)

    i=0
    while i < markupLen:
      ch = markup[i]
      if ch == "[":
        end = markup.find(']', i+1)
        if i+1 < markupLen and markup[i+1] == '[':
          # '[[' => literal '['
          cmdValStr = "bracket"
          end = i+1 #skip both [s
        elif end < i:
          #unmatched '['
          print("WARNING: invalid markup (unmatched '[')\n" + markup)
          cmdValStr = "bracket" #treat same as '[bracket]'
          end = i #skip just the one '[' character
        else:
          cmdValStr = markup[i+1:end]

        cmdVal = cmdValStr.split("=", 2)

        cmd = cmdVal[0].lower()
        val = ""
        if len(cmdVal) == 2:
          val = cmdVal[1]

        maxArgCounts = {
          "rect"    :4,
          "ellipse" :4,
          "bar"     :5,
          "shift"   :2,
        }

        valArgList = []
        if cmd in maxArgCounts:
          valArgList = val.split(",", maxArgCounts[cmd]-1)
          if "x" in valArgList[0]:
            #allow <X>x<Y> syntax instead of <X>,<Y> for first arg
            val = val.replace("x", ",", 1)
            valArgList = val.split(",")

        if cmd == "bracket":
          # literal '[', either '[bracket]' or '[['
          self.cursorDrawChar('[')
        elif cmd == "n":
          # '[n]' => newline
          self.cursorNewLine()
        elif cmd == "hline" or cmd == "hl" or cmd == "hr":
          # '[hr]' => hline
          self.cursorHline()
        elif cmd == "png":
          self.cursorDrawPNG(val)
        elif cmd == "pnm":
          self.cursorDrawPNM(val)
        elif cmd == "rect":
          (w, h, isFill, isSymbol) = (0, 0, True, False)
          if len(valArgList) >= 2:
            w = self.maybeReadInt(valArgList[0], 0)
            h = self.maybeReadInt(valArgList[1], 0)
          if len(valArgList) >= 3:
            isFill = self.maybeReadBool(valArgList[2], True)
          if len(valArgList) >= 4:
            isSymbol = self.maybeReadBool(valArgList[3], True)

          if isSymbol:
            w = w * self.cursor['size']
            h = h * self.cursor['size']
          self.cursorDrawRect(w, h, isFill)
          if isSymbol:
            self.cursorIndentHspace()
        elif cmd == "ellipse":
          (radX, radY, isFill, isSymbol) = (0, 0, True, False)

          if len(valArgList) >= 2:
            radX = self.maybeReadFloat(valArgList[0], 0)
            radY = self.maybeReadFloat(valArgList[1], 0)
          if len(valArgList) >= 3:
            isFill = self.maybeReadBool(valArgList[2], True)
          if len(valArgList) >= 4:
            isSymbol = self.maybeReadBool(valArgList[3], False)

          if isSymbol:
            radX = (radX*2+1) * self.cursor['size'] / 2
            radY = (radY*2+1) * self.cursor['size'] / 2
          (radX, radY) = (int(radX), int(radY))
          self.cursorDrawEllipse(radX, radY, isFill)
          if isSymbol:
            self.cursorIndentHspace()
        elif cmd == "shift":
          (x, y) = (0, 0)
          if len(valArgList) == 2:
            x = self.maybeReadInt(valArgList[0], 0)
            y = self.maybeReadInt(valArgList[1], 0)
          self.cursor['x'] += x
          self.cursor['y'] += y
        elif cmd == "bar":
          (w, h, pct, fillColor, emptyColor) = (0,0,0,None,None)

          if len(valArgList) == 5:
            w = self.maybeReadInt(valArgList[0], 0)
            h = self.maybeReadInt(valArgList[1], 0)
            pct = self.maybeReadInt(valArgList[2], 0)
            fillColor = self.maybeReadColor(valArgList[3], None)
            emptyColor = self.maybeReadColor(valArgList[4], None)

          self.cursorDrawBar(w, h, pct, fillColor, emptyColor)
        elif cmd == "rtc":
          if rtcEpoch == None:
            if self.rtc == None:
              print("WARNING: external rtc epoch not available, using system rtc\n")
              rtcEpoch = time.time()
            else:
              rtcEpoch = self.rtc.getTimeEpochPlusTZOffset()
          self.cursorDrawText(self.formatTime(val, rtcEpoch))
        elif cmd in self.cursor and len(val) > 0:
          # '[CMD=VAL]' => manipulate cursor without drawing anything
          if val == "prev":
            if cmd in prevVals:
              self.cursor[cmd] = prevVals[cmd]
            else:
              print("WARNING: ignoring 'prev' value without previous value\n" + markup)
          else:
            prevVals[cmd] = self.cursor[cmd]
            self.cursor[cmd] = self.maybeReadCmdVal(cmd, val, self.cursor[cmd])
        else:
          # unknown command, just draw the full markup segment
          print("WARNING: invalid markup (unknown command)\n" + markup)
          self.cursorDrawText('[' + cmdValStr + ']')

        i = end+1 #skip '[CMDVALSTR]'
      elif ch == "\n":
        self.cursorNewLine()
        i += 1
      else:
        self.cursorDrawChar(ch)
        i += 1
