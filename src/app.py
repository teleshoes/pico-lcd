# pico-lcd
# Copyright 2023 Elliot Wolk
# License: GPLv2
import network
import os
import time
import socket
import gc
import machine
import sys

import doc
from rtc import RTC_DS3231
from lcd import LCD, FramebufConf
from lcdFont import LcdFont

LCD_CONFS = {
  doc.LCD_NAME_1_3: {
    "buttons": {'A':15, 'B':17, 'X':19, 'Y':21,
                'UP':2, 'DOWN':18, 'LEFT':16, 'RIGHT':20, 'CTRL':3},
    "landscapeWidth":  240,
    "landscapeHeight": 240,
    "rotationLayouts": [
      {'DEG':  0, 'LANDSCAPE': True,  'X':  0, 'Y':  0, 'MY':0, 'MX':1, 'MV':1},
      {'DEG': 90, 'LANDSCAPE': False, 'X':  0, 'Y':  0, 'MY':0, 'MX':0, 'MV':0},
      {'DEG':180, 'LANDSCAPE': True,  'X': 80, 'Y':  0, 'MY':1, 'MX':0, 'MV':1},
      {'DEG':270, 'LANDSCAPE': False, 'X':  0, 'Y': 80, 'MY':1, 'MX':1, 'MV':0},
    ],
  },
  doc.LCD_NAME_2_0: {
    "buttons": {'B1':15, 'B2':17, 'B3':2, 'B4':3},
    "landscapeWidth":  320,
    "landscapeHeight": 240,
    "rotationLayouts": [
      {'DEG':  0, 'LANDSCAPE': True,  'X':  0, 'Y':  0, 'MY':0, 'MX':1, 'MV':1},
      {'DEG': 90, 'LANDSCAPE': False, 'X':  0, 'Y':  0, 'MY':0, 'MX':0, 'MV':0},
      {'DEG':180, 'LANDSCAPE': True,  'X':  0, 'Y':  0, 'MY':1, 'MX':0, 'MV':1},
      {'DEG':270, 'LANDSCAPE': False, 'X':  0, 'Y':  0, 'MY':1, 'MX':1, 'MV':0},
    ],
  },
}

DEFAULT_LCD_NAME = doc.LCD_NAME_2_0

STATE_FILE_WIFI_CONF = "wifi-conf.txt"
STATE_FILE_LCD_NAME = "last-lcd-name.txt"
STATE_FILE_ORIENTATION = "last-rotation-degrees.txt"
STATE_FILE_FRAMEBUF = "last-framebuf-conf.txt"
STATE_FILE_TIMEOUT = "timeout.txt"
STATE_FILE_TIMEZONE = "current_tz"

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

  (prevTimeoutMillis, prevTimeoutText) = readTimeoutFile()
  controller['timeoutMillis'] = prevTimeoutMillis
  controller['timeoutText'] = prevTimeoutText

  controller['rtc'] = RTC_DS3231()
  try:
    controller['rtc'].getTimeEpoch()
  except OSError as e:
    if e.errno == 5:
      #I/O error in I2C, probably no DS3231 device
      controller['rtc'] = None


  cmdFunctionsByName = {}
  symDict = globals()
  for cmd in doc.getAllCommands():
    for symName in symDict:
      if symName.lower() == "cmd" + cmd['name']:
        cmdFunctionsByName[cmd['name']] = symDict[symName]
        break
    if not cmdFunctionsByName[cmd['name']]:
      raise RuntimeError("ERROR: no function defined for cmd " + cmd['name'])

  while True:
    try:
      #something allocates memory that GC is not aware of
      gc.collect()

      #positive is blocking+timeout, 0 is non-blocking, None is blocking
      if controller['timeoutMillis'] != None and controller['timeoutMillis'] > 0:
        controller['socket'].settimeout(controller['timeoutMillis']/1000.0)
      else:
        controller['socket'].settimeout(None)

      try:
        cl, addr = controller['socket'].accept()
        print('client connected from', addr)
      except:
        print("SOCKET TIMEOUT (" + str(controller['timeoutMillis']) + "ms)\n")
        if controller['timeoutText'] == None:
          controller['timeoutText'] = "TIMEOUT"
        rtcEpoch = None
        #only fetch RTC epoch and timezone if markup looks like it might want it
        if controller['rtc'] != None and "!rtc" in controller['timeoutText']:
          rtcEpoch = controller['rtc'].getTimeEpoch()
          rtcEpoch = adjustRTCEpochWithTZOffset(rtcEpoch)
        controller['lcd'].fill(controller['lcd'].black)
        controller['lcdFont'].drawMarkup(controller['timeoutText'], rtcEpoch=rtcEpoch)
        controller['lcd'].show()
        continue

      (cmdName, params, data) = readCommandRequest(cl)

      if cmdName in cmdFunctionsByName:
        print('cmd: ' + cmdName)
        cmdFunction = cmdFunctionsByName[cmdName]
        out = cmdFunction(controller, params, data)
      else:
        raise(Exception("ERROR: could not parse cmdName in payload"))

      if out == None:
        out = ""

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

