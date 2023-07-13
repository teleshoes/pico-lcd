# pico-lcd
# Copyright 2023 Elliot Wolk
# License: GPLv2
import network
import time
import socket
import gc

import base64 #non-standard, must build micropython

from lcd import LCD
from lcdFont import LcdFont

ROTATION = LCD.MODE_ROTATION_NORMAL

LCD_CONF_1_3 = {'width':240, 'height':240, 'rotation':ROTATION}
LCD_CONF_2_0 = {'width':320, 'height':240, 'rotation':ROTATION}

LCD_CONF = LCD_CONF_1_3

if __name__=='__main__':
  lcd = LCD(LCD_CONF['width'], LCD_CONF['height'], LCD_CONF['rotation'])

  lcd.fillShow(lcd.black)

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

  lcd.fillShow(lcd.black)

  lcdFont.markup(""
    + "!size=4!!color=green!"             + "CONNECTED\n"
    + "!size=3!!color=blue!"              + "\nlistening on:\n"
    + "!size=3!!color=green!!hspace=0.7!" + ipAddr
  )
  lcd.show()

  while(1):
    try:
      #something allocates memory that GC is not aware of
      mem = gc.mem_free()
      gc.collect()

      cl, addr = s.accept()
      print('client connected from', addr)
      requestFirstLine = cl.readline()
      requestOther = cl.recv(1024)

      cmdStr = str(requestFirstLine).split()[1].strip('/')
      cmdArr = cmdStr.split("=", 1)
      cmd = cmdArr[0]
      val = None
      if len(cmdArr) == 2:
        val = cmdArr[1]

      if cmd == "clear":
        lcd.fillShow(lcd.black)
        print("clear")
      elif cmd == "show":
        lcd.show()
      elif cmd == "orient" or cmd == "rotation":
        if val == "landscape" or val == "0" or val == "normal" or val == "default":
          lcd.setRotation(LCD.MODE_ROTATION_NORMAL)
        elif val == "portrait" or val == "270" or val == "-90":
          lcd.setRotation(LCD.MODE_ROTATION_ROT270)
        elif val == "inverted-landscape" or val == "180":
          lcd.setRotation(LCD.MODE_ROTATION_ROT180)
        elif val == "inverted-portrait" or val == "90":
          lcd.setRotation(LCD.MODE_ROTATION_ROT90)
      elif cmd == "text" or cmd == "ctext" or cmd == "textbuf" or cmd == "ctextbuf":
        if cmd == "ctext" or cmd == "ctextbuf":
          lcd.fill(lcd.black)
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
      lcdFont.text("MSG\nFAILED", size=5, color=lcd.red)
      cl.send('HTTP/1.1 400 Bad request\r\nContent-Type: text/html\r\n\r\n')
      cl.close()
