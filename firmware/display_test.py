import time
import board
import busio
import adafruit_ds3231

# Initialize the I2C bus and the RTC using your exact pins
i2c = busio.I2C(board.D5, board.D4)
rtc = adafruit_ds3231.DS3231(i2c)

# Format: (Year, Month, Day, Hour (24hr), Minute, Second, Weekday, Yearday, IsDST)
# 4:09 PM is written as 16, 9, 0
new_time = time.struct_time((2026, 6, 14, 16, 9, 0, 6, -1, -1))

print("Current time before change:", rtc.datetime)

# This physically writes the new time to the chip!
rtc.datetime = new_time

print("Time successfully set to:", rtc.datetime)