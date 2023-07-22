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

LCD_CONFS = {
  "1_3": {
    "buttons": {'A':15, 'B':17, 'X':19, 'Y':21,
                'UP':2, 'DOWN':18, 'LEFT':16, 'RIGHT':20, 'CTRL':3},
    "layouts": [
      {'DEG':  0, 'W':240, 'H':240, 'X':  0, 'Y':  0, 'MY':0, 'MX':1, 'MV':1},
      {'DEG': 90, 'W':240, 'H':240, 'X':  0, 'Y':  0, 'MY':0, 'MX':0, 'MV':0},
      {'DEG':180, 'W':240, 'H':240, 'X': 80, 'Y':  0, 'MY':1, 'MX':0, 'MV':1},
      {'DEG':270, 'W':240, 'H':240, 'X':  0, 'Y': 80, 'MY':1, 'MX':1, 'MV':0},
    ],
  },
  "2_0": {
    "buttons": {'B1':15, 'B2':17, 'B3':2, 'B4':3},
    "layouts": [
      {'DEG':  0, 'W':320, 'H':240, 'X':  0, 'Y':  0, 'MY':0, 'MX':1, 'MV':1},
      {'DEG': 90, 'W':240, 'H':320, 'X':  0, 'Y':  0, 'MY':0, 'MX':0, 'MV':0},
      {'DEG':180, 'W':320, 'H':240, 'X':  0, 'Y':  0, 'MY':1, 'MX':0, 'MV':1},
      {'DEG':270, 'W':240, 'H':320, 'X':  0, 'Y':  0, 'MY':1, 'MX':1, 'MV':0},
    ],
  },
}

DEFAULT_LCD_NAME = "1_3"

def buttonPressedActions(btnName, controller):
  if btnName == "B2" or btnName == "A":
    controller['lcd'].set_rotation_next()
    writeLastRotationDegrees(controller['lcd'].get_rotation_degrees())


