# pico-lcd
micropython module for Raspberry Pi Pico W (RP2040) and Pico 2 W (RP2350) boards
to display markup over wifi on ST7789 LCD screens (such as the Waveshare Pico-LCD-2)

features:
- can draw text with colors and font sizes, percentage bars, PNG images, rectangles, with a markup string
  - markup format is custom and zany, and supports moving a cursor
  - PNG images must be uploaded to the filesystem via the upload command
 - fully configurable over wifi once uf2 is flashed, including SSID setup
   - initial boot acts as AP, once connected can setup other wlan networks
- supports Pico W and Pico 2 W
- supports Waveshare Pico-LCD-1.3, Pico-LCD-2, Pico-LCD-2.8
  - supports the buttons and touch screen for input, rotating the screen and reporting btn press counts
- supports real-time-clock module DS3231 RTC
  - timezone data can be added and markup supports formatting the offset timestamp with variables
  - it's a decent good customizable digital clock for places without wifi or constant power
- optional low-RAM framebuf in RGB444 for Pico W

## Command Documentation
<pre>
<!-- COMMAND_DOC -->
COMMAND info
  PARAMS: (none)
  BODY: (none)
  DESC:
    print LCD info+state, formatted as FORMAT
    FORMAT =
      window: &lt;WINDOW_SIZE&gt;
        (lcd: &lt;LCD_SIZE&gt;, framebuf: &lt;FRAMEBUF_GEOMETRY&gt;)
      char8px: &lt;CHAR_GRID_8PX&gt;
      orientation: &lt;ORIENTATION&gt; degrees
      RAM free: &lt;MEM_FREE_BYTES&gt; bytes
      buttons: &lt;BUTTON_LIST&gt;
      lcdconf: &lt;LCD_NAME&gt;
      framebuf-boot: &lt;BOOT_FRAMEBUF_CONF&gt;
      timeout-millis: &lt;TIMEOUT_MILLIS&gt;
      timeout-template: &lt;TIMEOUT_TEMPLATE&gt;
      timezone: &lt;TZ_NAME&gt;
      firmware: &lt;FIRMWARE_FMT&gt;
      board: &lt;BOARD_FMT&gt;
    WINDOW_SIZE = &lt;LCD_W&gt;x&lt;LCH_H&gt; | &lt;FB_W&gt;x&lt;FB_H&gt; | &lt;FB_H&gt;x&lt;FB_W&gt;
      the actual available screen size in pixels in the current orientation+framebuf
        -if framebuf is disabled:                             &lt;LCD_W&gt;x&lt;LCD_H&gt;
        -if framebuf is enabled and orientation is 0 or 180:  &lt;FB_W&gt;x&lt;FB_H&gt;
        -if framebuf is enabled and orientation is 90 or 270: &lt;FB_H&gt;x&lt;FB_W&gt;
    FRAMEBUF_GEOMETRY = off | &lt;FB_W&gt;x&lt;FB_H&gt; | &lt;FB_W&gt;x&lt;FB_H&gt;+&lt;FB_X&gt;+&lt;FB_Y&gt;
      the framebuf window in memory, if enabled
      consists of a width and height and the (x, y) offset of the top-left corner
        -this does NOT change when orientation changes
    LCD_SIZE = &lt;LCD_W&gt;x&lt;LCD_H&gt;
      the total size of the screen in the current orientation
        -this DOES change when orientation changes (left-to-right dimension is first)
        -this does NOT change when framebuf is enabled/disabled/changed
    CHAR_GRID_8PX = &lt;CH_GRID_W&gt;x&lt;CH_GRID_H&gt;
      the number of 8px chars that can fit in the current WINDOW_SIZE
      first number is characters per row, second number is total rows
      (similar to $COLUMNS and $LINES in a terminal emulator)
    ORIENTATION = 0 | 90 | 180 | 270
      0=landscape, 270=portrait, 180=inverted-landscape, 90=inverted-portrait
    MEM_FREE_BYTES = &lt;INT&gt;
      free RAM in bytes
    BUTTON_LIST = &lt;BUTTON&gt;, &lt;BUTTON_LIST&gt; | &lt;EMPTY&gt;
      a CSV of &lt;BUTTON&gt; entries
    BUTTON = &lt;BTN_NAME&gt;=&lt;BTN_PRESS_COUNT&gt;
      the name of a button and the number of times pressed since last boot
    LCD_NAME = 1_3 | 2_0 | 2_8
      name of the LCD model, set by the 'lcd' cmd
    BOOT_FRAMEBUF_CONF = off | &lt;FB_W&gt;x&lt;FB_H&gt; | &lt;FB_W&gt;x&lt;FB_H&gt;+&lt;FB_X&gt;+&lt;FB_Y&gt;
      the framebuf conf, set by the 'framebuf' cmd
      will be applied at the next boot, even if framebuf failed to load at runtime
    TIMEOUT_MILLIS = &lt;INT&gt;
      timeout in milliseconds, set by 'timeout' cmd
    TIMEOUT_TEMPLATE = &lt;STR&gt;
      markup template to be filled in and shown at timeout, set by 'template' cmd
    TZ_NAME = &lt;STR&gt;
      name of the timezone, set by 'timezone' cmd
    FIRMWARE_FMT = &lt;STR&gt;
      micropython firmware build info string, returned by os.uname().version
      contains the git commit hash, build date, and the compiler version
    BOARD_FMT = &lt;STR&gt;
      the hardware string returned by os.uname().machine
      contains either RP2040 for Pico or RP2350 for Pico2

