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

  def drawMarkup(self, markup, x=0, y=0, size=5, color=None, hspace=1.0, vspace=1.0):
    #  markup syntax is:
    #    !cmd=val!
    #        cmd    set the color to val
    #        size   set the pixels-per-dot to size, font size is 8*size px (for 5x8 font)
    #        x      set the left position for future text to val as absolute px on LCD
    #        y      set the top position for future text to val as absolute px on LCD
    #        hspace leave floor(5*hspace) pixels between each character (for 5x8 font)
    #                 1.0 is the default, 0 means no space, 2.0 means wide
    #        vspace leave floor(8*vspace) pixels between new lines (for 5x8 font)
    #                 1.0 is the default, 0 means no space, 2.0 means wide
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
        elif cmd in self.cursor and len(val) > 0:
          # '!CMD=VAL!' => manipulate cursor without drawing anything
          if cmd == "color":
            if val == "red":
              self.cursor['color'] = self.lcd.red
            elif val == "green":
              self.cursor['color'] = self.lcd.green
            elif val == "blue":
              self.cursor['color'] = self.lcd.blue
            elif val == "white":
              self.cursor['color'] = self.lcd.white
            elif val == "black":
              self.cursor['color'] = self.lcd.black
          elif cmd == "size":
            self.cursor['size'] = int(val)
          elif cmd == "x":
            self.cursor[x] = int(val)
          elif cmd == "y":
            self.cursor[y] = int(val)
          elif cmd == "hspace":
            self.cursor['hspace'] = float(val)
          elif cmd == "vspace":
            self.cursor['vspace'] = float(val)
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
