
def getAllCommands():
  cmds = []
  symbols = globals()
  for name in globals():
    if name.startswith("CMD_"):
      cmds.append(symbols[name])
  return cmds

def formatAllCommands():
  fmt = ""
  for cmd in getAllCommands():
    params = cmd['params']
    fmt += "COMMAND %s\n" % cmd['name']
    if len(params) == 0:
      fmt += "  PARAMS: (none)\n"
    else:
      fmt += "  PARAMS:\n"
      for paramName, paramDesc in params.items():
        fmt += "    %8s = %s\n" % (paramName, paramDesc)
    if cmd['body'] == None:
      fmt += "  BODY: (none)\n"
    else:
      fmt += "  BODY: %s\n" % cmd['body']
    fmt += "  DESC:\n    %s\n" % cmd['desc'].strip()
    fmt += "\n"
  return fmt

LCD_NAME_1_3 = "1_3"
LCD_NAME_2_0 = "2_0"
LCD_NAME_2_8 = "2_8"
LCD_NAMES = [LCD_NAME_1_3, LCD_NAME_2_0, LCD_NAME_2_8]

CMD_INFO = {
  "name":   "info",
  "params": {},
  "body":   None,
  "desc":   """
    print LCD info+state, formatted as FORMAT
    FORMAT =
      window: <WINDOW_SIZE>
        (lcd: <LCD_SIZE>, framebuf: <FRAMEBUF_GEOMETRY>)
      char8px: <CHAR_GRID_8PX>
      orientation: <ORIENTATION> degrees
      RAM free: <MEM_FREE_BYTES> bytes
      FS used: <USED_KIB>/<TOTAL_KIB> KiB (<USED_BLK>/<TOTAL_BLK> <BLKSIZE_KIB>k blocks)
      buttons: <BUTTON_LIST>
      lcdconf: <LCD_NAME>
      framebuf-boot: <BOOT_FRAMEBUF_CONF>
      timeout-millis: <TIMEOUT_MILLIS>
      timeout-template: <TIMEOUT_TEMPLATE>
      timezone: <TZ_NAME>
      firmware: <FIRMWARE_FMT>
      board: <BOARD_FMT>
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
    CHAR_GRID_8PX = <CH_GRID_W>x<CH_GRID_H>
      the number of 8px chars that can fit in the current WINDOW_SIZE
      first number is characters per row, second number is total rows
      (similar to $COLUMNS and $LINES in a terminal emulator)
    ORIENTATION = 0 | 90 | 180 | 270
      0=landscape, 270=portrait, 180=inverted-landscape, 90=inverted-portrait
    MEM_FREE_BYTES = <INT>
      free RAM in bytes
    TOTAL_BLK = <INT>
      total filesystem blocks, as reported by os.statvfs('/')
    AVAIL_BLK = <INT>
      available filesystem blocks, as reported by os.statvfs('/')
    BLKSIZE_BYTES = <INT>
      filesystem blocksize, as reported by os.statvfs('/') (NOTE: 4096 on LFS)
    BLKSIZE_KIB = <INT>
      <BLKSIZE_BYTES> divided by 1024, rounded down in case of weird blocksize (NOTE: 4 on LFS)
    USED_BLK = <INT>
      <TOTAL_BLK> minus <AVAIL_BLK>
    USED_KIB = <INT>
      <USED_BLK> times <BLKSIZE_KIB>
    TOTAL_KIB = <INT>
      <TOTAL_BLK> times <BLKSIZE_KIB>
    BUTTON_LIST = <BUTTON>, <BUTTON_LIST> | <EMPTY>
      a CSV of <BUTTON> entries
    BUTTON = <BTN_NAME>=<BTN_PRESS_COUNT>
      the name of a button and the number of times pressed since last boot
    LCD_NAME = """ + " | ".join(LCD_NAMES) + """
      name of the LCD model, set by the 'lcd' cmd
    BOOT_FRAMEBUF_CONF = off | <FB_W>x<FB_H> | <FB_W>x<FB_H>+<FB_X>+<FB_Y>
      the framebuf conf, set by the 'framebuf' cmd
      will be applied at the next boot, even if framebuf failed to load at runtime
    TIMEOUT_MILLIS = <INT>
      timeout in milliseconds, set by 'timeout' cmd
    TIMEOUT_TEMPLATE = <STR>
      markup template to be filled in and shown at timeout, set by 'template' cmd
    TZ_NAME = <STR>
      name of the timezone, set by 'timezone' cmd
    FIRMWARE_FMT = <STR>
      micropython firmware build info string, returned by os.uname().version
      contains the git commit hash, build date, and the compiler version
    BOARD_FMT = <STR>
      the hardware string returned by os.uname().machine
      contains either RP2040 for Pico or RP2350 for Pico2
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
    "ssid":     "[REQUIRED] ssid",
    "password": "[REQUIRED] password",
    "timeout":  "[OPTIONAL] max time to wait in seconds to connect before trying next",
  },
  "body":   None,
  "desc":   "append a wifi network to the list of networks to try at boot",
}
CMD_RESETWIFI = {
  "name":   "resetwifi",
  "params": {},
  "body":   None,
  "desc":   "forget all wifi networks (does not disconnect current)",
}
CMD_TEMPLATE = {
  "name":   "template",
  "params": {
    "templateName": "one of: timeout, wifi-waiting, wifi-connected, ap-waiting, ap-active"
  },
  "body":   "message markup, blank for default",
  "desc":   """
    set the markup template for status messages
    allows variable substitution with the syntax: [var=VARIABLE_NAME]
    VARIABLE_NAME
      ssid     = the external AP ssid to connect to, or the internal AP ssid
      password = the hardcoded WPA key for the internal AP (never the configured WPA)
      ip       = the IP address on the local network, or the internal AP IP address
  """,
}
CMD_TIMEOUT = {
  "name":   "timeout",
  "params": {
    "timeoutMillis": "[OPTIONAL] timeout in milliseconds, missing means no timeout",
  },
  "body":   None,
  "desc":   "set a timeout on network. when reached, display the timeout template (see template)",
}
CMD_TIMEZONE = {
  "name":   "timezone",
  "params": {
    "name": "[OPTIONAL] tzdata zone name, missing is the same as UTC",
  },
  "body":   None,
  "desc":   """
     for DS3231 real-time-clock [rtc] markup
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
    "name": "[REQUIRED] LCD name, one of: " + " | ".join(LCD_NAMES)
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
    "framebuf": "[OPTIONAL] off | <FB_W>x<FB_H> | <FB_W>x<FB_H>+<FB_X>+<FB_Y> | <FB_NAME>"
  },
  "body":   None,
  "desc":   """
    disable the framebuf, or enable framebuf and set the dimensions and offset
    NOTE: 'framebuf' param is *unaffected* by orientation
          <FB_W> and <FB_X> always refer to the longest dimension of the physical LCD
          <FB_H> and <FB_Y> always refer to the shortest dimension of the physical LCD
    NOTE: 'framebuf' uses a lot of memory. if memory allocation fails, framebuf is disabled
          the framebuf, if any, that is actually successfully allocated is returned
          if 'framebuf: off' is returned instead of a framebuf, allocation likely failed

    'framebuf' param:
      <FB_W>x<FB_H>+<FB_X>+<FB_Y> = enable framebuf with WxH and offset (0, 0)
      <FB_W>x<FB_H> = same as <FB_W>x<FB_H>+0+0
      off           = disable the framebuf
      <FB_NAME>     = one of: full | left | right | top | bottom | square
      full          = same as <LCD_W>x<LCD_H>                      e.g.: 320x240
      left          = same as <HALF_LCD_W>x<LCD_H>                 e.g.: 160x240
      right         = same as <HALF_LCD_W>x<LCD_H>+<HALF_LCD_W>+0  e.g.: 160x240+160+0
      top           = same as <LCD_W>x<HALF_LCD_H>                 e.g.: 320x120
      bottom        = same as <LCD_W>x<HALF_LCD_H>+0+<HALF_LCD_H>  e.g.: 320x120+0+120
      square        = same as <LCD_H>x<LCD_H>                      e.g.: 240x240

    <LCD_W>:      320 for lcd=2_0 or 240 for lcd=1_3
    <LCD_H>:      240 for lcd=2_0 or 240 for lcd=1_3
    <HALF_LCD_W>: 160 for lcd=2_0 or 120 for lcd_1_3
    <HALF_LCD_H>: 120 for lcd_2_0 or 120 for lcd_1_3
  """
}
CMD_UPLOAD = {
  "name":   "upload",
  "params": {
    "name": "[REQUIRED] filename",
  },
  "body":   "file contents",
  "desc":   """
    write body to file 'filename', creating dirs as necessary if filename contains '/'
  """,
}
CMD_DELETE = {
  "name":   "delete",
  "params": {
    "name": "[REQUIRED] filename",
  },
  "body":   "file contents",
  "desc":   """
    delete file 'filename'
  """,
}
CMD_BOOTLOADER = {
  "name":   "bootloader",
  "params": {},
  "body":   None,
  "desc":   "immediately enter BOOTSEL mass storage mode by running machine.bootloader()",
}
CMD_TEXT = {
  "name":   "text",
  "params": {
    "clear":    "[OPTIONAL] fill LCD window with black (default=True)",
    "show":     "[OPTIONAL] write framebuf to LCD if enabled (default=True)",
    "info":     "[OPTIONAL] if present, add output as in 'info' command (default=False)",
    "framebuf": "[OPTIONAL] if present, same as 'framebuf' command (default=None)",
    "orient":   "[OPTIONAL] if present, same as 'orient' command (default=None)",
  },
  "body":   "markup to display",
  "desc":   """
    -fetch 'markup' from body, decode as UTF-8
    -if 'orient' param is given, set the orientation as in the 'orient' cmd
    -if 'framebuf' param is given, set the framebuf as in the 'framebuf' cmd
    -if 'markup' contains '[rtc]:
      -fetch the current RTC epoch
      -calculate the tz offset from CSV, if tz name is set and CSV exists
    -if 'clear' param is given, fill the window with black as in the 'fill' cmd
    -draw the markup, in the framebuf or in the LCD
    -if 'show' is given, copy the framebuf to the LCD as in the 'show' cmd
  """,
}

if __name__=='__main__':
  print(formatAllCommands())