COMMAND connect
  PARAMS: (none)
  BODY: (none)
  DESC:
    run setupWifi

COMMAND ssid
  PARAMS:
        ssid = [REQUIRED] ssid
    password = [REQUIRED] password
     timeout = [OPTIONAL] max time to wait in seconds to connect before trying next
  BODY: (none)
  DESC:
    append a wifi network to the list of networks to try at boot

COMMAND resetwifi
  PARAMS: (none)
  BODY: (none)
  DESC:
    forget all wifi networks (does not disconnect current)

COMMAND template
  PARAMS:
    templateName = one of: timeout, wifi-waiting, wifi-connected, ap-waiting, ap-active
  BODY: message markup, blank for default
  DESC:
    set the markup template for status messages
    allows variable substitution with the syntax: [var=VARIABLE_NAME]
    VARIABLE_NAME
      ssid     = the external AP ssid to connect to, or the internal AP ssid
      password = the hardcoded WPA key for the internal AP (never the configured WPA)
      ip       = the IP address on the local network, or the internal AP IP address

COMMAND timeout
  PARAMS:
    timeoutMillis = [OPTIONAL] timeout in milliseconds, missing means no timeout
  BODY: (none)
  DESC:
    set a timeout on network. when reached, display the timeout template (see template)

COMMAND timezone
  PARAMS:
        name = [OPTIONAL] tzdata zone name, missing is the same as UTC
  BODY: (none)
  DESC:
    for DS3231 real-time-clock [rtc] markup
     use the tzdata ZONE_NAME to calculate offset,
     if a CSV exists at zoneinfo/&lt;ZONE_NAME&gt;.csv

COMMAND rtc
  PARAMS:
       epoch = [OPTIONAL] UNIX epoch seconds since 1970-01-01 UTC
  BODY: (none)
  DESC:
    for DS3231 real-time-clock
       -if 'epoch' is passed in, set the DS3231 clock UTC time
         -epoch must be UTC, mean solar seconds, since 1970-01-01T00:00:00+00:00
         -if 'epoch' is NOT passed in, RTC is not set, just read
       -read RTC epoch, and format as epoch and as in `date --utc --iso=s`

COMMAND clear
  PARAMS: (none)
  BODY: (none)
  DESC:
    empty ST7789 LCD screen memory (and framebuf, if enabled)

COMMAND show
  PARAMS: (none)
  BODY: (none)
  DESC:
    display LCD (write framebuf to LCD, no effect if framebuf=off)

