# LEGACY: Standalone-only firmware from an earlier iteration, before the
# charging dock (Quick Timer / Tamagotchi / Productivity Stats modes) was
# added. Superseded by ../code.py, which is the file that actually runs on
# the device (CircuitPython auto-runs code.py on boot). Kept here for
# reference only.

import time
import board
import busio
import adafruit_mpu6050
import adafruit_ds3231
import digitalio
import terminalio
import displayio
import analogio
import fourwire
import alarm
from adafruit_gc9a01a import GC9A01A
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.circle import Circle

FourWire = fourwire.FourWire
displayio.release_displays()


spi = busio.SPI(clock=board.D8, MOSI=board.D10)
battery_pin = analogio.AnalogIn(board.A0)
dock_pin = analogio.AnalogIn(board.A1)

tft_dc = board.D2
tft_cs = board.D9
tft_rst = board.D6 

# Force the SPI bus to send data at max speed!
display_bus = FourWire(spi, command=tft_dc, chip_select=tft_cs, reset=tft_rst, baudrate=60000000)
display = GC9A01A(display_bus, width=240, height=240)

i2c = busio.I2C(board.D5, board.D4)
mpu = adafruit_mpu6050.MPU6050(i2c, address = 0x69)
rtc = adafruit_ds3231.DS3231(i2c)

button = digitalio.DigitalInOut(board.D3)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP # This keeps it "True" until pressed

buzzer = digitalio.DigitalInOut(board.D7)
buzzer.direction = digitalio.Direction.OUTPUT
buzzer.value = True

mode_0 = "idle"
mode_1 = "5 minutes" 
mode_2 = "25 minutes"
mode_3 = "45 minutes" 
mode_4 = "60 minutes" 
mode_5 = "finished" 
mode_6 = "paused" 
mode_7 = "reset"
time_duration = {mode_1: 300, mode_2: 1500, mode_3: 2700, mode_4: 3600}

orientation_buffer = []
buffer_size = 6

mode = mode_0 # Default mode
print (f"State: {mode}")

previous_mode = mode_0
previous_active_mode = mode_0
is_idle = True
time_remaining = 0 
last_tick_time = 0
last_battery_tick = 0
battery_interval = 3

def get_battery_percentage():
    # Read the raw 16-båit analog value (0 to 65535)
    raw_reading = battery_pin.value
    
    # Convert the raw number to the voltage hitting the pin (3.3V reference)
    pin_voltage = (raw_reading / 65535.0) * 3.3
    
    # Reverse the physical voltage divider (multiply by 2)
    real_battery_voltage = pin_voltage * 2.0 
    
    # A standard LiPo is roughly 4.2V at 100% and 3.2V at 0% (Dead)
    # This maps that 1.0V window to a 0-100 percentage.
    percentage = ((real_battery_voltage - 3.2) / (4.2 - 3.2)) * 100
    
    # Clamp the values so it doesn't show 105% or -5%
    percentage = max(0, min(100, int(percentage)))
    
    return percentage, real_battery_voltage
 
def play_beep(duration):
    buzzer.value = False  
    time.sleep(duration)
    buzzer.value = True  
    time.sleep(0.1)

def auto_rotate():
    accel_x, accel_y, accel_z = mpu.acceleration
    
    if accel_y > 8.0:
        display.rotation = 0
    elif accel_x < -8.0:
        display.rotation = 270
    elif accel_y < -8.0:
        display.rotation = 180
    elif accel_x > 8.0:
        display.rotation = 90

def update_clock_display():
    clock_time = rtc.datetime
    hour_12 = clock_time.tm_hour % 12
    if hour_12 == 0:
        hour_12 = 12
    time_str = f"{hour_12}:{clock_time.tm_min:02}"
    clock_label.text = time_str
    # dynamically center based on character count
    clock_label.x = (240 - len(time_str) * 36) // 2
    temp_c = rtc.temperature
    temp_f = (temp_c * 9/5) + 32
    temp_string.text = str(int(temp_f))

