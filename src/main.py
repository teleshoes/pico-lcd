# pico-lcd
# Copyright 2023 Elliot Wolk
# License: GPLv2
import network
import time
import socket
import gc
import machine
import sys

from rtc import RTC_DS3231
from lcd import LCD, FramebufConf
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
    'socket': None,
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

  controller['socket'] = getSocket()

  setupWifi(controller['lcdFont'])

  (timeoutS, timeoutText) = readTimeoutFile()

  rtc = RTC_DS3231()

  while True:
    try:
      #something allocates memory that GC is not aware of
      gc.collect()

      #positive is blocking+timeout, 0 is non-blocking, None is blocking
      if timeoutS != None and timeoutS > 0:
        controller['socket'].settimeout(timeoutS)
      else:
        controller['socket'].settimeout(None)

      try:
        cl, addr = controller['socket'].accept()
        print('client connected from', addr)
      except:
        print("SOCKET TIMEOUT (" + str(timeoutS) + "s)\n")
        if timeoutText == None:
          timeoutText = "TIMEOUT"
        rtcEpoch = None
        #only fetch RTC epoch and timezone if markup looks like it might want it
        if rtc != None and "!rtc" in timeoutText:
          rtcEpoch = rtc.getTimeEpoch()
          rtcEpoch = adjustRTCEpochWithTZOffset(rtcEpoch)
        controller['lcd'].fill(controller['lcd'].black)
        controller['lcdFont'].drawMarkup(timeoutText, rtcEpoch=rtcEpoch)
        controller['lcd'].show()
        continue

      (cmd, params, data) = readCommandRequest(cl)

      out = ""

      if cmd == "info":
        if controller['lcd'].is_framebuf_enabled():
          (winX, winY) = controller['lcd'].get_framebuf_size()
        else:
          (winX, winY) = (controller['lcd'].get_width(), controller['lcd'].get_height())
        (charX, charY) = controller['lcdFont'].getCharGridSize(1)

        out += "window: %sx%s\n" % (
          winX,
          winY)
        out += "  (lcd: %sx%s, framebuf: %s)\n" % (
          controller['lcd'].get_width(),
          controller['lcd'].get_height(),
          controller['lcd'].get_framebuf_conf())
        out += "orientation: %s degrees\n" % (
          controller['lcd'].get_rotation_degrees())
        out += "RAM free: %s bytes\n" % (
          gc.mem_free())
        out += "buttons: %s\n" % (
          formatButtonCount(controller['buttons']))
        out += "char8px: %sx%s\n" % (
          charX,
          charY)
      elif cmd == "connect":
        setupWifi(controller['lcdFont'])
      elif cmd == "ssid":
        ssid = maybeGetParamStr(params, "ssid", None)
        password = maybeGetParamStr(params, "password", None)
        if ssid != None and password != None:
          appendSSID(ssid, password)
          out = "added wifi network:\n ssid=" + ssid +"\n password=" + password + "\n"
        else:
          out = "ERROR: missing ssid or password\n"
      elif cmd == "resetwifi":
        writeFile("wifi-conf.txt", "")
        out = "WARNING: all wifi networks removed for next boot\n"
        print(out)
      elif cmd == "timeout":
        timeoutS = maybeGetParamInt(params, "timeoutS", None)
        timeoutText = data.decode("utf8")
        print("timeout: " + str(timeoutS) + "s = " + str(timeoutText))
        writeTimeoutFile(timeoutS, timeoutText)
      elif cmd == "tz":
        tzName = maybeGetParamStr(params, "name", None)
        writeTZFile(tzName)
        print("set timezone for rtc = " + tzName)
      elif cmd == "rtc":
        #epoch param must be in seconds since midnight 1970-01-01 UTC
        epoch = maybeGetParamInt(params, "epoch", None)
        if rtc == None:
          out = "NO RTC"
        elif epoch != None:
          rtc.setTimeEpoch(epoch)
          out += "SET RTC=" + str(rtc.getTimeEpoch()) + "\n"
        out += "RTC EPOCH=" + str(rtc.getTimeEpoch()) + "\n"
        out += "RTC ISO=" + str(rtc.getTimeISO()) + "\n"
      elif cmd == "clear":
        print("clear")
        controller['lcd'].fill_mem_blank()
      elif cmd == "show":
        print("show")
        controller['lcd'].show()
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
      elif cmd == "orient" or cmd == "rotation":
        orient = maybeGetParamStr(params, "orient", None)
        print("orient=" + orient)

        out = setOrientation(controller['lcd'], orient)
      elif cmd == "framebuf":
        fbConf = maybeGetParamFramebufConf(params, "framebuf", None)
        print("framebuf=" + str(fbConf))
        out = setFramebuf(controller['lcd'], fbConf)
      elif cmd == "text":
        isClear = maybeGetParamBool(params, "clear", True)
        isShow = maybeGetParamBool(params, "show", True)
        fbConf = maybeGetParamFramebufConf(params, "framebuf", None)
        orient = maybeGetParamStr(params, "orient", None)
        markup = data.decode("utf8")

        print("text: " + markup)

        if orient != None:
          out += setOrientation(controller['lcd'], orient)
        if fbConf != None:
          out += setFramebuf(controller['lcd'], fbConf)

        rtcEpoch = None
        #only fetch RTC epoch and timezone if markup looks like it might want it
        if rtc != None and "!rtc" in markup:
          rtcEpoch = rtc.getTimeEpoch()
          rtcEpoch = adjustRTCEpochWithTZOffset(rtcEpoch)

        if isClear:
          controller['lcd'].fill(controller['lcd'].black)
        controller['lcdFont'].drawMarkup(markup, rtcEpoch=rtcEpoch)
        if isShow:
          controller['lcd'].show()
      else:
        raise(Exception("ERROR: could not parse payload"))

      cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n' + out)
      cl.close()

    except Exception as e:
      try:
        sys.print_exception(e)
        controller['lcdFont'].text("MSG\nFAILED", size=5, color=controller['lcd'].red)
        if cl != None:
          cl.send('HTTP/1.1 400 Bad request\r\nContent-Type: text/html\r\n\r\n')
          cl.close()
      except:
        pass

