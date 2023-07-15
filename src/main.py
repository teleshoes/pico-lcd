# pico-lcd
# Copyright 2023 Elliot Wolk
# License: GPLv2
import network
import time
import socket
import gc
import machine

from lcd import LCD
from lcdFont import LcdFont

LCD_CONF_1_3 = {
  "buttons": {'A':15, 'B':17, 'X':19, 'Y':21,
              'UP':2, 'DOWN':18, 'LEFT':16, 'RIGHT':20, 'CTRL':3},
  "layouts": [
    {'DEG':  0, 'W':240, 'H':240, 'X':  0, 'Y':  0, 'MY':0, 'MX':1, 'MV':1},
    {'DEG': 90, 'W':240, 'H':240, 'X':  0, 'Y':  0, 'MY':0, 'MX':0, 'MV':0},
    {'DEG':180, 'W':240, 'H':240, 'X': 80, 'Y':  0, 'MY':1, 'MX':0, 'MV':1},
    {'DEG':270, 'W':240, 'H':240, 'X':  0, 'Y': 80, 'MY':1, 'MX':1, 'MV':0},
  ],
}
LCD_CONF_2_0 = {
  "buttons": {'B1':15, 'B2':17, 'B3':2, 'B4':3},
  "layouts": [
    {'DEG':  0, 'W':320, 'H':240, 'X':  0, 'Y':  0, 'MY':0, 'MX':1, 'MV':1},
    {'DEG': 90, 'W':240, 'H':320, 'X':  0, 'Y':  0, 'MY':0, 'MX':0, 'MV':0},
    {'DEG':180, 'W':320, 'H':240, 'X':  0, 'Y':  0, 'MY':1, 'MX':0, 'MV':1},
    {'DEG':270, 'W':240, 'H':320, 'X':  0, 'Y':  0, 'MY':1, 'MX':1, 'MV':0},
  ],
}

LCD_CONF = LCD_CONF_1_3


def buttonPressed(pin, btnName, controller):
  #debounce 0.1s
  nowTicks = time.ticks_ms()
  lastPress = controller['btnLastPress'][btnName]
  if lastPress != None and time.ticks_diff(nowTicks, lastPress) < 100:
    return
  controller['btnLastPress'][btnName] = nowTicks

  print("PRESSED: " + btnName + " " + str(pin))
  controller['btnCount'][btnName] += 1

  if btnName == "B2" or btnName == "A":
    controller['lcd'].setRotationNext()
    writeLastRotationDegrees(controller['lcd'].getRotationDegrees())