def get_orientation():
    # Read the accelerometer data
    accel_x, accel_y, accel_z = mpu.acceleration

    # Check the accelerometer readings to determine the current mode
    if accel_y < -8.3 and abs(accel_x) < 6 and abs(accel_z) < 6: 
        raw = mode_3
    elif accel_x > 8.3 and abs(accel_y) < 6 and abs(accel_z) < 6: 
        raw = mode_4
    elif accel_y > 8.3 and abs(accel_x) < 6 and abs(accel_z) < 6:
        raw = mode_1
    elif accel_x < -8.3 and abs(accel_y) < 4 and abs(accel_z) < 6:
        raw = mode_2
    elif accel_z > 8.3 and abs(accel_x) < 6 and abs(accel_y) < 6:
        raw = mode_6 
    elif accel_z < -8.3 and abs(accel_x) < 6 and abs(accel_y) < 6:
        raw = mode_7 
    else: 
        raw = "unknown" 
        
    orientation_buffer.append(raw)
    if len(orientation_buffer) > buffer_size:
        orientation_buffer.pop(0)
        
    if len(orientation_buffer) == buffer_size and len(set(orientation_buffer)) == 1:
        return orientation_buffer[0]
    return None

time_remaining = 0 
last_tick_time = 0


# ---------------- MASTER GROUP (THE BASE LAYER) -------------
# ------------------------------------------------------------
# This group holds things that never disappear, saving RAM!
master_group = displayio.Group()
display.root_group = master_group

# 1. The Global Circle (Only drawn once in memory)
global_circle = Circle(120, 120, 117, outline=0xFFFFFF)
master_group.append(global_circle)

# 2. The Global Battery Widget
battery_group = displayio.Group()
master_group.append(battery_group)

#Percentage Text Sticker
percent_label = label.Label(terminalio.FONT, text="67%", color=0xFFFFFF)
percent_label.x = 111
percent_label.y = 185
master_group.append(percent_label)

# Battery static outlines
battery_outline = Rect(95, 193, 48, 18, outline=0xFFFFFF)
battery_tip = Rect(143, 197, 2, 10, fill=0xFFFFFF, outline=0xFFFFFF)
battery_group.append(battery_outline)
battery_group.append(battery_tip)

# Battery dynamic cells (Stored in a list so you can turn them on/off later)
battery_cells = [
    Rect(97, 195, 8, 14, fill=0x4caf50, outline=0x4caf50),
    Rect(106, 195, 8, 14, fill=0x4caf50, outline=0x4caf50),
    Rect(115, 195, 8, 14, fill=0x4caf50, outline=0x4caf50),
    Rect(124, 195, 8, 14, fill=0x4caf50, outline=0x4caf50),
    Rect(133, 195, 8, 14, fill=0x4caf50, outline=0x4caf50)
]
for cell in battery_cells:
    battery_group.append(cell)


# ---------------- TIMER UI LAYER ----------------------------
# ------------------------------------------------------------
Timer_UI = displayio.Group()

# The Time Text Sticker
time_label = label.Label(terminalio.FONT, text="00:00", color=0xFFFFFF)
time_label.x = 30
time_label.y = 110 
time_label.scale = 6
Timer_UI.append(time_label)


# The Progress Bar Outline
bar_outline = Rect(19, 145, 202, 20, outline=0xffffff)
Timer_UI.append(bar_outline)

# The Progress Bar Fill
battery_width = 198
bar_fill_group = displayio.Group()
Timer_UI.append(bar_fill_group)
bar_fill_group.append(Rect(21, 147, battery_width, 16, fill=0xffffff))

# Pause bar 1 
pause_bar_1 = Rect(124, 22, 9, 29, fill=0xffffff, outline=0xffffff)
pause_bar_1.hidden = True
Timer_UI.append(pause_bar_1)

# Pause bar 2 
pause_bar_2 = Rect(107, 22, 9, 29, fill=0xffffff, outline=0xffffff)
pause_bar_2.hidden = True
Timer_UI.append(pause_bar_2)

# Pause Text
pause_string = label.Label(terminalio.FONT, text="Paused...", color=0xFFFFFF)
pause_string.x = 79
pause_string.y = 77
pause_string.scale = 2
pause_string.hidden = True 
Timer_UI.append(pause_string)


# ---------------- IDLE UI LAYER -----------------------------
# ------------------------------------------------------------
Idle_UI = displayio.Group()