def adjustRTCEpochWithTZOffset(rtcEpoch):
  tzName = readTZFile()
  if rtcEpoch != None and tzName != None:
    foundOffset = None
    tzCsvFile = "zoneinfo" + "/" + tzName + ".csv"
    try:
      with open(tzCsvFile, "r") as fh:
        for line in fh:
          cols = line.split(',')
          if len(cols) == 2:
            (offsetStartEpochStr, offsetSecondsStr) = cols
            offsetStartEpoch = int(offsetStartEpochStr)
            offsetSeconds = int(offsetSecondsStr)
            if offsetStartEpoch >= rtcEpoch:
              foundOffset = offsetSeconds
              break
    except:
      print("WARNING: failed to set offset from timezone\n")
      foundOffset = None
    if foundOffset != None:
      rtcEpoch += foundOffset
  return rtcEpoch

def createLCD(lcdName):
  layouts = LCD_CONFS[lcdName]["layouts"]
  lcd = LCD(layouts)
  msg = "LCD init\n"

  msg += setFramebuf(lcd, readLastFramebufConf()) + "\n"
  msg += setOrientation(lcd, str(readLastRotationDegrees())) + "\n"

  print(msg)

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


def setOrientation(lcd, orient):
  degrees = None
  if orient == None:
    degrees = 0
  elif orient == "landscape" or orient == "0" or orient == "normal" or orient == "default":
    degrees = 0
  elif orient == "portrait" or orient == "270" or orient == "-90":
    degrees = 270
  elif orient == "inverted-landscape" or orient == "180":
    degrees = 180
  elif orient == "inverted-portrait" or orient == "90":
    degrees = 90

  if degrees != None:
    lcd.set_rotation_degrees(degrees)
    writeLastRotationDegrees(lcd.get_rotation_degrees())
    return "orient=" + str(degrees) + "\n"
  else:
    return "unknown orient " + str(orient) + "\n"

