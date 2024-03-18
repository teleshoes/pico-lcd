
def getAllCommands():
  cmds = []
  symbols = globals()
  for name in globals():
    if name.startswith("CMD_"):
      cmds.append(symbols[name])
  return cmds

LCD_NAME_1_3 = "1_3"
LCD_NAME_2_0 = "2_0"

CMD_INFO = {
  "name":   "info",
  "params": [],
  "body":   None,
  "desc":   """
    print LCD info+state, formatted as FORMAT
    FORMAT =
      window: <WINDOW_SIZE>
        (lcd: <LCD_SIZE>, framebuf: <FRAMEBUF_GEOMETRY>)
      orientation: <ORIENTATION> degrees
      RAM free: <MEM_FREE_BYTES> bytes
      buttons: <BUTTON_LIST>
      char8px: <CHAR_GRID_8PX>
    WINDOW_SIZE = <LCD_W>x<LCH_H> | <FB_W>x<FB_H> | <FB_H>x<FB_W>
      the actual available screen size in pixels in the current orientation+framebuf
        -if framebuf is disabled:                             <LCD_W>x<LCD_H>
        -if framebuf is enabled and orientation is 0 or 180:  <FB_W>x<FB_H>
        -if framebuf is enabled and orientation is 90 or 270: <FB_H>x<FB_W>
    FRAMEBUF_GEOMETRY = off | <FB_W>x<FB_H> | <FB_W>x<FB_H>+<FB_X>+<FB_Y>
      the framebuf window in memory, if enabled
      consists of a width and height and the (x, y) offset of the top-left corner
        -this does NOT change when orientation changes
    LCD_SIZE = <LCD_W>x<LCD_H>
      the total size of the screen in the current orientation
        -this DOES change when orientation changes (left-to-right dimension is first)
        -this does NOT change when framebuf is enabled/disabled/changed
    ORIENTATION = 0 | 90 | 180 | 270
      0=landscape, 270=portrait, 180=inverted-landscape, 90=inverted-portrait
    MEM_FREE_BYTES = <INT>
      free RAM in bytes
    BUTTON_LIST = <BUTTON>, <BUTTON_LIST> | <EMPTY>
      a CSV of <BUTTON> entries
    BUTTON = <BTN_NAME>=<BTN_PRESS_COUNT>
      the name of a button and the number of times pressed since last boot
    CHAR_GRID_8PX = <CH_GRID_W>x<CH_GRID_H>
      the number of 8px chars that can fit in the current WINDOW_SIZE
      first number is characters per row, second number is total rows
  """
}
CMD_CONNECT = {
  "name":   "connect",
  "params": {},
  "body":   None,
  "desc":   "run setupWifi",
}
CMD_SSID = {
  "name":   "ssid",
  "params": {
    "ssid":      "[REQUIRED] ssid",
    "password": "[REQUIRED] password",
  },
  "body":   None,
  "desc":   "add a wifi network",
}
CMD_RESETWIFI = {
  "name":   "resetwifi",
  "params": {},
  "body":   None,
  "desc":   "forget all wifi networks (does not disconnect current)",
}
CMD_TIMEOUT = {
  "name":   "timeout",
  "params": {
    "timeoutS": "[OPTIONAL] timeout in seconds, missing means no timeout",
  },
  "body":   "message markup to show on timeout, missing means no timeout",
  "desc":   "set a timeout on network. when reached, display the indicated markup",
}
CMD_TZ = {
  "name":   "tz",
  "params": {
    "name": "[OPTIONAL] tzdata zone name, missing is the same as UTC",
  },
  "body":   None,
  "desc":   """
     for DS3231 real-time-clock !rtc! markup
     use the tzdata ZONE_NAME to calculate offset,
     if a CSV exists at zoneinfo/<ZONE_NAME>.csv
  """,
}
CMD_RTC = {
  "name":   "rtc",
  "params": {
    "epoch": "[OPTIONAL] UNIX epoch seconds since 1970-01-01 UTC",
  },
  "body":   None,
  "desc":   """
     for DS3231 real-time-clock
       -if 'epoch' is passed in, set the DS3231 clock UTC time
         -epoch must be UTC, mean solar seconds, since 1970-01-01T00:00:00+00:00
         -if 'epoch' is NOT passed in, RTC is not set, just read
       -read RTC epoch, and format as epoch and as in `date --utc --iso=s`
  """,
}
CMD_CLEAR = {
  "name":   "clear",
  "params": {},
  "body":   None,
  "desc":   "empty ST7789 LCD screen memory (and framebuf, if enabled)",
}
CMD_SHOW = {
  "name":   "show",
  "params": {},
  "body":   None,
  "desc":   "display LCD (write framebuf to LCD, no effect if framebuf=off)",
}
CMD_BUTTONS = {
  "name":   "buttons",
  "params": {},
  "body":   None,
  "desc":   "show button names+count (like 'info' with FORMAT=BUTTON_LIST)",
}
CMD_FILL = {
  "name":   "fill",
  "params": {
    "color": "[REQUIRED] the color name to fill with",
  },
  "body":   None,
  "desc":   "fill the window (LCD or framebuf) with the indicated color",
}
CMD_LCD = {
  "name":   "lcd",
  "params": {
    "color": "[REQUIRED] LCD name, one of: " + LCD_NAME_1_3 + " | " + LCD_NAME_2_0,
  },
  "body":   None,
  "desc":   "set the physical LCD device-type name, e.g.: 2_0",
}
CMD_ORIENT = {
  "name":   "orient",
  "params": {
    "orient": "[REQUIRED] 0 | 270 | 180 | 90, or ORIENT_SYNONYM",
  },
  "body":   None,
  "desc":   """
    set the orientation of the LCD
    ORIENT_SYNONYM =
      0   = landscape | normal | default
      270 = portrait | -90
      180 = inverted-landscape
      90  = inverted-portrait
  """,
}
CMD_FRAMEBUF = {
  "name":   "framebuf",
  "params": {
    "framebuf": "[OPTIONAL] geometry WxH or WxH+X+Y, or off (missing is off)",
  },
  "body":   None,
  "desc":   "disable framebuf, or enable with width+height and optional (x, y) offset",
}
CMD_TEXT = {
  "name":   "text",
  "params": {
    "clear":    "[OPTIONAL] fill LCD window with black (default=True)",
    "show":     "[OPTIONAL] write framebuf to LCD if enabled (default=True)",
    "framebuf": "[OPTIONAL] if present, same as 'framebuf' command (default=None)",
    "orient":   "[OPTIONAL] if present, same as 'orient' command (default=None)",
  },
  "body":   "markup to display",
  "desc":   """
    -fetch 'markup' from body, decode as UTF-8
    -if 'orient' param is given, set the orientation as in the 'orient' cmd
    -if 'framebuf' param is given, set the framebuf as in the 'framebuf' cmd
    -if 'markup' contains '!rtc':
      -fetch the current RTC epoch
      -calculate the tz offset from CSV, if tz name is set and CSV exists
    -if 'clear' param is given, fill the window with black as in the 'fill' cmd
    -draw the markup, in the framebuf or in the LCD
    -if 'show' is given, copy the framebuf to the LCD as in the 'show' cmd
  """,
}