def main():
  controller = {
    'lcdName': None, 'lcd': None, 'lcdFont': None,
    'wlan': None, 'socket': None,
    'buttons': None,
  }

  lcdName = readLastLCDName()
  if lcdName == None:
    lcdName = DEFAULT_LCD_NAME

  controller['lcdName'] = lcdName
  controller['lcd'] = createLCD(controller['lcdName'])
  controller['buttons'] = createButtons(controller['lcdName'])
  addButtonHandlers(controller['buttons'], controller)

  controller['lcdFont'] = LcdFont('font5x8.bin', controller['lcd'])
  controller['lcdFont'].setup()

  controller['wlan'] = connectToWifi(controller['lcdFont'])

  controller['socket'] = getSocket()

  controller['lcd'].fill_show(controller['lcd'].black)

  controller['lcdFont'].markup(""
    + "!size=4!!color=green!"             + "CONNECTED\n"
    + "!size=3!!color=blue!"              + "\nlistening on:\n"
    + "!size=3!!color=green!!hspace=0.7!" + controller['wlan'].ifconfig()[0]
  )
  controller['lcd'].show()

  while True:
    try:
      #something allocates memory that GC is not aware of
      mem = gc.mem_free()
      gc.collect()

      cl, addr = controller['socket'].accept()
      print('client connected from', addr)

      (cmd, params, data) = readCommandRequest(cl)

      out = ""

      if cmd == "info":
        if controller['lcd'].framebufEnabled:
          (winX, winY) = controller['lcd'].get_framebuf_size()
        else:
          (winX, winY) = (controller['lcd'].get_width(), controller['lcd'].get_height())
        (charX, charY) = controller['lcdFont'].getCharGridSize(1)

        out += "window: %sx%s\n" % (
          winX,
          winY)
        out += "  (lcd: %sx%s, framebuf: enabled=%s maxW=%s maxH=%s x=%s y=%s)\n" % (
          controller['lcd'].get_width(),
          controller['lcd'].get_height(),
          controller['lcd'].framebufEnabled,
          controller['lcd'].framebufMaxWidth,
          controller['lcd'].framebufMaxHeight,
          controller['lcd'].framebufOffsetX,
          controller['lcd'].framebufOffsetY)
        out += "orientation: %s degrees\n" % (
          controller['lcd'].get_rotation_degrees())
        out += "RAM free: %s bytes\n" % (
          gc.mem_free())
        out += "buttons: %s\n" % (
          formatButtonCount(controller['buttons']))
        out += "char8px: %sx%s\n" % (
          charX,
          charY)
      elif cmd == "clear":
        print("clear")
        controller['lcd'].fill_mem_blank()
      elif cmd == "show":
        print("show")
        controller['lcd'].show()
      elif cmd == "ssid":
        ssid = maybeGetParamStr(params, "ssid", None)
        password = maybeGetParamStr(params, "password", None)
        if ssid != None and password != None:
          appendSSID(ssid, password)
          out = "added wifi network:\n ssid=" + ssid +"\n password=" + password + "\n"
        else:
          out = "ERROR: missing ssid or password\n"
      elif cmd == "buttons":
        print("buttons")
        out = formatButtonCount(controller['buttons']) + "\n"
      elif cmd == "fill":
        print("fill")
        colorName = maybeGetParamStr(params, "color", None)
        color = controller['lcd'].get_color_by_name(colorName)
        if color == None:
          out = "ERROR: could not parse color " + colorName + "\n"
        else:
          controller['lcd'].fill(color)
          controller['lcd'].show()
      elif cmd == "lcd":
        name = maybeGetParamStr(params, "name", None)
        if name in LCD_CONFS:
          removeButtonHandlers(controller['buttons'])

          controller['lcdName'] = name
          controller['lcd'] = createLCD(controller['lcdName'])
          controller['buttons'] = createButtons(controller['lcdName'])
          addButtonHandlers(controller['buttons'], controller)

          controller['lcdFont'].setLCD(controller['lcd'])
          writeLastLCDName(name)
      elif cmd == "framebuf":
        #NOTE: regardless of current orientation:
        #  'maxwidth' and 'x' refers to the largest physical dimension
        #  'maxheight' and 'y' refers to the smallest physical dimension

        enabled = maybeGetParamBool(params, "enabled", True)
        maxW = maybeGetParamInt(params, "maxwidth", None)
        maxH = maybeGetParamInt(params, "maxheight", None)
        offsetX = maybeGetParamInt(params, "x", None)
        offsetY = maybeGetParamInt(params, "y", None)
        if maxW == 0:
          maxW = None
        if maxH == 0:
          maxH = None
        if offsetX == 0:
          offsetX = None
        if offsetY == 0:
          offsetY = None
        controller['lcd'].set_framebuf_enabled(enabled, maxW, maxH, offsetX, offsetY)
        writeLastFramebufConf(
          controller['lcd'].framebufEnabled,
          controller['lcd'].framebufMaxWidth,
          controller['lcd'].framebufMaxHeight,
          controller['lcd'].framebufOffsetX,
          controller['lcd'].framebufOffsetY)
        out = "framebuf: enabled=%s maxW=%s maxH=%s x=%s y=%s\n" % (
          controller['lcd'].framebufEnabled,
          controller['lcd'].framebufMaxWidth,
          controller['lcd'].framebufMaxHeight,
          controller['lcd'].framebufOffsetX,
          controller['lcd'].framebufOffsetY)
      elif cmd == "orient" or cmd == "rotation":
        val = maybeGetParamStr(params, "orient", None)
        print("orient=" + val)

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
          controller['lcd'].set_rotation_degrees(degrees)
          writeLastRotationDegrees(controller['lcd'].get_rotation_degrees())
          out = "orient=" + str(degrees) + "\n"
        else:
          out = "unknown orient " + val + "\n"
      elif cmd == "text":
        markup = data.decode("utf8")
        print("text: " + markup)

        isClear = True
        if "clear" in params and params["clear"].lower() == "false":
          isClear = False

        isShow = True
        if "show" in params and params["show"].lower() == "false":
          isShow = False
        if isClear:
          controller['lcd'].fill(controller['lcd'].black)
        controller['lcdFont'].drawMarkup(markup)
        if isShow:
          controller['lcd'].show()
      else:
        raise(Exception("ERROR: could not parse payload"))

      cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n' + out)
      cl.close()

    except Exception as e:
      try:
        print(e)
        controller['lcdFont'].text("MSG\nFAILED", size=5, color=controller['lcd'].red)
        if cl != None:
          cl.send('HTTP/1.1 400 Bad request\r\nContent-Type: text/html\r\n\r\n')
          cl.close()
      except:
        pass

def createLCD(lcdName):
  layouts = LCD_CONFS[lcdName]["layouts"]
  lcd = LCD(layouts)
  (enabled, maxW, maxH, offsetX, offsetY) = readLastFramebufConf()
  lcd.set_framebuf_enabled(enabled, maxW, maxH, offsetX, offsetY)
  print("LCD init")
  print("framebuf: enabled=%s maxW=%s maxH=%s x=%s y=%s\n" % (
    lcd.framebufEnabled,
    lcd.framebufMaxWidth,
    lcd.framebufMaxHeight,
    lcd.framebufOffsetX,
    lcd.framebufOffsetY))

  degrees = readLastRotationDegrees()
  if degrees != None:
    lcd.set_rotation_degrees(degrees)
  return lcd

def createButtons(lcdName):
  buttons = {'pins': {}, 'lastPress': {}, 'count': {}}

  lcdConf = LCD_CONFS[lcdName]
  for btnName in lcdConf['buttons']:
    gpioPin = lcdConf['buttons'][btnName]
    buttons['lastPress'][btnName] = None
    buttons['count'][btnName] = 0
    buttons['pins'][btnName] = machine.Pin(gpioPin, machine.Pin.IN, machine.Pin.PULL_UP)

  return buttons

def addButtonHandlers(buttons, controller):
  if buttons != None:
    for btnName in buttons['pins']:
      pin = buttons['pins'][btnName]
      pin.irq(trigger=machine.Pin.IRQ_FALLING, handler=(
        lambda pin, btn=btnName, c=controller: buttonPressedHandler(pin, btn, c)
      ))