def main():
  lcd = LCD(LCD_CONF["layouts"])

  degrees = readLastRotationDegrees()
  if degrees != None:
    lcd.setRotationDegrees(degrees)

  lcdFont = LcdFont('font5x8.bin', lcd)
  lcdFont.setup()

  wlan = connectToWifi(lcdFont)

  s = getSocket()

  controller = {
    'btnLastPress': {}, 'btnCount': {},
    'lcd': lcd, 'lcdFont': lcdFont,
    'wlan': wlan, 'socket': s
  }

  for btnName in LCD_CONF['buttons']:
    gpioPin = LCD_CONF['buttons'][btnName]
    controller['btnLastPress'][btnName] = None
    controller['btnCount'][btnName] = 0
    pin = machine.Pin(gpioPin, machine.Pin.IN, machine.Pin.PULL_UP)
    pin.irq(trigger=machine.Pin.IRQ_FALLING, handler=(
      lambda pin, btn=btnName, c=controller: buttonPressed(pin, btn, c)
    ))

  lcd.fillShow(lcd.black)

  lcdFont.markup(""
    + "!size=4!!color=green!"             + "CONNECTED\n"
    + "!size=3!!color=blue!"              + "\nlistening on:\n"
    + "!size=3!!color=green!!hspace=0.7!" + wlan.ifconfig()[0]
  )
  lcd.show()

  while True:
    try:
      #something allocates memory that GC is not aware of
      mem = gc.mem_free()
      gc.collect()

      cl, addr = s.accept()
      print('client connected from', addr)

      (cmd, val) = readCommandRequest(cl)

      out = ""

      if cmd == "clear":
        lcd.fillShow(lcd.black)
        print("clear")
      elif cmd == "show":
        lcd.show()
      elif cmd == "buttons":
        for btnName in sorted(controller['btnCount']):
          if len(out) > 0:
            out += ", "
          out += btnName + "=" + str(controller['btnCount'][btnName])
        out += "\n"
      elif cmd == "orient" or cmd == "rotation":
        degrees = None
        if val == "landscape" or val == "0" or val == "normal" or val == "default":
          degrees = 0
        elif val == "portrait" or val == "270" or val == "-90":
          degrees = 270
        elif val == "inverted-landscape" or val == "180":
          degrees = 180
        elif val == "inverted-portrait" or val == "90":
          degrees = 90

        if degrees != None:
          lcd.setRotationDegrees(degrees)
          writeLastRotationDegrees(lcd.getRotationDegrees())
      elif cmd == "text" or cmd == "ctext" or cmd == "textbuf" or cmd == "ctextbuf":
        print("text: " + val)
        if cmd == "ctext" or cmd == "ctextbuf":
          lcd.fill(lcd.black)
        lcdFont.drawMarkup(val)
        if cmd == "text" or cmd == "ctext":
          lcd.show()
      else:
        raise(Exception("ERROR: could not parse payload"))

      cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n' + out)
      cl.close()

    except Exception as e:
      try:
        print(e)
        lcdFont.text("MSG\nFAILED", size=5, color=lcd.red)
        if cl != None:
          cl.send('HTTP/1.1 400 Bad request\r\nContent-Type: text/html\r\n\r\n')
          cl.close()
      except:
        pass

def readCommandRequest(cl):
  cl.settimeout(0.25)
  start_ms = time.ticks_ms()

  #read content length, skip to POST data
  line = ""
  contentLen = None
  while line != b'\r\n':
    try:
      if line.startswith(b"Content-Length: "):
        lenStr = line[16:]
      contentLen = int(lenStr)
    except Exception as e:
      pass

    try:
      line = cl.readline()
    except:
      line = ""

    if time.ticks_diff(time.ticks_ms(), start_ms) > 5000:
      print("WARNING: max timeout reading from socket exceeded")
      break

  data = b""
  while len(data) < contentLen:
    try:
      chunk = cl.recv(1024)
    except:
      chunk = None
    if chunk != None:
      data += chunk
    if time.ticks_diff(time.ticks_ms(), start_ms) > 5000:
      print("WARNING: max timeout reading from socket exceeded")
      break

  cmdArr = data.split(b'=', 1)
  cmd = cmdArr[0].decode("utf8")
  val = None
  if len(cmdArr) == 2:
    val = cmdArr[1].decode("utf8")

  return (cmd, val)

def readLastRotationDegrees():
  return readFileInt("last-rotation-degrees.txt")
def writeLastRotationDegrees(degrees):
  writeFile("last-rotation-degrees.txt", str(degrees) + "\n")

def readFileInt(file):
  try:
    with open(file, "r") as fh:
      return int(fh.readline())
  except:
    return None

def writeFile(file, contents):
  try:
    with open(file, "w") as fh:
      fh.write(contents)
  except:
    pass

def connectToWifi(lcdFont):
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

  wlan = network.WLAN(network.STA_IF)
  wlan.active(True)

  while not connected:
    for ssidPassword in networks:
      ssid = ssidPassword[0]
      password = ssidPassword[1]

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
  return wlan

def getSocket():
  addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]

  s = socket.socket()
  s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  s.bind(addr)
  s.listen(1)

  print('listening on', addr)
  return s

if __name__=='__main__':
  main()