COMMAND buttons
  PARAMS: (none)
  BODY: (none)
  DESC:
    show button names+count (like 'info' with FORMAT=BUTTON_LIST)

COMMAND fill
  PARAMS:
       color = [REQUIRED] the color name to fill with
  BODY: (none)
  DESC:
    fill the window (LCD or framebuf) with the indicated color

COMMAND lcd
  PARAMS:
        name = [REQUIRED] LCD name, one of: 1_3 | 2_0 | 2_8
  BODY: (none)
  DESC:
    set the physical LCD device-type name, e.g.: 2_0

COMMAND orient
  PARAMS:
      orient = [REQUIRED] 0 | 270 | 180 | 90, or ORIENT_SYNONYM
  BODY: (none)
  DESC:
    set the orientation of the LCD
    ORIENT_SYNONYM =
      0   = landscape | normal | default
      270 = portrait | -90
      180 = inverted-landscape
      90  = inverted-portrait

COMMAND framebuf
  PARAMS:
    framebuf = [OPTIONAL] off | &lt;FB_W&gt;x&lt;FB_H&gt; | &lt;FB_W&gt;x&lt;FB_H&gt;+&lt;FB_X&gt;+&lt;FB_Y&gt; | &lt;FB_NAME&gt;
  BODY: (none)
  DESC:
    disable the framebuf, or enable framebuf and set the dimensions and offset
    NOTE: 'framebuf' param is *unaffected* by orientation
          &lt;FB_W&gt; and &lt;FB_X&gt; always refer to the longest dimension of the physical LCD
          &lt;FB_H&gt; and &lt;FB_Y&gt; always refer to the shortest dimension of the physical LCD
    NOTE: 'framebuf' uses a lot of memory. if memory allocation fails, framebuf is disabled
          the framebuf, if any, that is actually successfully allocated is returned
          if 'framebuf: off' is returned instead of a framebuf, allocation likely failed

    'framebuf' param:
      &lt;FB_W&gt;x&lt;FB_H&gt;+&lt;FB_X&gt;+&lt;FB_Y&gt; = enable framebuf with WxH and offset (0, 0)
      &lt;FB_W&gt;x&lt;FB_H&gt; = same as &lt;FB_W&gt;x&lt;FB_H&gt;+0+0
      off           = disable the framebuf
      &lt;FB_NAME&gt;     = one of: full | left | right | top | bottom | square
      full          = same as &lt;LCD_W&gt;x&lt;LCD_H&gt;                      e.g.: 320x240
      left          = same as &lt;HALF_LCD_W&gt;x&lt;LCD_H&gt;                 e.g.: 160x240
      right         = same as &lt;HALF_LCD_W&gt;x&lt;LCD_H&gt;+&lt;HALF_LCD_W&gt;+0  e.g.: 160x240+160+0
      top           = same as &lt;LCD_W&gt;x&lt;HALF_LCD_H&gt;                 e.g.: 320x120
      bottom        = same as &lt;LCD_W&gt;x&lt;HALF_LCD_H&gt;+0+&lt;HALF_LCD_H&gt;  e.g.: 320x120+0+120
      square        = same as &lt;LCD_H&gt;x&lt;LCD_H&gt;                      e.g.: 240x240

    &lt;LCD_W&gt;:      320 for lcd=2_0 or 240 for lcd=1_3
    &lt;LCD_H&gt;:      240 for lcd=2_0 or 240 for lcd=1_3
    &lt;HALF_LCD_W&gt;: 160 for lcd=2_0 or 120 for lcd_1_3
    &lt;HALF_LCD_H&gt;: 120 for lcd_2_0 or 120 for lcd_1_3

COMMAND upload
  PARAMS:
        name = [REQUIRED] filename
  BODY: file contents
  DESC:
    write body to file 'filename', creating dirs as necessary if filename contains '/'

COMMAND delete
  PARAMS:
        name = [REQUIRED] filename
  BODY: file contents
  DESC:
    delete file 'filename'