#####
#####

def cmdInfo(controller, params, data):
  (winW, winH) = controller['lcd'].get_target_window_size()
  (lcdW, lcdH) = controller['lcd'].get_lcd_rotated_size()
  fbConf = controller['lcd'].get_framebuf_conf()

  (charW, charH) = controller['lcdFont'].getCharGridSize(1)

  fbConfBootState = readLastFramebufConf()
  tz = readTZFile()

  out = ""
  out += "window: %sx%s\n" % (winW, winH)
  out += "  (lcd: %sx%s, framebuf: %s)\n" % (lcdW, lcdH, fbConf)
  out += "char8px: %sx%s\n" % (charW, charH)
  out += "orientation: %s degrees\n" % (
    controller['lcd'].get_rotation_degrees())
  out += "RAM free: %s bytes\n" % (
    gc.mem_free())
  out += "buttons: %s\n" % (
    formatButtonCount(controller['buttons']))
  out += "lcdconf: %s\n" % controller['lcdName']
  out += "framebuf-boot: %s\n" % fbConfBootState
  out += "timeout-millis: %s\n" % controller['timeoutMillis']
  out += "timeout-text: %s\n" % controller['timeoutText']
  out += "timezone: %s\n" % tz
  out += "firmware: %s\n" % os.uname().version
  out += "board: %s\n" % os.uname().machine
  return out

def cmdConnect(controller, params, data):
  setupWifi(controller['lcdFont'])
  return None

def cmdSSID(controller, params, data):
  ssid = maybeGetParamStr(params, "ssid", None)
  password = maybeGetParamStr(params, "password", None)
  if ssid != None and password != None:
    appendSSID(ssid, password)
    out = "added wifi network:\n ssid=" + ssid +"\n password=" + password + "\n"
  else:
    out = "ERROR: missing ssid or password\n"
  return out

def cmdResetWifi(controller, params, data):
  writeFile(STATE_FILE_WIFI_CONF, "")
  out = "WARNING: all wifi networks removed for next boot\n"
  return out

def cmdTimeout(controller, params, data):
  timeoutMillis = maybeGetParamInt(params, "timeoutMillis", None)
  timeoutText = data.decode("utf8")
  print("timeout: " + str(timeoutMillis) + "ms = " + str(timeoutText))
  writeTimeoutFile(timeoutMillis, timeoutText)
  if timeoutMillis == None or timeoutMillis == 0:
    controller['timeoutMillis'] = None
    controller['timeoutText'] = None
  else:
    controller['timeoutMillis'] = timeoutMillis
    controller['timeoutText'] = timeoutText
  return None

def cmdTZ(controller, params, data):
  tzName = maybeGetParamStr(params, "name", None)
  writeTZFile(tzName)
  print("set timezone for rtc = " + str(tzName))
  return None

def cmdRTC(controller, params, data):
  #epoch param must be in seconds since midnight 1970-01-01 UTC
  epoch = maybeGetParamInt(params, "epoch", None)
  out = ""
  if controller['rtc'] == None:
    out += "NO RTC"
  elif epoch != None:
    controller['rtc'].setTimeEpoch(epoch)
    out += "SET RTC=" + str(controller['rtc'].getTimeEpoch()) + "\n"
  out += "RTC EPOCH=" + str(controller['rtc'].getTimeEpoch()) + "\n"
  out += "RTC ISO=" + str(controller['rtc'].getTimeISO()) + "\n"
  return out

def cmdClear(controller, params, data):
  controller['lcd'].fill_mem_blank()
  return None

def cmdShow(controller, params, data):
  controller['lcd'].show()
  return None

def cmdButtons(controller, params, data):
  return formatButtonCount(controller['buttons']) + "\n"

def cmdFill(controller, params, data):
  colorName = maybeGetParamStr(params, "color", None)
  color = controller['lcd'].get_color_by_name(colorName)
  out = ""
  if color == None:
    out = "ERROR: could not parse color " + colorName + "\n"
  else:
    controller['lcd'].fill(color)
    controller['lcd'].show()
  return out

def cmdLCD(controller, params, data):
  name = maybeGetParamStr(params, "name", None)
  if name in LCD_CONFS:
    removeButtonHandlers(controller['buttons'])

    controller['lcdName'] = name
    controller['lcd'] = createLCD(controller['lcdName'])
    controller['buttons'] = createButtons(controller['lcdName'])
    addButtonHandlers(controller['buttons'], controller)

    controller['lcdFont'].setLCD(controller['lcd'])
    writeLastLCDName(name)
  else:
    raise ValueError("ERROR: missing LCD param 'name'\n")
  return None

