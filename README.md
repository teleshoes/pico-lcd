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
<!-- COMMAND_DOC -->
</pre>

## Markup Syntax for 'text' command
<pre>
<!-- MARKUP_SYNTAX -->
<!-- MARKUP_SYNTAX -->
</pre>