# The Clock Text Sticker
clock_label = label.Label(terminalio.FONT, text="00:00", color=0xFFFFFF)
clock_label.x = 30
clock_label.y = 125
clock_label.scale = 6
Idle_UI.append(clock_label)

# Thermometer Icon
thermometer_bitmap = displayio.OnDiskBitmap("/thermometer.bmp")
image_thermometer_tile = displayio.TileGrid(thermometer_bitmap, pixel_shader=thermometer_bitmap.pixel_shader)
image_thermometer_tile.x = 74
image_thermometer_tile.y = 45
Idle_UI.append(image_thermometer_tile)

# Degree Symbol Icon
temperature_bitmap = displayio.OnDiskBitmap("/temperature.bmp")
image_temperature_tile = displayio.TileGrid(temperature_bitmap, pixel_shader=temperature_bitmap.pixel_shader)
image_temperature_tile.x = 135
image_temperature_tile.y = 39
Idle_UI.append(image_temperature_tile)

# Temperature Text
temp_string = label.Label(terminalio.FONT, text="0", color=0xFFFFFF)
temp_string.x = 101
temp_string.y = 62
temp_string.scale = 3
Idle_UI.append(temp_string)



# ---------------- SHUTDOWN UI LAYER -------------------------
# ------------------------------------------------------------
Shutdown_UI = displayio.Group()

shut_string = label.Label(terminalio.FONT, text="Shutting", color=0xFFFFFF)
shut_string.x = 48
shut_string.y = 116
shut_string.scale = 3
Shutdown_UI.append(shut_string)

down_string = label.Label(terminalio.FONT, text="Down", color=0xFFFFFF)
down_string.x = 74
down_string.y = 165
down_string.scale = 3
Shutdown_UI.append(down_string)

moon_bitmap = displayio.OnDiskBitmap("/moon.bmp")
image_moon_tile = displayio.TileGrid(moon_bitmap, pixel_shader=moon_bitmap.pixel_shader)
image_moon_tile.x = 107
image_moon_tile.y = 26
Shutdown_UI.append(image_moon_tile)


# ---------------- STARTUP INITIALIZATION --------------------
# ------------------------------------------------------------
# Set the Idle screen to be visible when the ESP32 first boots
current_ui = Idle_UI
master_group.append(current_ui)
update_clock_display()