def cmdOrient(controller, params, data):
  orient = maybeGetParamStr(params, "orient", None)
  print("orient=" + orient)

  return setOrientation(controller['lcd'], orient)

def cmdFramebuf(controller, params, data):
  fbConfStr = maybeGetParamStr(params, "framebuf", None)
  fbConf = FramebufConf.parseFramebufConfStr(
    fbConfStr,
    controller['lcd'].get_lcd_landscape_width(),
    controller['lcd'].get_lcd_landscape_height())
  print("framebuf=" + str(fbConf))
  return setFramebuf(controller['lcd'], fbConf)

def cmdText(controller, params, data):
  isClear = maybeGetParamBool(params, "clear", True)
  isShow = maybeGetParamBool(params, "show", True)
  fbConfStr = maybeGetParamStr(params, "framebuf", None)
  orient = maybeGetParamStr(params, "orient", None)
  markup = data.decode("utf8")

  fbConf = FramebufConf.parseFramebufConfStr(
    fbConfStr,
    controller['lcd'].get_lcd_landscape_width(),
    controller['lcd'].get_lcd_landscape_height())

  print("text: " + markup)

  out = ""
  if orient != None:
    out += setOrientation(controller['lcd'], orient)
  if fbConf != None:
    out += setFramebuf(controller['lcd'], fbConf)

  rtcEpoch = None
  #only fetch RTC epoch and timezone if markup looks like it might want it
  if controller['rtc'] != None and "!rtc" in markup:
    rtcEpoch = controller['rtc'].getTimeEpoch()
    rtcEpoch = adjustRTCEpochWithTZOffset(rtcEpoch)

  if isClear:
    controller['lcd'].fill(controller['lcd'].black)
  controller['lcdFont'].drawMarkup(markup, rtcEpoch=rtcEpoch)
  if isShow:
    controller['lcd'].show()

  return out

#####
#####

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
  lcdConf = LCD_CONFS[lcdName]
  lcd = LCD(
    lcdConf['landscapeWidth'],
    lcdConf['landscapeHeight'],
    lcdConf['rotationLayouts'])
  msg = "LCD init\n"

  fbConfStr = readLastFramebufConf()
  fbConf = FramebufConf.parseFramebufConfStr(
    fbConfStr,
    lcd.get_lcd_landscape_width(),
    lcd.get_lcd_landscape_height())

  msg += setFramebuf(lcd, fbConf) + "\n"
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
  # see doc for 'framebuf' command for framebuf param
  if fbConf == None:
    fbConf = FramebufConf(enabled=False)

  lcd.set_framebuf_conf(fbConf)
  # write the ATTEMPTED framebuf to last framebuf
  writeLastFramebufConf(fbConf)
  # get the actual framebuf conf of the LCD (might have failed due to OOM)
  fbConf = lcd.get_framebuf_conf()
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
    with open(STATE_FILE_WIFI_CONF, "a") as fh:
      fh.write(ssid + " = " + password + "\n")
  except:
    pass

def readLastLCDName():
  val = readFileLine(STATE_FILE_LCD_NAME)
  if val != None:
    val = val.strip()
  if val in LCD_CONFS:
    return val
def writeLastLCDName(lcdName):
  writeFile(STATE_FILE_LCD_NAME, lcdName + "\n")

def readLastRotationDegrees():
  return readFileInt(STATE_FILE_ORIENTATION)
def writeLastRotationDegrees(degrees):
  writeFile(STATE_FILE_ORIENTATION, str(degrees) + "\n")

def readLastFramebufConf():
  val = readFileLine(STATE_FILE_FRAMEBUF)
  if val != None:
    val = val.strip()
  return val
def writeLastFramebufConf(fbConf):
  writeFile(STATE_FILE_FRAMEBUF, str(fbConf) + "\n")

def readTimeoutFile():
  val = readFileLine(STATE_FILE_TIMEOUT)
  if val != None:
    val = val.strip()
    segments = val.split(",")
    if len(segments) == 2:
      try:
        timeoutMillis = int(segments[0])
        timeoutText = segments[1]
        return (timeoutMillis, timeoutText)
      except:
        return (None, None)
  return (None, None)
def writeTimeoutFile(timeoutMillis, timeoutText):
  if timeoutMillis == 0 or timeoutMillis == None or timeoutText == None:
    writeFile(STATE_FILE_TIMEOUT, "")
  else:
    writeFile(STATE_FILE_TIMEOUT, str(timeoutMillis) + "," + timeoutText + "\n")

def readTZFile():
  val =  readFileLine(STATE_FILE_TIMEZONE)
  if val != None:
    val = val.strip()
  return val
def writeTZFile(tzName):
  if tzName == None:
    try:
      os.remove(STATE_FILE_TIMEZONE)
    except OSError:
      pass
  else:
    writeFile(STATE_FILE_TIMEZONE, tzName + "\n")

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
  with open(STATE_FILE_WIFI_CONF, "r") as fh:
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
