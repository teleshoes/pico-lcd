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
    self.cursor['x'] += int(self.cursor['size'] * (self.fontWidth + self.cursor['hspace']))
  def cursorDrawPNG(self, filename):
    self.lcd.png(filename, self.cursor['x'], self.cursor['y'])
  def cursorDrawRect(self, w, h):
    self.lcd.rect(self.cursor['x'], self.cursor['y'], w, h, self.getCursorColor(), True)
    self.cursor['x'] += w
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
  def maybeReadCoord(self, valStr, defaultVal):
    valStr = valStr.replace("x", ",", 1) #<X>x<Y> => <X>,<Y>
    valArr = valStr.split(",")
    if len(valArr) == 2:
      x = self.maybeReadInt(valArr[0], None)
      y = self.maybeReadInt(valArr[1], None)
      if x != None and y != None:
        return (x,y)
      else:
        return defaultVal
    else:
      return defaultVal
  def maybeReadBar(self, valStr, defaultVal):
    if valStr.find("x") < valStr.find(","):
      #replace the first 'x', if it is before first ','
      valStr = valStr.replace("x", ",", 1) #<X>x<Y> => <X>,<Y>
    valArr = valStr.split(",")
    if len(valArr) == 5:
      x = self.maybeReadInt(valArr[0], None)
      y = self.maybeReadInt(valArr[1], None)
      pct = self.maybeReadInt(valArr[2], None)
      fillColor = self.maybeReadColor(valArr[3], None)
      emptyColor = self.maybeReadColor(valArr[4], None)
      if x != None and y != None and pct != None and fillColor != None and emptyColor != None:
        return (x,y,pct,fillColor,emptyColor)
      else:
        return defaultVal
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

  def clear(self):
    self.lcd.fill(self.lcd.black)

  def markup(self, markup, isClear=True, isShow=True,
    x=0, y=0, size=5, color=None, hspace=1.0, vspace=1.0
  ):
    if isClear:
      self.clear()
    self.drawMarkup(markup, x, y, size, color, hspace, vspace)
    if isShow:
      self.show()

  def drawMarkup(self, markup, x, y, size, color, hspace, vspace):
    #  markup syntax is:
    #    !CURSOR_CMD=VAL!
    #      CURSOR_CMD = color|size|x|y|hspace|vspace
    #        !color=<COLOR>!
    #          set the cursor color to COLOR
    #          COLOR = either a NAMED_COLOR or a HEX_COLOR
    #          NAMED_COLOR = one of white black red green blue cyan magenta yellow aqua purple
    #          HEX_COLOR   = rgb hex color formatted '#RRGGBB' e.g.: '#C0C0C0'
    #        !size=<SIZE>!
    #          set the pixels-per-dot to SIZE
    #          for 5x8 font, font size in px is: 8*SIZE
    #        !x=<X>!
    #          set the left position of cursor to X as absolute px on LCD
    #        !y=<Y>!
    #          set the top position of cursor to Y as absolute px on LCD
    #        !hspace=<HSPACE>!
    #          leave floor(HSPACE*SIZE) dots between each character
    #            any non-negative number, 1.0=default, 0=no space, 2.0=wide
    #            for 5x8 font, total width of a char in px is: SIZE*(5+HSPACE)
    #        !vspace=<VSPACE>!
    #          leave floor(VSPACE*SIZE) dots between lines
    #            any non-negative number, 1.0=default, 0=no space, 2.0=wide
    #            for 5x8 font, total height of a line in px is: SIZE*(8+VSPACE)
    #
    #    !CURSOR_CMD=prev!
    #      CURSOR_CMD = color|size|x|y|hspace|vspace
    #        if VAL is 'prev', restore the value of CURSOR_CMD before the last change
    #        e.g.:   !color=white! A !color=blue! B !color=prev! C
    #                  is the same as:
    #                !color=white! A !color=blue! B !color=white! C
    #
    #    !png=FILENAME!
    #      draw the PNG image, already present in the filesystem, at FILENAME
    #      cursor position is the top-left corner of the image
    #      NOTE:
    #        A) file must already be on the filesystem, uploaded beforehand with upload command
    #        B) does not move the cursor, use !shift=Wx0! to do so
    #        C) framebuf does not support PNG
    #           if framebuf is enabled,
    #             PNG is drawn directly, relative to the LCD, ignoring the framebuf offset,
    #               'on top' of the previous content,
    #               and the framebuf for that call is *not* rendered
    #           this means all non-PNG markup is ignored
    #           THEREFORE, either:
    #             1) disable framebuf before using !png!, and everything works
    #             or
    #             2) draw all non-PNG markup first,
    #                and then draw PNG markup in a second separate call
    #                (multiple PNGs at once is fine)
    #             e.g.: draw one 16x16 icon twice, with a label,
    #                       and then another 16x16 icon with another label beneath it
    #                     formatted like this:
    #                       Ax2:[a][a]
    #                       Bx1:[b]
    #                     use two drawMarkup() calls,
    #                       one to draw the labels first,
    #                       and one just for the three PNGs
    #
    #                   drawMarkup(): !size=2!!color=red!  Ax2:!n!  Bx1:
    #                   drawMarkup(): !shift=70x0!!png=icon_a_16x16.png!
    #                                 !shift=16x0!!png=icon_a_16x16.png!
    #                                 !size=2!!n!
    #                                 !shift=70x0!!png=icon_b_16x16.png!
    #
    #    !rect=<W>x<H>!
    #    !rect=<W>,<H>!
    #       draw a rectangle from cursor at top-left to (W,H) at bottom-right
    #       move the cursor to the right exactly <W> px (no HSPACE)
    #         e.g.: !rect=10x20!    draw a vertical rectangle at the cursor
    #
    #    !bar=<W>x<H>,<PCT>,<FILL_COLOR>,<EMPTY_COLOR>
    #    !bar=<W>,<H>,<PCT>,<FILL_COLOR>,<EMPTY_COLOR>
    #       draw two rectangles, to make a progress/status bar
    #         W           = the full outer width of the bar in pixels
    #         H           = the full outer height of the bar in pixels
    #         PCT         = an *integer* percentage of the fill state of the bar
    #         FILL_COLOR  = the color of the filled-in part of the bar
    #         EMPTY_COLOR = the color of the outer rectangle of the bar
    #       -draw empty rectangle
    #           -draw one rectangle, without moving the cursor, as in:
    #             !color=<EMPTY_COLOR>!!rect=<W>x<H>!
    #           -move the cursor back and restore previous color, as in:
    #             !shift=-<W>x0!!color=prev!
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
    #            !shift=0x<FILL_SHIFT_Y>!
    #          -draw filled-in rectangle on top of empty rectangle as in:
    #            !color=<FILL_COLOR>!!rect=<FILL_W>x<FILL_H>!
    #           -move the cursor back and restore previous color, as in:
    #             !shift=-<W>x-<FILL_SHIFT_Y>!!color=prev!
    #       -move the cursor to the right of the outer empty rect, as in:
    #          !shift=<X>x0!
    #       e.g.: !bar=20,100,65,green,red!   vertical 20x100 green-on-red bar 65% full
    #                                          same as:
    #                                             !color=red!!rect=20x100!
    #                                             !shift=-20x0!!color=prev!
    #                                             !shift=0x35!
    #                                             !color=green!!rect=20x65!
    #                                             !shift=-20x-35!!color=prev!
    #                                             !shift=20x0!
    #
    #    !shift=<W>x<H>!
    #    !shift=<W>,<H>!
    #       move the left position of the cursor W pixels to the right (negative for left)
    #       move the top position of the cursor H pixels down (negative for up)
    #       e.g.: !shift=0x-20!    move the cursor up 20 pixels
    #
    #    !rtc=FORMAT!
    #        use time from DS3231 rtc clock (if supported) and format with FORMAT string
    #        NOTE: all !rtc=FORMAT! entries in markup share a single epoch time,
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
    #    !n!
    #        treated the same as a newline literal
    #          moves the cursor down (8+vspace)*size px,
    #          and resets the left to initial
    #    !hline!
    #    !hl!
    #    !hr!
    #        draw a horizontal line at cursor
    #    !!
    #        literal '!' character
    #  e.g.:
    #      hello!n!!size=6!!color=red!world!!
    #        looks similar to the following HTML:
    #      hello<br/><span style="font-size:48px; color:red">world!</span>

    if not self.fontReady:
      print("ERROR: no font loaded")
      return

    self.cursorSet(x, y, x, y, size, color, hspace, vspace)
    prevVals = {}

    #calculate once, but only if !rtc! command present
    rtcEpoch = None

    i=0
    while i < len(markup):
      ch = markup[i]
      if ch == "!":
        end = markup.find('!', i+1)
        if end < i:
          #unmatched '!'
          print("WARNING: invalid markup (unmatched '!')\n" + markup)
          cmdValStr = "" #treat same as '!!'
          end = i #skip just the one '!' character
        else:
          cmdValStr = markup[i+1:end]

        cmdVal = cmdValStr.split("=")

        if len(cmdVal) == 1:
          cmd = cmdVal[0].lower()
          val = ""
        elif len(cmdVal) == 2:
          cmd = cmdVal[0].lower()
          val = cmdVal[1]
        else:
          #bad cmd=val format, treat as unknown command
          cmd = None
          val = None

        if cmd == "":
          # '!!' => literal '!'
          self.cursorDrawChar('!')
        elif cmd == "n":
          # '!n!' => newline
          self.cursorNewLine()
        elif cmd == "hline" or cmd == "hl" or cmd == "hr":
          # '!hr!' => hline
          self.cursorHline()
        elif cmd == "png":
          self.cursorDrawPNG(val)
        elif cmd == "rect":
          (w, h) = self.maybeReadCoord(val, (0,0))
          self.cursorDrawRect(w, h)
        elif cmd == "shift":
          (x, y) = self.maybeReadCoord(val, (0,0))
          self.cursor['x'] += x
          self.cursor['y'] += y
        elif cmd == "bar":
          (w, h, pct, fillColor, emptyColor) = self.maybeReadBar(val, (0,0,0,None,None))
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
          # '!CMD=VAL!' => manipulate cursor without drawing anything
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
          self.cursorDrawText('!' + cmdValStr + '!')

        i = end+1 #skip '!CMDVALSTR!'
      elif ch == "\n":
        self.cursorNewLine()
        i += 1
      else:
        self.cursorDrawChar(ch)
        i += 1