def setFramebuf(lcd, fbConf):
  #  'framebuf' param is one of:
  #     on | enabled | true
  #       enable framebuf, with no max WxH or X/Y offsets
  #     off | disabled | false
  #       disable framebuf
  #     WxH
  #       enable framebuf, and set max WxH with no X/Y offsets
  #     WxH+X+Y
  #       enable framebuf, and set max WxH and X/Y offsets
  #
  #NOTE: regardless of current orientation:
  #  W and X always refers to the larger physical dimension of the LCD
  #  H and Y always refers to the smaller physical dimension of the LCD

  if fbConf == None:
    fbConf = FramebufConf(enabled=False)

  lcd.set_framebuf_conf(fbConf)
  # get the actual framebuf conf of the LCD (might have failed due to OOM)
  fbConf = lcd.get_framebuf_conf()
  writeLastFramebufConf(fbConf)
  return "framebuf: " + str(fbConf) + "\n"


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

def maybeGetParamFramebufConf(params, paramName, defaultValue=None):
  val = maybeGetParamStr(params, paramName, None)
  if val == None:
    return defaultValue
  else:
    fbConf = FramebufConf.parseFramebufConfStr(val)
    if fbConf == None:
      return defaultValue
    else:
      return fbConf

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
  return FramebufConf.parseFramebufConfStr(val)
def writeLastFramebufConf(fbConf):
  writeFile("last-framebuf-conf.txt", str(fbConf) + "\n")

def readTimeoutFile():
  val = readFileLine("timeout.txt")
  if val != None:
    val = val.strip()
    segments = val.split(",")
    if len(segments) == 2:
      timeoutS = int(segments[0])
      timeoutText = segments[1]
      return (timeoutS, timeoutText)
  return (None, None)
def writeTimeoutFile(timeoutS, timeoutText):
  if timeoutS == None or timeoutText == None:
    writeFile("timeout.txt", "")
  else:
    writeFile("timeout.txt", str(timeoutS) + "," + timeoutText + "\n")

def readTZFile():
  val =  readFileLine("current_tz")
  if val != None:
    val = val.strip()
  return val
def writeTZFile(tzName):
  if tzName == None:
    os.remove("current_tz")
  else:
    writeFile("current_tz", tzName + "\n")

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

def setupWifi(lcdFont):
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
    return setupAccessPoint(lcdFont)
  else:
    print('connected')
    ip = wlan.ifconfig()[0]
    print('ip=' + ip)
    lcdFont.markup(""
      + "!size=4!!color=green!"             + "CONNECTED\n"
      + "!size=3!!color=blue!"              + "\nlistening on:\n"
      + "!size=3!!color=green!!hspace=0.7!" + ip + "\n"
    )

def setupAccessPoint(lcdFont):
  ssid = "pico-lcd"
  password = "123456789"

  lcdFont.markup(""
    + "!size=4!!color=green!" + "TURNING ON\n"
    + "!size=4!!color=green!" + "WIFI AP\n"
    + "!size=4!!color=white!" + "--------\n"
    + "!size=2!!color=blue!"  + ssid
  )
  wlan = network.WLAN(network.AP_IF)
  wlan.config(essid=ssid, password=password)
  wlan.active(True)

  max_wait = 30
  while max_wait > 0:
    if wlan.active:
      break
    max_wait -= 1
    print('waiting for connection...')
    time.sleep(1)

  if not wlan.active:
    lcdFont.markup("!size=7!!color=red!" + "FAILED\nWIFI")
    raise RuntimeError('network connection failed')

  print("AP active: ssid=" + ssid + " password=" + password)
  print(wlan.ifconfig())

  ip = wlan.ifconfig()[0]

  lcdFont.markup(""
    + "!size=2!!color=green!"             + "SSID:\n"
    + "!size=2!!color=white!"             + ssid + "\n"
    + "!size=2!!color=green!"             + "PASSWORD:\n"
    + "!size=2!!color=white!"             + password + "\n"
    + "!size=2!!color=blue!"              + "IP:\n"
    + "!size=2!!color=green!!hspace=0.7!" + ip + "\n"
    + "!size=1!!color=white!"             + "e.g.:\n"
    + "!size=1!!color=white!"             + "curl 'http://" + ip + "/ssid?\nssid=MY_NETWORK&password=P4SSW0RD'\n"
  )


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
