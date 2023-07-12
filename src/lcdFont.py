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

  def drawChar(self, charStr, left, top, size, color):
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
          self.lcd.rect(left + chX*size, top + chY*size, size, size, color, True)

  def drawText(self, text, x=0, y=0, size=5, color=None, hspace=1.0, vspace=1.0):
    top = y
    for line in text.split("\n"):
      left = x
      for charStr in line:
        self.drawChar(charStr, left, top, size, color)
        left += int((self.fontWidth+hspace)*size)
      top += int((self.fontHeight+vspace)*size)

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
    top = y
    for line in markup.split("\n"):
      left = x
      i=0
      while i < len(line):
        ch = line[i]
        if ch == "!":
          end = line.find('!', i+1)
          if end < i:
            print("WARNING: invalid markup\n" + markup)
            cmdVal = []
          else:
            cmdVal = line[i+1:end].split("=")

          if len(cmdVal) == 1 and cmdVal[0] == "":
            # '!!' is literal '!'
            self.drawChar('!', left, top, size, color)
            left += int((self.fontWidth+hspace)*size)
            i += 2 #skip '!!'
          elif len(cmdVal) == 1 and cmdVal[0] == "n":
            # !n! is a newline
            top += int((self.fontHeight+vspace)*size)
            left = x
            i = end+1 #skip '!n!'
          elif len(cmdVal) != 2:
            print("WARNING: invalid markup\n" + markup)
            self.drawChar('!', left, top, size, color)
            left += int((self.fontWidth+hspace)*size)
            i += 1 #skip '!'
          else:
            cmd, val = cmdVal
            cmd = cmd.lower()
            if cmd == "color":
              if val == "red":
                color = self.lcd.red
              elif val == "green":
                color = self.lcd.green
              elif val == "blue":
                color = self.lcd.blue
              elif val == "white":
                color = self.lcd.white
              elif val == "black":
                color = self.lcd.black
            elif cmd == "size":
              size = int(val)
            elif cmd == "x":
              left = int(val)
            elif cmd == "y":
              top = int(val)
            elif cmd == "hspace":
              hspace = float(val)
            elif cmd == "vspace":
              vspace = float(val)
            i = end+1 #skip '!cmd=val!'
        else:
          self.drawChar(ch, left, top, size, color)
          left += int((self.fontWidth+hspace)*size)
          i += 1
      top += int((self.fontHeight+vspace)*size)

  def markup(self, markup, x=0, y=0, size=5, color=None, hspace=1.0, vspace=1.0):
    self.lcd.fill(0)
    self.drawMarkup(markup, x, y, size, color, hspace, vspace)
    self.lcd.show()