def buttonPressedHandler(pin, btnName, controller):
  #debounce 0.25s
  nowTicks = time.ticks_ms()
  lastPress = controller['buttons']['lastPress'][btnName]
  if lastPress != None:
    diff = time.ticks_diff(nowTicks, lastPress)
    if diff < 250:
      return
  controller['buttons']['lastPress'][btnName] = nowTicks

  print("PRESSED: " + btnName + " " + str(pin))
  controller['buttons']['count'][btnName] += 1

  buttonPressedActions(btnName, controller)

def removeButtonHandlers(buttons):
  if buttons != None:
    for btnName in buttons['pins']:
      pin = buttons['pins'][btnName]
      pin.irq(handler=None)

def formatButtonCount(buttons):
  fmt = ""
  for btnName in sorted(buttons['count']):
    if len(fmt) > 0:
      fmt += ", "
    fmt += btnName + "=" + str(buttons['count'][btnName])
  return fmt

def maybeGetParamStr(params, paramName, defaultValue=None):
  if paramName in params:
    return params[paramName]
  else:
    return defaultValue

def maybeGetParamBool(params, paramName, defaultValue=None):
  val = maybeGetParamStr(params, paramName, None)
  if val == None:
    return defaultValue
  elif val.lower() == "true":
    return True
  elif val.lower() == "false":
    return False
  else:
    print("WARNING: could not parse bool param " + paramName + "=" + val + "\n")
    return defaultValue

def maybeGetParamInt(params, paramName, defaultValue=None):
  val = maybeGetParamStr(params, paramName, None)
  if val == None:
    return defaultValue
  else:
    try:
      return int(val)
    except:
      print("WARNING: could not parse int param " + paramName + "=" + val + "\n")
      return defaultValue

def readCommandRequest(cl):
  cl.settimeout(0.25)
  start_ms = time.ticks_ms()

  #read URL params + content length, skip to POST data
  line = ""
  contentLen = 0
  cmd = None
  params = {}
  while line != b'\r\n':
    if line.startswith("POST /") or line.startswith("GET /"):
      segments = line.decode("utf8").split(" ")
      urlStr = segments[1]
      urlStr = urlStr[1:] #remove /
      cmdParamsStr = urlStr.split("?")
      if len(cmdParamsStr) == 2:
        cmd = cmdParamsStr[0]
        paramsStr = cmdParamsStr[1]
      elif len(cmdParamsStr) == 1:
        cmd = cmdParamsStr[0]
        paramsStr = ""
      for keyValPair in paramsStr.split("&"):
        keyVal = keyValPair.split("=")
        if len(keyVal) == 2:
          (key, val) = keyVal
          params[keyVal[0]] = keyVal[1]
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

  return (cmd, params, data)

def appendSSID(ssid, password):
  try:
    with open("wifi-conf.txt", "a") as fh:
      fh.write(ssid + " = " + password + "\n")
  except:
    pass

def readLastLCDName():
  val = readFileLine("last-lcd-name.txt")
  if val != None:
    val = val.strip()
  if val in LCD_CONFS:
    return val
def writeLastLCDName(lcdName):
  writeFile("last-lcd-name.txt", lcdName + "\n")

def readLastRotationDegrees():
  return readFileInt("last-rotation-degrees.txt")
def writeLastRotationDegrees(degrees):
  writeFile("last-rotation-degrees.txt", str(degrees) + "\n")

def readLastFramebufConf():
  val = readFileLine("last-framebuf-conf.txt")
  (maxW, maxH, offsetX, offsetY) = (0, 0, 0, 0)
  enabled = True
  if val != None:
    arr = val.split(" ")
    if len(arr) == 5:
      enabledStr = arr[0]
      if enabledStr == "true":
        enabled = True
      elif enabledStr == "false":
        enabled = False
      else:
        enabled = True

      try:
        (maxW, maxH, offsetX, offsetY) = (int(arr[1]), int(arr[2]), int(arr[3]), int(arr[4]))
      except:
        (maxW, maxH, offsetX, offsetY) = (0, 0, 0, 0)
  if maxW == 0:
    maxW = None
  if maxH == 0:
    maxH = None
  if offsetX == 0:
    offsetX = None
  if offsetY == 0:
    offsetY = None
  return (enabled, maxW, maxH, offsetX, offsetY)
def writeLastFramebufConf(enabled, maxW, maxH, offsetX, offsetY):
  if maxW == None:
    maxW = 0
  if maxH == None:
    maxH = 0
  if offsetX == None:
    offsetX = 0
  if offsetY == None:
    offsetY = 0
  fbConfFmt = str(enabled).lower()
  fbConfFmt += " " + str(maxW)
  fbConfFmt += " " + str(maxH)
  fbConfFmt += " " + str(offsetX)
  fbConfFmt += " " + str(offsetY)
  writeFile("last-framebuf-conf.txt", fbConfFmt + "\n")

def readFileInt(file):
  try:
    return int(readFileLine(file))
  except:
    return None

def readFileLine(file):
  try:
    with open(file, "r") as fh:
      return fh.readline()
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