while True:
    
    current_time = time.monotonic()

    if current_time - last_battery_tick >= battery_interval:
        batt_pct, batt_volts = get_battery_percentage()
        print(f"Battery: {batt_pct}% ({batt_volts:.2f}V)")
        last_battery_tick = current_time # Reset the stopwatch
        percent_string = f"{batt_pct}%"
        percent_label.text = percent_string
        
        if batt_pct >= 80:
            active_color = 0x4caf50
        elif batt_pct >= 60:
            active_color = 0xCDDC39 # Lime Green (4-5 cells)
        elif batt_pct >= 40:
            active_color = 0xFFEB3B # Yellow (3 cells)
        elif batt_pct >= 20:
            active_color = 0xFF9800 # Orange (2 cells)
        else:
            active_color = 0xF44336 # Red (1 cell)
                
        for i in range(5):
            battery_cells[i].hidden = True
            battery_cells[i].fill = active_color
            battery_cells[i].outline = active_color
                
        if batt_pct > 5:
            battery_cells[0].hidden = False
        if batt_pct >= 20:
            battery_cells[1].hidden = False 
        if batt_pct >= 40:
            battery_cells[2].hidden = False
        if batt_pct >= 60:
            battery_cells[3].hidden = False
        if batt_pct >= 80:
            battery_cells[4].hidden = False
                
                
    if not button.value:
        power_button = time.monotonic()
        show_shutdown = False
        
        while not button.value:
            power_timer = time.monotonic() - power_button
            
            if power_timer >= 1 and not show_shutdown:
                if current_ui != Shutdown_UI:
                    master_group.remove(current_ui)
                    current_ui = Shutdown_UI
                    master_group.append(current_ui)
                show_shutdown = True
                
            if power_timer >= 1:
                down_string.text = "Down" 
                
            if power_timer >= 1.5:
                down_string.text = "Down."

            if power_timer >= 2:
                down_string.text = "Down.."
                
            if power_timer >= 2.5:
                down_string.text = "Down..."
                
            if power_timer >= 3:
                print ("Sleeping!")
                play_beep (0.5)

                display.root_group = displayio.Group()
                button.deinit()
                pin_alarm = alarm.pin.PinAlarm(pin=board.D1, value=False, pull=True)
                alarm.exit_and_deep_sleep_until_alarms(pin_alarm)
            time.sleep(0.05)
            
        
        if show_shutdown:
            if current_ui != Timer_UI:
                master_group.remove(current_ui)
                current_ui = Timer_UI
                master_group.append(current_ui)
            time.sleep (0.2)
            continue
            
            
        is_idle = not is_idle
        play_beep(0.1)
        
        if is_idle: 
            mode = mode_0
            
            if current_ui != Idle_UI:
                master_group.remove(current_ui)
                current_ui = Idle_UI
                master_group.append(current_ui)
                display.rotation = 0
            update_clock_display()
            time.sleep(0.5) 
            auto_rotate()
            print ("Manual Reset Triggered")
            print (f"State: {mode}")
            
            
        else:
            orientation_buffer.clear()
            previous_mode = mode_0
            
            if current_ui != Timer_UI:
                master_group.remove(current_ui)
                current_ui = Timer_UI
                master_group.append(current_ui)
                
            print ("Manual Reset Triggered: Timer")
            
        time.sleep(0.2)
        continue
 
    if is_idle:
        update_clock_display()
        auto_rotate()
        time.sleep(0.5)
    
    else:
        detected = get_orientation()
        
        if detected is None or detected == "unknown":
            pass
        
        else:
            mode = detected

            if mode != previous_mode:
                play_beep(0.1)
                
                
                if mode == mode_6:
                    previous_active_mode = previous_mode
                    pause_string.hidden = False
                    pause_bar_1.hidden = False
                    pause_bar_2.hidden = False
                    time_label.y = 120
                    bar_outline.y = 152
                    bar_fill_group.y = 7
                    
                elif previous_mode == mode_6:
                    pause_string.hidden = True
                    pause_bar_1.hidden = True
                    pause_bar_2.hidden = True
                    time_label.y = 110
                    bar_outline.y = 145
                    bar_fill_group.y = 0 
                
                if mode in time_duration:
                    if previous_mode == mode_6 and mode == previous_active_mode and time_remaining > 0:
                        print(f"Resuming {mode}")

                        
                    else:
                        print(f"{mode}")
                        time_remaining = time_duration[mode]

                        
                elif mode == mode_7: 
                    time_remaining = 0
                    

                previous_mode = mode
                last_tick_time = time.monotonic()
                print(f"State:{mode}")
                
                if mode == mode_1:     # 5 Minutes
                    display.rotation = 0
                elif mode == mode_2:   # 25 Minutes
                    display.rotation = 270
                elif mode == mode_3:   # 45 Minutes
                    display.rotation = 180
                elif mode == mode_4:   # 60 Minutes
                    display.rotation = 90
                
            if mode in time_duration and time_remaining > 0:
                current_time = time.monotonic()
                if current_time - last_tick_time >= 1.0:
                    time_remaining -= 1
                    last_tick_time = current_time
                    minutes = time_remaining // 60
                    seconds = time_remaining % 60
                    time_string = f"{minutes:02d}:{seconds:02d}"
                    print(f"Time remaining: {time_string}")
                    time_label.text = time_string
                    
                    total_time = time_duration[mode]
                    bar_scaler = time_remaining / total_time
                    bar_width = int (198 * bar_scaler)
                    
                    if bar_width < 1:
                        bar_width = 1
                        
                    while len(bar_fill_group) > 0:
                        bar_fill_group.pop()
                    bar_fill_group.append(Rect(21, 147, bar_width, 16, fill=0xffffff))
            

                                

                    
            if time_remaining <= 0 and mode in time_duration:
                print(f"{mode} finished")
                mode = mode_5 # Set mode to finished
                for _ in range(3):
                    play_beep(0.12)
                time.sleep (0.25)
                
                