COMMAND bootloader
  PARAMS: (none)
  BODY: (none)
  DESC:
    immediately enter BOOTSEL mass storage mode by running machine.bootloader()

COMMAND text
  PARAMS:
       clear = [OPTIONAL] fill LCD window with black (default=True)
        show = [OPTIONAL] write framebuf to LCD if enabled (default=True)
        info = [OPTIONAL] if present, add output as in 'info' command (default=False)
    framebuf = [OPTIONAL] if present, same as 'framebuf' command (default=None)
      orient = [OPTIONAL] if present, same as 'orient' command (default=None)
  BODY: markup to display
  DESC:
    -fetch 'markup' from body, decode as UTF-8
    -if 'orient' param is given, set the orientation as in the 'orient' cmd
    -if 'framebuf' param is given, set the framebuf as in the 'framebuf' cmd
    -if 'markup' contains '[rtc]:
      -fetch the current RTC epoch
      -calculate the tz offset from CSV, if tz name is set and CSV exists
    -if 'clear' param is given, fill the window with black as in the 'fill' cmd
    -draw the markup, in the framebuf or in the LCD
    -if 'show' is given, copy the framebuf to the LCD as in the 'show' cmd
<!-- COMMAND_DOC -->
</pre>

## Markup Syntax for 'text' command
<pre>
<!-- MARKUP_SYNTAX -->
  markup syntax is:
    [CURSOR_CMD=VAL]
      CURSOR_CMD = color|size|x|y|hspace|vspace
        [color=&lt;COLOR&gt;]
          set the cursor color to COLOR
          COLOR = either a NAMED_COLOR or a HEX_COLOR
          NAMED_COLOR = one of white black red green blue cyan magenta yellow aqua purple
          HEX_COLOR   = rgb hex color formatted '#RRGGBB' e.g.: '#C0C0C0'
        [size=&lt;SIZE&gt;]
          set the pixels-per-dot to SIZE
          for 5x8 font, font size in px is: 8*SIZE
        [x=&lt;X&gt;]
          set the left position of cursor &lt;CURSOR_X&gt; to &lt;X&gt;, as absolute px on LCD
        [y=&lt;Y&gt;]
          set the top position of cursor &lt;CURSOR_Y&gt; to &lt;Y&gt;, as absolute px on LCD
        [hspace=&lt;HSPACE&gt;]
          leave floor(HSPACE*SIZE) dots between each character
            any non-negative number, 1.0=default, 0=no space, 2.0=wide
            for 5x8 font, total width of a char in px is: SIZE*(5+HSPACE)
        [vspace=&lt;VSPACE&gt;]
          leave floor(VSPACE*SIZE) dots between lines
            any non-negative number, 1.0=default, 0=no space, 2.0=wide
            for 5x8 font, total height of a line in px is: SIZE*(8+VSPACE)

    [CURSOR_CMD=prev]
      CURSOR_CMD = color|size|x|y|hspace|vspace
        if VAL is 'prev', restore the value of CURSOR_CMD before the last change
        e.g.:   [color=white] A [color=blue] B [color=prev] C
                  is the same as:
                [color=white] A [color=blue] B [color=white] C

    [png=FILENAME]
      draw the PNG image, already present in the filesystem, at FILENAME
      top-left corner of the image is at cursor (&lt;CURSOR_X&gt;,&lt;CURSOR_Y&gt;)
      NOTE:
        A) file must already be on the filesystem, uploaded beforehand with upload command
        B) does not move the cursor, use [shift=&lt;W&gt;x0] to do so, where &lt;W&gt; is the PNG width
        C) framebuf does not support PNG:
             if framebuf is enabled:
               -PNGs are drawn directly on the LCD, not the framebuf
               -PNGs are offset by the same amount as the framebuf,
                 but they may extend past the area of the framebuf
               -PNGs are drawn only after building and showing the framebuf
                  -PNGs are always 'on top' of any other markup in framebuf
                  -PNGs will 'flicker' when being redrawn, if they overlap the framebuf
               -PNGs are re-drawn on each show until clear() is called

      e.g.: draw one 16x16 icon twice, with a label,
              and then another 16x16 icon with another label beneath it,
              formatted like this:
                Ax2:|a||a|
                Bx1:|b|
            [size=2][color=red]
            Ax2:[png=icon_a_16x16.png][shift=16x0][png=icon_a_16x16.png]
            [n]
            Bx1:[png=icon_b_16x16.png]

    [rect=&lt;W&gt;x&lt;H&gt;,&lt;IS_FILL&gt;,&lt;IS_SYMBOL&gt;]
    [rect=&lt;W&gt;,&lt;H&gt;,&lt;IS_FILL&gt;,&lt;IS_SYMBOL&gt;]
       -draw a rectangle from top-left at (&lt;CURSOR_X&gt;,&lt;CURSOR_Y&gt;) to bottom-right at (&lt;W&gt;,&lt;H&gt;)
       -move the cursor to the right exactly &lt;W&gt; px
       -fill pixels if &lt;IS_FILL&gt;
          -if &lt;IS_FILL&gt; is 'true' or '1' or 'y':
            -set fill=True, draw pixels contained by the rectangle
            (True is the default if omitted)
          -if &lt;IS_FILL&gt; is 'false' or '0' or 'n':
            -set fill=False, draw only the outline of the rectangle
       -scale and indent if &lt;IS_SYMBOL&gt;
          -if &lt;IS_SYMBOL&gt; is 'true' or '1' or 'y':
            -scale rectangle by &lt;SIZE&gt;, i.e.: [rect=&lt;W&gt;*&lt;SIZE&gt;,&lt;H&gt;*&lt;SIZE&gt;]
            -shift to the right by &lt;HSPACE&gt;*&lt;SIZE&gt;, i.e.: [shift=&lt;HSPACE&gt;*&lt;SIZE&gt;x0]
          -if &lt;IS_SYMBOL&gt; is 'false' or '0' or 'n':
             -do not scale &lt;W&gt; or &lt;H&gt;
             -do not shift by &lt;HSPACE&gt;
            (False is the default if omitted)
       e.g.:
          [rect=10x10,n,n]           empty square 10x10
          [size=3]A[rect=6x10,y,y]B  'A', solid rectangle 18x30 with 3px indent, 'B'
          [size=5]A[rect=5x8,n,y]B   'A', placeholder char, 'B', same spacing as 'A_B'

    [rect=&lt;W&gt;x&lt;H&gt;]
    [rect=&lt;W&gt;,&lt;H&gt;]
       same as: [rect=&lt;W&gt;x&lt;H&gt;,True,False]

    [ellipse=&lt;RAD_X&gt;x&lt;RAD_Y&gt;,&lt;IS_FILL&gt;,&lt;IS_SYMBOL&gt;]
    [ellipse=&lt;RAD_X&gt;,&lt;RAD_Y&gt;,&lt;IS_FILL&gt;,&lt;IS_SYMBOL&gt;]
       -draw an ellipse with x-radius=&lt;RAD_X&gt; and y-radius=&lt;RAD_Y&gt;,
         centered at (&lt;CURSOR_X&gt; + &lt;RAD_X&gt;, &lt;CURSOR_Y&gt; + &lt;RAD_Y&gt;)
         (left-most point is at &lt;CURSOR_X&gt;, top-most point is at &lt;CURSOR_Y&gt;)
       -&lt;RAD_X&gt; and &lt;RAD_Y&gt; can be fractional, to be scaled by &lt;IS_SYMBOL&gt;
       -move the cursor to the right exactly 2*&lt;RAD_X&gt;+1 px
       -fill pixels if &lt;IS_FILL&gt;
          -if &lt;IS_FILL&gt; is 'true' or '1' or 'y':
            -set fill=True, draw pixels contained by the ellipse
            (True is the default if omitted)
          -if &lt;IS_FILL&gt; is 'false' or '0' or 'n':
            -set fill=False, draw only the outline of the ellipse
       -scale and indent if &lt;IS_SYMBOL&gt;
          -if &lt;IS_SYMBOL&gt; is 'true' or '1' or 'y':
            -scale ellipse diameters by &lt;SIZE&gt;
                &lt;RAD_X&gt; = floor( (&lt;RAD_X&gt;*2+1)*&lt;SIZE&gt;) / 2)
                &lt;RAD_Y&gt; = floor( (&lt;RAD_Y&gt;*2+1)*&lt;SIZE&gt;) / 2)
            -shift to the right by &lt;HSPACE&gt;*&lt;SIZE&gt;, i.e.: [shift=&lt;HSPACE&gt;*&lt;SIZE&gt;x0]
          -if &lt;IS_SYMBOL&gt; is 'false' or '0' or 'n':
             -do not scale &lt;RAD_X&gt; or &lt;RAD_Y&gt;
             -do not shift by &lt;HSPACE&gt;
            (False is the default if omitted)

       NOTE:
         -all horizontal/vertical diameters are always an odd number of pixels

         -if xR=0 or yR=0, the result is a line segment and &lt;IS_FILL&gt; has no effect

         -with &lt;CURSOR&gt; = (&lt;CURSOR_X&gt;,&lt;CURSOR_Y&gt;)
           [ellipse=0,0,n,n] =&gt; 1px single pixel at &lt;CURSOR&gt;+(0,0)
           [ellipse=1,0,n,n] =&gt; 3px horizontal line from &lt;CURSOR&gt;+(0,0) to &lt;CURSOR&gt;+(2,0)
           [ellipse=0,1,n,n] =&gt; 3px vertical line from &lt;CURSOR&gt;+(0,0) to &lt;CURSOR&gt;+(0,2)
           [ellipse=1,1,n,n] =&gt; 3px cross centered at &lt;CURSOR&gt;+(1,1),
                                with the point &lt;CURSOR&gt;+(0,0) omitted for fill=False,
                                made of two 3px lines:
                                  3px horizontal line from &lt;CURSOR&gt;+(0,1) to &lt;CURSOR&gt;+(2,1)
                                  3px vertical line from &lt;CURSOR&gt;+(1,0) to &lt;CURSOR&gt;+(1,2)
           [ellipse=2,2] =&gt; a 5px diameter circle centered at &lt;CURSOR&gt;+(2,2)

       e.g.:
          [ellipse=5x5,n,n]                 empty circle 10px diameter
          [size=3]A[ellipse=5.1x4.9,y,y]B   'A', solid circle 33px diameter, 3px indent, 'B'
                                            same as: [size=3]A[ellipse=16x16,y,n][shift=3x0]B
          [size=5]25[ellipse=0.4x0.7,n,y]C  '25', stylized degree symbol, 3px indent, 'C'
                                            same as: [size=5]25[ellipse=4,6,n,n][shift=5x0]C

    [ellipse=&lt;RAD_X&gt;x&lt;RAD_Y&gt;]
    [ellipse=&lt;RAD_X&gt;,&lt;RAD_Y&gt;]
      same as: [ellipse=&lt;RAD_X&gt;x&lt;RAD_Y&gt;,True,False]

    [bar=&lt;W&gt;x&lt;H&gt;,&lt;PCT&gt;,&lt;FILL_COLOR&gt;,&lt;EMPTY_COLOR&gt;]
    [bar=&lt;W&gt;,&lt;H&gt;,&lt;PCT&gt;,&lt;FILL_COLOR&gt;,&lt;EMPTY_COLOR&gt;]
       draw two rectangles, to make a progress/status bar
         W           = the full outer width of the bar in pixels
         H           = the full outer height of the bar in pixels
         PCT         = an *integer* percentage of the fill state of the bar
         FILL_COLOR  = the color of the filled-in part of the bar
         EMPTY_COLOR = the color of the outer rectangle of the bar
       -draw empty rectangle
           -draw one rectangle, without moving the cursor, as in:
             [color=&lt;EMPTY_COLOR&gt;][rect=&lt;W&gt;x&lt;H&gt;]
           -move the cursor back and restore previous color, as in:
             [shift=-&lt;W&gt;x0][color=prev]
       -calculate filled-in rectangle
         -if &lt;W&gt; is bigger than &lt;H&gt; (horizontal bar):
            -calculate &lt;FILL_W&gt; as floor(&lt;W&gt;*&lt;PCT&gt;/100.0)
            -calculate &lt;FILL_H&gt; as just &lt;H&gt;
            -calculate &lt;FILL_SHIFT_Y&gt; as 0
         -otherwise (vertical bar):
            -calculate &lt;FILL_W&gt; as just &lt;W&gt;
            -calculate &lt;FILL_H&gt; as floor(&lt;H&gt;*&lt;PCT&gt;/100.0)
            -calculate &lt;FILL_SHIFT_Y&gt; as &lt;H&gt; - &lt;FILL_H&gt;
       -draw filled-in rectangle
          -move the cursor down for vertical bars (filled-in on bottom), as in:
            [shift=0x&lt;FILL_SHIFT_Y&gt;]
          -draw filled-in rectangle on top of empty rectangle as in:
            [color=&lt;FILL_COLOR&gt;][rect=&lt;FILL_W&gt;x&lt;FILL_H&gt;]
           -move the cursor back and restore previous color, as in:
             [shift=-&lt;W&gt;x-&lt;FILL_SHIFT_Y&gt;][color=prev]
       -move the cursor to the right of the outer empty rect, as in:
          [shift=&lt;X&gt;x0]
       e.g.: [bar=20,100,65,green,red]   vertical 20x100 green-on-red bar 65% full
                                          same as:
                                             [color=red][rect=20x100]
                                             [shift=-20x0][color=prev]
                                             [shift=0x35]
                                             [color=green][rect=20x65]
                                             [shift=-20x-35][color=prev]
                                             [shift=20x0]

    [shift=&lt;W&gt;x&lt;H&gt;]
    [shift=&lt;W&gt;,&lt;H&gt;]
       add &lt;W&gt; to &lt;CURSOR_X&gt; (move the cursor &lt;W&gt; pixels to the right, negative &lt;W&gt; for left)
       add &lt;H&gt; to &lt;CURSOR_Y&gt; (move the cursor &lt;Y&gt; pixels down, negative &lt;H&gt; for up)
       e.g.: [shift=0x-20]    move the cursor up 20 pixels

    [rtc=FORMAT]
        use time from DS3231 rtc clock (if supported) and format with FORMAT string
        NOTE: all [rtc=FORMAT] entries in markup share a single epoch time,
              multiple entries cannot show different times due to race conditions

        FORMAT is any string, with the following replacements:
          %s   EPOCH number of seconds since
          %Y   year, formatted as YYYY
          %m   month 1-12, formatted as MM
          %d   day 1-31, formatted as DD
          %H   hour 0-23, formatted as HH
          %I   hour 1-12, formatted as II
          %p   'AM' if %H is less than 12, otherwise 'PM'
          %M   minute, 0-59
          %S   second, 0-59
          %a   abbreviated day of week Mon/Tue/Wed/Thu/Fri/Sat/Sun
          %b   abbreviated month Jan/Feb/Mar/Apr/May/Jun/Jul/Aug/Sep/Oct/Nov/Dec
          %%   literal '%' character
    [n]
        treated the same as a newline literal
          moves the cursor down (8+vspace)*size px,
          and resets the left to initial
    [hline]
    [hl]
    [hr]
        draw a horizontal line at cursor
    [[
    [bracket]
        literal '[' character
  e.g.:
      hello[n][size=6][color=red]world[[]]
        looks similar to the following HTML:
      hello&lt;br/&gt;&lt;span style=&quot;font-size:48px; color:red&quot;&gt;world[]]&lt;/span&gt;
<!-- MARKUP_SYNTAX -->
</pre>
