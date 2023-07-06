# pico-lcd
# Copyright 2023 Elliot Wolk
# License: GPLv2
import network
import time
import socket

from lcd13 import LCD
from lcdFont import LcdFont

if __name__=='__main__':
  LCD.INIT_PWM(65535)
  lcd = LCD()
  lcd.fill(0)

  lcdFont = LcdFont('font5x8.bin', lcd)
  lcdFont.setup()

  lcdFont.markup('!size=5!!color=green!HELLO\nWORLD')
