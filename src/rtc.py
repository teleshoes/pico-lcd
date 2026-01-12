from machine import Pin, I2C
import time

I2C_PORT = 0
I2C_SDA = 20
I2C_SCL = 21

ADDRESS = 0x68

START_REGISTER = 0x00
CONTROL_REGISTER = 0x0e
STATUS_REGISTER = 0x0f

# DS3231 can only handle two centuries 1900-2099
#  change to YEAR_2000=2000 to support 2000-2199
#    it also cannot handle non-leap-year centuries like 1900 and 2100
#  this is RIDICULOUS as there is so much wasted space in the registers,
#     could easily hold a two-byte year
YEAR_1900 = 1900

# convert from decimal byte to binary-coded-decimal byte
def byteDecToBCD(byteVal):
  # e.g.:  0x63 (99) ---> 0x99 (153)
  #        0x1e (30) ---> 0x30 (48)
  return (byteVal//10<<4) + (byteVal%10)
def byteBCDToDec(byteVal):
  # e.g.: 0x99 (153) ---> 0x63 (99)
  #       0x30 (48)  ---> 0x1e (30)
  return 10*(byteVal>>4) + (byteVal%16)


class RTC_DS3231:
  def __init__(self):
    self.bus = I2C(I2C_PORT, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA))

  def convertTimeObjToBytes(self, timeObj):
    secondByte = byteDecToBCD(timeObj['second'])
    minuteByte = byteDecToBCD(timeObj['minute'])
    hourByte = byteDecToBCD(timeObj['hour'])
    dayOfWeekByte = byteDecToBCD(timeObj['dayOfWeek']) #1-7
    dayByte = byteDecToBCD(timeObj['day'])
    monthAndCenturyByte = byteDecToBCD(timeObj['month'])
    yearByte = byteDecToBCD(timeObj['year'] % 100)

    # 24hour = 0 0 [hourStartsWith2] [hourStartsWith1] H3 H2 H1 H0
    # 12hour = 0 1 [hourIsPM]        [hourStartsWith1] H3 H2 H1 H0
    #    where the ones-place of the hour is H3*8 + H2*4 + H1*2 + H0
    # e.g.:
    #                    24-hour   (12-hour)
    #   17:00 (5pm)   =  0001 0111 (0110 0101)
    #   00:00 (12am)  =  0000 0000 (0101 0010)
    #   12:00 (12pm)  =  0001 0010 (0111 0010)
    #   23:00 (11pm)  =  0010 0011 (0111 0001)
    if timeObj['is12Hr']:
      hourByte += 1<<6                           #hourIs12Hr bit
      hourByte += 1<<5 if timeObj['isPM'] else 0 #hourIsPM bit

    #check for naive leap year implementation
    if timeObj['year'] % 100 == 0 and timeObj['year'] % 400 != 0:
      raise ValueError("ERROR: DS3231 wrongly treats EVERY 4 years as leap year,"
        + " (including %d" + str(timeObj['year']) + ")\n")

    #bit7 of month is century, which is set if year 0-99 overflows
    if YEAR_1900 <= timeObj['year'] and timeObj['year'] < (YEAR_1900+100):
      monthAndCenturyByte += 0
    elif (YEAR_1900+100) <= timeObj['year'] and timeObj['year'] < (YEAR_1900+200):
      monthAndCenturyByte += 1<<7
    else:
      raise ValueError("ERROR: RTC year outside of supported range "
        + str(YEAR_1900) + "-" + str(YEAR_1900+100+99))

    byteList = [
      secondByte, minuteByte, hourByte,
      dayOfWeekByte,
      dayByte, monthAndCenturyByte, yearByte
    ]

    return bytes(byteList)

  def convertBytesToTimeObj(self, timeBytes):
    ( secondByte, minuteByte, hourByte,
      dayOfWeekByte,
      dayByte, monthAndCenturyByte, yearByte ) = list(timeBytes)

    is12Hr = False
    isPM = False
    if hourByte & 0b01000000:
      hourByte -= 0b01000000
      is12Hr = True
      if hourByte & 0b00100000:
        hourByte -= 0b00100000
        isPM = True

    century = 1900
    if monthAndCenturyByte & 0b10000000:
      monthAndCenturyByte -= 0b10000000
      century += 100

    timeObj = {
      'second': byteBCDToDec(secondByte),
      'minute': byteBCDToDec(minuteByte),
      'hour': byteBCDToDec(hourByte),
      'is12Hr': is12Hr,
      'isPM': isPM,
      'dayOfWeek': byteBCDToDec(dayOfWeekByte),
      'day': byteBCDToDec(dayByte),
      'month': byteBCDToDec(monthAndCenturyByte),
      'year': byteBCDToDec(yearByte) + century,
    }

    return timeObj

  def convertTimeObjToEpoch(self, timeObj):
    hr = timeObj['hour']
    if timeObj['isPM']:
      hr += 12
    return time.mktime((
      timeObj['year'], timeObj['month'], timeObj['day'],
      hr, timeObj['minute'], timeObj['second'], 0, 0))

  def convertEpochToTimeObj(self, epoch):
    (year, mon, day, hr, minute, sec, wkDay, yearDay) = time.gmtime(epoch)
    timeObj = {
      'second': sec,
      'minute': minute,
      'hour': hr,
      'is12Hr': False,
      'isPM': False,
      'dayOfWeek': wkDay + 1,
      'day': day,
      'month': mon,
      'year': year,
    }
    return timeObj

  def convertTimeObjToISO(self, timeObj):
    hr = timeObj['hour']
    if timeObj['isPM']:
      hr += 12
    return "%04d-%02d-%02dT%02d:%02d:%02d+00:00" % (
      timeObj['year'],
      timeObj['month'],
      timeObj['day'],
      hr,
      timeObj['minute'],
      timeObj['second'],
    )

  def readTimeBytes(self):
    return bytes(self.bus.readfrom_mem(int(ADDRESS),int(START_REGISTER),7))

  def writeTimeBytes(self, timeBytes):
    self.bus.writeto_mem(int(ADDRESS), int(START_REGISTER), timeBytes)

  def getTimeEpoch(self):
    return self.convertTimeObjToEpoch(self.convertBytesToTimeObj(self.readTimeBytes()))
  def setTimeEpoch(self, timeObj):
    return self.writeTimeBytes(self.convertTimeObjToBytes(self.convertEpochToTimeObj(timeObj)))

  def getTimeISO(self):
    return self.convertTimeObjToISO(self.convertBytesToTimeObj(self.readTimeBytes()))

  def setOffsetTZDataCsvFile(self, tzdataCsvFile):
    self.tzdataCsvFile = tzdataCsvFile

  def getTimeEpochPlusTZOffset(self):
    rtcEpoch = self.getTimeEpoch()
    if self.tzdataCsvFile != None:
      try:
        with open(self.tzdataCsvFile, "r") as fh:
          for line in fh:
            cols = line.split(',')
            if len(cols) == 2:
              (offsetStartEpochStr, offsetSecondsStr) = cols
              offsetStartEpoch = int(offsetStartEpochStr)
              offsetSeconds = int(offsetSecondsStr)
              if offsetStartEpoch >= rtcEpoch:
                rtcEpoch += offsetSeconds
                break
      except Exception as e:
        print("WARNING: failed to read tzdata from " + self.tzdataCsvFile + "\n" + str(e) + "\n")
    return rtcEpoch

#if __name__ == '__main__':
#  rtc = RTC_DS3231()
#  #rtc.setTimeEpoch(0)
#
#  while 1:
#    print(str(rtc.getTimeISO()))
#    print(str(rtc.getTimeEpoch()))
#    time.sleep(1)
