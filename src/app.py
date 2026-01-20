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
    "lcdPins": {'BL':13, 'DC':8, 'RST':12, 'MOSI':11, 'SCK':10, 'CS':9},
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
    "lcdPins": {'BL':13, 'DC':8, 'RST':12, 'MOSI':11, 'SCK':10, 'CS':9},
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
  doc.LCD_NAME_2_8: {
    "lcdPins": {'BL':13, 'DC':8, 'RST':15, 'MOSI':11, 'SCK':10, 'CS':9},
    "buttons": {'TS':17},
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

DEFAULT_WIFI_TIMEOUT_S = 10

STATE_FILE_WIFI_CONF = "state-wifi-conf"
STATE_FILE_LCD_NAME = "state-lcd-name"
STATE_FILE_ORIENTATION = "state-orientation"
STATE_FILE_FRAMEBUF = "state-framebuf"
STATE_FILE_TIMEOUT = "state-timeout"
STATE_FILE_TIMEZONE = "state-timezone"
PREFIX_STATE_FILE_TEMPLATE = "state-template-"

DEFAULT_MARKUP_TEMPLATES = {
  'timeout': (""
    + "TIMEOUT"
  ),
  'wifi-waiting': (""
    + "!size=4!!color=green!" + "WAITING!n!"
    + "!size=4!!color=green!" + "FOR WIFI!n!"
    + "!size=4!!color=white!" + "--------!n!"
    + "!size=2!!color=blue!"  + "!var=ssid!"
  ),
  'wifi-connected': (""
    + "!size=4!!color=green!"             + "CONNECTED!n!"
    + "!size=3!!color=blue!"              + "!n!listening on:!n!"
    + "!size=3!!color=green!!hspace=0.7!" + "!var=ip!!n!"
  ),
  'ap-waiting': (""
    + "!size=4!!color=green!" + "TURNING ON!n!"
    + "!size=4!!color=green!" + "WIFI AP!n!"
    + "!size=4!!color=white!" + "--------!n!"
    + "!size=2!!color=blue!"  + "!var=ssid!"
  ),
  'ap-active': (""
    + "!size=2!!color=green!"             + "SSID:!n!"
    + "!size=2!!color=white!"             + "!var=ssid!!n!"
    + "!size=2!!color=green!"             + "PASSWORD:!n!"
    + "!size=2!!color=white!"             + "!var=password!!n!"
    + "!size=2!!color=blue!"              + "IP:!n!"
    + "!size=2!!color=green!!hspace=0.7!" + "!var=ip!!n!"
    + "!size=1!!color=white!"             + "e.g.:!n!"
    + "!size=1!!color=white!"             + "curl 'http://!var=ip!/ssid?!n!"
                                          + "ssid=MY_NETWORK&password=P4SSW0RD'!n!"
  ),
}

def buttonPressedActions(btnName, controller):
  if btnName == "B2" or btnName == "A":
    controller['lcd'].set_rotation_next()
    writeStateOrientation(controller['lcd'].get_rotation_degrees())

def main():
  controller = {
    'lcdName': None, 'lcd': None, 'lcdFont': None,
    'timeoutMarkup': None,
    'rtc': None,
    'socket': None,
    'buttons': None,
    'wlanInfo': {'mac': None, 'ssid': None, 'ip': None},
  }

  lcdName = readStateLCDName()
  if lcdName == None:
    lcdName = DEFAULT_LCD_NAME

  controller['lcdName'] = lcdName
  controller['lcd'] = createLCD(controller['lcdName'])
  controller['buttons'] = createButtons(controller['lcdName'])
  addButtonHandlers(controller['buttons'], controller)

  controller['rtc'] = maybeGetRTC()

  controller['lcdFont'] = LcdFont('font5x8.bin', controller['lcd'], controller['rtc'])
  controller['lcdFont'].setup()

  controller['socket'] = getSocket()

  try:
    setupWifi(controller)
  except Exception as e:
    print("ERROR: wlan setup failed\n" + str(e))

  controller['timeoutMillis'] = readStateTimeout()

  cmdFunctionsByName = {}
  symDict = globals()
  for cmd in doc.getAllCommands():
    for symName in symDict:
      if symName.lower() == "cmd" + cmd['name']:
        cmdFunctionsByName[cmd['name']] = symDict[symName]
        break
    if cmd['name'] not in cmdFunctionsByName:
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
        if controller['timeoutMarkup'] == None:
          controller['timeoutMarkup'] = replaceMarkupTemplate('timeout',
            {})
        controller['lcdFont'].markup(controller['timeoutMarkup'])
        continue

      (cmdName, params, socketReader) = readCommandRequest(cl)

      if cmdName in cmdFunctionsByName:
        print('cmd: ' + cmdName)
        cmdFunction = cmdFunctionsByName[cmdName]
        out = cmdFunction(controller, params, socketReader)
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

  fbConfBootState = readStateFramebuf()
  tz = readStateTimezone()

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
  out += "wlan: mac=%s, ssid=%s, ip=%s\n" % (
            controller['wlanInfo']['mac'],
            controller['wlanInfo']['ssid'],
            controller['wlanInfo']['ip'],
          )
  out += "framebuf-boot: %s\n" % fbConfBootState
  out += "timeout-millis: %s\n" % controller['timeoutMillis']
  out += "timeout-template: %s\n" % str(readStateTemplate('timeout'))
  out += "timezone: %s\n" % tz
  out += "firmware: %s\n" % os.uname().version
  out += "board: %s\n" % os.uname().machine
  return out

def cmdConnect(controller, params, socketReader):
  setupWifi(controller)
  return None

def cmdSSID(controller, params, socketReader):
  ssid = maybeGetParamStr(params, "ssid", None)
  password = maybeGetParamStr(params, "password", None)
  timeout = maybeGetParamInt(params, "timeout", None)
  if ssid != None and password != None:
    writeStateWifiConfAppendSSID(ssid, password, timeout)
    out = (""
      + "added wifi network:\n"
      + "  ssid=" + ssid + "\n"
      + "  password=" + password + "\n"
      + "  timeout=" + str(timeout) + "\n"
    )
  else:
    out = "ERROR: missing ssid or password\n"
  return out

def cmdResetWifi(controller, params, socketReader):
  writeStateWifiConfReset()
  out = "WARNING: all wifi networks removed for next boot\n"
  return out

def cmdTemplate(controller, params, socketReader):
  controller['timeoutMarkup'] = None
  templateName = maybeGetParamStr(params, "templateName", None)
  templateMarkup = socketReader.readDataStr()
  out = ""
  if templateName != None:
    writeStateTemplate(templateName, templateMarkup)
  out += "template[" + templateName + "] = " + readStateTemplate(templateName)
  out += "\n"
  return out

def cmdTimeout(controller, params, socketReader):
  timeoutMillis = maybeGetParamInt(params, "timeoutMillis", None)
  print("timeout: " + str(timeoutMillis))
  writeStateTimeout(timeoutMillis)
  if timeoutMillis == None or timeoutMillis == 0:
    controller['timeoutMillis'] = None
  else:
    controller['timeoutMillis'] = timeoutMillis
  return None

def cmdTimezone(controller, params, socketReader):
  tzName = maybeGetParamStr(params, "name", None)
  writeStateTimezone(tzName)
  print("set timezone for rtc = " + str(tzName))
  if controller['rtc'] != None:
    controller['rtc'].setOffsetTZDataCsvFile(getTZDataCsvFile(readStateTimezone()))
  return None

def cmdRTC(controller, params, socketReader):
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

def cmdClear(controller, params, socketReader):
  controller['lcd'].fill_mem_blank()
  return None

def cmdShow(controller, params, socketReader):
  controller['lcd'].show()
  return None

def cmdButtons(controller, params, socketReader):
  return formatButtonCount(controller['buttons']) + "\n"

def cmdFill(controller, params, socketReader):
  colorName = maybeGetParamStr(params, "color", None)
  color = controller['lcd'].get_color_by_name(colorName)
  out = ""
  if color == None:
    out = "ERROR: could not parse color " + colorName + "\n"
  else:
    controller['lcd'].fill(color)
    controller['lcd'].show()
  return out

def cmdLCD(controller, params, socketReader):
  name = maybeGetParamStr(params, "name", None)
  if name in LCD_CONFS:
    removeButtonHandlers(controller['buttons'])

    controller['lcdName'] = name
    controller['lcd'] = createLCD(controller['lcdName'])
    controller['buttons'] = createButtons(controller['lcdName'])
    addButtonHandlers(controller['buttons'], controller)

    controller['lcdFont'].setLCD(controller['lcd'])
    writeStateLCDName(name)
  else:
    raise ValueError("ERROR: missing LCD param 'name'\n")
  return None

def cmdOrient(controller, params, socketReader):
  orient = maybeGetParamStr(params, "orient", None)
  print("orient=" + orient)

  return setOrientation(controller['lcd'], orient)

def cmdFramebuf(controller, params, socketReader):
  fbConfStr = maybeGetParamStr(params, "framebuf", None)
  fbConf = FramebufConf.parseFramebufConfStr(
    fbConfStr,
    controller['lcd'].get_lcd_landscape_width(),
    controller['lcd'].get_lcd_landscape_height())
  print("framebuf=" + str(fbConf))
  return setFramebuf(controller['lcd'], fbConf)

def cmdUpload(controller, params, socketReader):
  filename = maybeGetParamStr(params, "filename", None)
  out = ""
  try:
    byteCount = 0
    with open(filename, "w") as fh:
      while socketReader.isReady():
        data = socketReader.readDataChunk()
        if data != None:
          dataLen = len(data)
          byteCount += dataLen
          print("wrote %d bytes" % dataLen)
          fh.write(data)
    out = "wrote %d bytes to file %s\n" % (byteCount, filename)
  except Exception as e:
    print("WARNING: upload failed\n" + str(e))
  return out

def cmdDelete(controller, params, socketReader):
  filename = maybeGetParamStr(params, "filename", None)
  out = ""
  try:
    os.remove(filename)
    out += "deleted file %s\n" % filename
  except Exception as e:
    print("WARNING: delete file failed\n" + str(e))
  return out

def cmdBootloader(controller, params, data):
  print("ENTERING BOOTLOADER")
  machine.bootloader()
  print("WARNING: bootloader mode failed")
  return None

def cmdText(controller, params, socketReader):
  isClear = maybeGetParamBool(params, "clear", True)
  isShow = maybeGetParamBool(params, "show", True)
  fbConfStr = maybeGetParamStr(params, "framebuf", None)
  orient = maybeGetParamStr(params, "orient", None)
  info = maybeGetParamBool(params, "info", False)
  markup = socketReader.readDataStr()

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

  if info:
    out += cmdInfo(controller, None, None)

  controller['lcdFont'].markup(markup, isClear=isClear, isShow=isShow)

  return out

#####
#####

def createLCD(lcdName):
  lcdConf = LCD_CONFS[lcdName]
  lcd = LCD(
    lcdConf['lcdPins'],
    lcdConf['landscapeWidth'],
    lcdConf['landscapeHeight'],
    lcdConf['rotationLayouts'])
  msg = "LCD init\n"

  fbConfStr = readStateFramebuf()
  fbConf = FramebufConf.parseFramebufConfStr(
    fbConfStr,
    lcd.get_lcd_landscape_width(),
    lcd.get_lcd_landscape_height())

  msg += setFramebuf(lcd, fbConf) + "\n"
  msg += setOrientation(lcd, str(readStateOrientation())) + "\n"

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
    writeStateOrientation(lcd.get_rotation_degrees())
    return "orient=" + str(degrees) + "\n"
  else:
    return "unknown orient " + str(orient) + "\n"

def setFramebuf(lcd, fbConf):
  # see doc for 'framebuf' command for framebuf param
  if fbConf == None:
    fbConf = FramebufConf(enabled=False)

  lcd.set_framebuf_conf(fbConf)
  # write the ATTEMPTED framebuf to last framebuf
  writeStateFramebuf(fbConf)
  # get the actual framebuf conf of the LCD (might have failed due to OOM)
  actualFbConf = lcd.get_framebuf_conf()
  msg = "framebuf: " + str(actualFbConf) + "\n"
  if fbConf != actualFbConf:
    msg += "  (framebuf allocation failed, will be set on next boot to %s)\n" % fbConf
  return msg


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

def getTZDataCsvFile(tzName):
  if tzName == None:
    return None
  else:
    return "zoneinfo" + "/" + tzName + ".csv"

def readCommandRequest(cl):
  cl.settimeout(0.25)
  start_ms = time.ticks_ms()

  #read URL params + content length, skip to POST data
  line = ""
  contentLen = 0
  cmd = None
  params = {}
  while line != b'\r\n':
    if line.startswith("POST /") or line.startswith("GET /") or line.startswith("PUT /"):
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

  socketReader = SocketReader(cl, contentLen)

  return (cmd, params, socketReader)

class SocketReader:
  def __init__(self, socket, contentLen):
    self.socket = socket
    self.contentLen = contentLen
    self.lastReadMs = time.ticks_ms()
    self.bytesRead = 0
  def readDataStr(self):
    data = b""
    while self.isReady():
      chunk = self.readDataChunk()
      if chunk != None:
        data += chunk
    return data.decode("utf8")
  def readDataChunk(self):
    try:
      chunk = self.socket.recv(1024)
    except Exception as e:
      print("WARNING: error reading from socket\n" + str(e))
      chunk = None
    if chunk != None and len(chunk) > 0:
      self.lastReadMs = time.ticks_ms()
      self.bytesRead += len(chunk)
    return chunk
  def isReady(self):
    return self.hasData() and not self.isTimeout()
  def isTimeout(self):
    if time.ticks_diff(time.ticks_ms(), self.lastReadMs) > 5000:
      print("WARNING: exceeded timeout (5s) reading from socket")
      return True
    else:
      return False
  def hasData(self):
    return self.bytesRead < self.contentLen

def readStateWifiConf():
  networks = []
  try:
    with open(STATE_FILE_WIFI_CONF, "r") as fh:
      for line in fh:
        nw = parseNetworkEntry(line)
        if nw != None:
          networks.append(nw)
  except:
    networks = []
  return networks
def writeStateWifiConfAppendSSID(ssid, password, timeout):
  if timeout != None:
    appendFile(STATE_FILE_WIFI_CONF, str(timeout) + "," + ssid + " = " + password + "\n")
  else:
    appendFile(STATE_FILE_WIFI_CONF, ssid + " = " + password + "\n")
def writeStateWifiConfReset():
  writeFile(STATE_FILE_WIFI_CONF, "")

def parseNetworkEntry(entry):
  nw = None
  try:
    idxComma = entry.find(",")
    idxEq = entry.find("=")

    timeoutStr = None
    ssid = None
    password = None
    if idxComma >= 0 and idxComma < idxEq:
      #  TIMEOUT,SSID=PASSWORD
      timeoutStr = entry[:idxComma].strip()
      ssid = entry[idxComma+1:idxEq].strip()
      password = entry[idxEq+1:].strip()
    elif idxComma < 0 and idxEq >= 0:
      #  SSID=PASSWORD
      timeoutStr = None
      ssid = entry[0:idxEq].strip()
      password = entry[idxEq+1:].strip()

    timeout = None
    try:
      if timeoutStr == None:
        timeout = DEFAULT_WIFI_TIMEOUT_S
      else:
        timeout = int(timeoutStr)
    except:
      timeout = DEFAULT_WIFI_TIMEOUT_S

    if timeout != None and ssid != None and password != None:
      nw = [timeout, ssid, password]
    else:
      print("WARNING: malformed wifi entry\n" + str(entry))
  except Exception as e:
    print("WARNING: failed to parse wifi entry\n" + str(entry) + "\n" + str(e))
    nw = None
  return nw

def readStateLCDName():
  val = readFileLine(STATE_FILE_LCD_NAME)
  if val != None:
    val = val.strip()
  if val in LCD_CONFS:
    return val
def writeStateLCDName(lcdName):
  writeFile(STATE_FILE_LCD_NAME, lcdName + "\n")

def readStateOrientation():
  return readFileInt(STATE_FILE_ORIENTATION)
def writeStateOrientation(degrees):
  writeFile(STATE_FILE_ORIENTATION, str(degrees) + "\n")

def readStateFramebuf():
  val = readFileLine(STATE_FILE_FRAMEBUF)
  if val != None:
    val = val.strip()
  return val
def writeStateFramebuf(fbConf):
  writeFile(STATE_FILE_FRAMEBUF, str(fbConf) + "\n")

def readStateTemplate(templateName):
  stateFile = PREFIX_STATE_FILE_TEMPLATE + templateName
  template = None
  try:
    template = readFileLine(stateFile)
  except:
    template = None
  if template == None or template == "":
    template = DEFAULT_MARKUP_TEMPLATES[templateName]
  return template
def writeStateTemplate(templateName, templateMarkup):
  stateFile = PREFIX_STATE_FILE_TEMPLATE + templateName
  writeFile(stateFile, templateMarkup)

def readStateTimeout():
  val = readFileLine(STATE_FILE_TIMEOUT)
  try:
    val = val.strip()
    return int(val)
  except:
    return None
def writeStateTimeout(timeoutMillis):
  if timeoutMillis == 0 or timeoutMillis == None:
    writeFile(STATE_FILE_TIMEOUT, "")
  else:
    writeFile(STATE_FILE_TIMEOUT, str(timeoutMillis) + "\n")

def readStateTimezone():
  val =  readFileLine(STATE_FILE_TIMEZONE)
  if val != None:
    val = val.strip()
  return val
def writeStateTimezone(tzName):
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

def appendFile(file, contents):
  try:
    with open(file, "a") as fh:
      fh.write(contents)
  except:
    pass

def setupWifi(controller):
  networks = readStateWifiConf()

  connected = False
  connectedSSID = None

  wlan = network.WLAN(network.STA_IF)
  wlan.active(True)

  mac = wlan.config('mac').hex(":").upper()
  print("MAC: " + mac)

  NW_STAT_WRONG_PASSWORD =  -3
  NW_STAT_NO_AP_FOUND =     -2
  NW_STAT_CONNECT_FAIL =    -1
  NW_STAT_IDLE =             0
  NW_STAT_CONNECTING =       1
  NW_STAT_NO_IP =            2 #missing from network module but happens
  NW_STAT_GOT_IP =           3

  ARR_NW_STAT_IDLE = [NW_STAT_IDLE]
  ARR_NW_STAT_SUCCESS = [NW_STAT_GOT_IP]
  ARR_NW_STAT_FAILURE = [
    NW_STAT_NO_IP,
    NW_STAT_WRONG_PASSWORD,
    NW_STAT_NO_AP_FOUND,
    NW_STAT_CONNECT_FAIL,
  ]

  for nw in networks:
    (timeout, ssid, password) = nw

    endEpoch = time.time() + timeout
    while time.time() < endEpoch:
      status = wlan.status()
      print('waiting for connection (ssid=' + ssid + ', status=' + str(status) + ')...')
      controller['lcdFont'].markup(replaceMarkupTemplate('wifi-waiting',
        {'ssid':ssid}))

      if status in ARR_NW_STAT_IDLE or status in ARR_NW_STAT_FAILURE:
        if status in ARR_NW_STAT_FAILURE:
          print('  (retrying failure until timeout)')
        try:
          wlan.connect(ssid, password)
        except Exception as e:
          print(str(e))
      elif status in ARR_NW_STAT_SUCCESS:
        break

      time.sleep(0.5)

    if wlan.status() in ARR_NW_STAT_SUCCESS:
      connected = True
      connectedSSID = ssid
      break

  ipAddr = None
  if not connected:
    return setupAccessPoint(controller)
  else:
    print('connected')
    ip = wlan.ifconfig()[0]
    print('ip=' + ip)

    controller['wlanInfo'] = {'mac': mac, 'ssid': connectedSSID, 'ip': ip}

    controller['lcdFont'].markup(replaceMarkupTemplate('wifi-connected',
      {'ip':ip}))

def setupAccessPoint(controller):
  ssid = "pico-lcd"
  password = "123456789"

  controller['lcdFont'].markup(replaceMarkupTemplate('ap-waiting',
    {'ssid':ssid}))

  wlan = network.WLAN(network.AP_IF)
  wlan.config(essid=ssid, password=password)
  wlan.active(True)

  timeout = time.time() + 30
  while time.time() < timeout:
    if wlan.active:
      break
    print('waiting for connection...')
    controller['lcdFont'].markup(replaceMarkupTemplate('ap-waiting',
      {'ssid':ssid}))
    time.sleep(0.5)

  if not wlan.active:
    controller['lcdFont'].markup("!size=7!!color=red!" + "FAILED\nWIFI")
    raise RuntimeError('network connection failed')

  print("AP active: ssid=" + ssid + " password=" + password)
  print(wlan.ifconfig())

  ip = wlan.ifconfig()[0]

  mac = wlan.config('mac').hex(":").upper()
  controller['wlanInfo'] = {'mac': mac, 'ssid': ssid, 'ip': ip}

  controller['lcdFont'].markup(replaceMarkupTemplate('ap-active',
    {'ssid':ssid, 'password':password, 'ip':ip}))

def replaceMarkupTemplate(templateName, keyVals):
  markup = readStateTemplate(templateName)
  for key in keyVals.keys():
    markup = markup.replace('!var=' + key + '!', keyVals[key])
  return markup

def maybeGetRTC():
  rtc = RTC_DS3231()
  try:
    rtc.setOffsetTZDataCsvFile(getTZDataCsvFile(readStateTimezone()))
    rtc.getTimeEpochPlusTZOffset()
  except OSError as e:
    if e.errno == 5:
      #I/O error in I2C, probably no DS3231 device
      rtc = None
    else:
      print("WARNING: rtc error " + str(e))
  return rtc

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
