#LCD Font - simple wrapper around adafruit GFX font and waveshare LCD framebuf
#  support for font sizes and colors with simple markup language
#Copyright 2023 Elliot Wolk
#License: GPLv2

import ustruct

class LcdFont:
  def __init__(self, fontFileName, lcd):
    self.fontFileName = fontFileName
    self.lcd = lcd
    self.defaultColor = self.lcd.white
    self.fontHandle = None
    self.fontWidth = None
    self.fontHeight = None
    self.bitsPerChar = None
    self.bytesPerChar = None
    self.ready = False
    self.cursor = None

  def setup(self):
    if not self.ready:
      self.fontHandle = open(self.fontFileName, 'rb')
      self.fontWidth, self.fontHeight = ustruct.unpack('BB', self.fontHandle.read(2))
      self.bitsPerChar = self.fontWidth * self.fontHeight
      self.bytesPerChar = int(self.bitsPerChar/8 + 0.5)
      self.ready = True

  def close(self):
    if self.ready:
      self.fontHandle.close()
      self.fontHandle = None
      self.fontWidth = None
      self.fontHeight = None
      self.bitsPerChar = None
      self.bytesPerChar = None
      self.ready = False

  def getCharGridWidth(self, size):
    return int( self.lcd.width / ((self.fontWidth+1)*size))

  def getCharGridHeight(self, size):
    return int(self.lcd.height / ((self.fontHeight+1)*size))

  def getFontCharBytes(self, charStr):
    asciiIndex = ord(charStr)
    self.fontHandle.seek(asciiIndex * self.bytesPerChar + 2)
    return ustruct.unpack('B'*self.bytesPerChar, self.fontHandle.read(self.bytesPerChar))

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
  def cursorNewLine(self):
    self.cursor['x'] = self.cursor['startX']
    self.cursor['y'] += int(self.cursor['size'] * (self.fontHeight + self.cursor['vspace']))
  def cursorHline(self):
    color = self.cursor['color']
    if color == None:
      color = self.defaultColor
    self.lcd.hline(self.cursor['startX'], self.cursor['y'],
      self.lcd.get_width(), color)
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
    if color == None:
      color = self.defaultColor
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
    self.lcd.show()

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
    if valStr == "red":
       return self.lcd.red
    elif valStr == "green":
       return self.lcd.green
    elif valStr == "blue":
       return self.lcd.blue
    elif valStr == "white":
       return self.lcd.white
    elif valStr == "black":
       return self.lcd.black
    else:
       return defaultVal
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

  def drawMarkup(self, markup, x=0, y=0, size=5, color=None, hspace=1.0, vspace=1.0):
    #  markup syntax is:
    #    !CMD=VAL!
    #      CMD=COLOR  set the color to COLOR
    #      CMD=SIZE   set the pixels-per-dot to SIZE
    #                   for 5x8 font, font size in px is: 8*SIZE
    #      CMD=X      set the left position of cursor to X as absolute px on LCD
    #      CMD=Y      set the top position of cursor to Y as absolute px on LCD
    #      CMD=HSPACE leave floor(HSPACE*SIZE) dots between each character
    #                   any non-negative number, 1.0=default, 0=no space, 2.0=wide
    #                   for 5x8 font, total width of a char in px is: SIZE*(5+HSPACE)
    #      CMD=VSPACE leave floor(VSPACE*SIZE) dots between lines
    #                   any non-negative number, 1.0=default, 0=no space, 2.0=wide
    #                   for 5x8 font, total height of a line in px is: SIZE*(8+VSPACE)
    #    !CMD=prev!
    #        if VAL is 'prev', restore the value of CMD before the last change
    #        e.g.:   !color=white! A !color=blue! B !color=prev! C
    #                  is the same as:
    #                !color=white! A !color=blue! B !color=white! C
    #    !n!
    #        treated the same as a newline literal
    #          moves the cursor down (8+vspace)*size px,
    #          and resets the left to initial
    #    !!
    #        literal '!' character
    #  e.g.:
    #      hello!n!!size=6!!color=red!world!!
    #        looks similar to the following HTML:
    #      hello<br/><span style="font-size:48px; color:red">world!</span>

    self.cursorSet(x, y, x, y, size, color, hspace, vspace)
    prevVals = {}

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

  def markup(self, markup, x=0, y=0, size=5, color=None, hspace=1.0, vspace=1.0):
    self.lcd.fill(0)
    self.drawMarkup(markup, x, y, size, color, hspace, vspace)
    self.lcd.show()
