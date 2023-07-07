# pico-lcd
# Copyright 2023 Elliot Wolk
# License: GPLv2
import network
import time
import socket

import base64 #non-standard, must build micropython

from lcd13 import LCD
from lcdFont import LcdFont

if __name__=='__main__':
  LCD.INIT_PWM(65535)
  lcd = LCD()
  lcd.fill(0)

  lcdFont = LcdFont('font5x8.bin', lcd)
  lcdFont.setup()

  networks = []
  with open("wifi-conf.txt", "r") as fh:
    for line in fh:
      idx = line.find("=")
      if idx > 0:
        ssid = line[:idx].strip()
        password = line[idx+1:].strip()
        networks.append([ssid, password])

  connected = False
  connectedSSID = None
  while not connected:
    for ssidPassword in networks:
      ssid = ssidPassword[0]
      password = ssidPassword[1]

      wlan = network.WLAN(network.STA_IF)
      wlan.active(True)
      try:
        wlan.connect(ssid, password)
      except Exception as e:
        print(str(e))

      lcdFont.markup(""
        + "!size=4!!color=green!" + "WAITING\n"
        + "!size=4!!color=green!" + "FOR WIFI\n"
        + "!size=4!!color=white!" + "--------\n"
        + "!size=2!!color=blue!"  + ssid
      )

      max_wait = 10
      while max_wait > 0:
          if wlan.status() < 0 or wlan.status() >= 3:
              break
          max_wait -= 1
          print('waiting for connection...')
          time.sleep(1)

      if wlan.status() == 3:
        connected = True
        connectedSSID = ssid
        break

  ipAddr = None
  if not connected:
      lcdFont.markup("!size=7!!color=red!" + "FAILED\nWIFI")
      raise RuntimeError('network connection failed')

  else:
      print('connected')
      status = wlan.ifconfig()
      print( 'ip = ' + status[0] )
      ipAddr = status[0]

  addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]

  s = socket.socket()
  s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  s.bind(addr)
  s.listen(1)

  print('listening on', addr)

  lcd.fill(0)
  lcdFont.markup(""
    + "!size=4!!color=green!"             + "CONNECTED\n"
    + "!size=3!!color=blue!"              + "\nlistening on:\n"
    + "!size=3!!color=green!!hspace=0.7!" + ipAddr
  )
  lcd.show()

  while(1):
    try:
      cl, addr = s.accept()
      print('client connected from', addr)
      request = cl.recv(1024)
      print(request)

      cmdStr = str(request).split()[1].strip('/')
      cmdArr = cmdStr.split("=", 1)
      cmd = cmdArr[0]
      val = None
      if len(cmdArr) == 2:
        val = cmdArr[1]

      if cmd == "clear":
        lcd.fill(0)
        lcd.show()
        print("clear")
      elif cmd == "text" or cmd == "ctext" or cmd == "textbuf" or cmd == "ctextbuf":
        if cmd == "ctext" or cmd == "ctextbuf":
          lcd.fill(0)
        msgBase64 = val
        msgBytesBase64 = msgBase64.encode("utf8")
        msgBytes = base64.b64decode(msgBytesBase64)
        msg = msgBytes.decode("utf8")
        lcdFont.drawMarkup(msg)
        if cmd == "text" or cmd == "ctext":
          lcd.show()
        print("text: " + msg)
      else:
        raise(Exception("ERROR: could not parse payload"))

      cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
      cl.close()

    except Exception as e:
      print(e)
      lcdFont.text("MSG\nFAILED", pxPerDot=5, color=lcd.red)
      cl.send('HTTP/1.1 400 Bad request\r\nContent-Type: text/html\r\n\r\n')
      cl.close()
