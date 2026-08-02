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
import gc
import random
import microcontroller
import struct
from adafruit_gc9a01a import GC9A01A
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.circle import Circle

# ------------------------------------------------------------
# 1. HARDWARE SETUP & INITIALIZATION
# ------------------------------------------------------------
FourWire = fourwire.FourWire
displayio.release_displays()

spi = busio.SPI(clock=board.D8, MOSI=board.D10)
battery_pin = analogio.AnalogIn(board.A0)
dock_pin = analogio.AnalogIn(board.A1)

tft_dc = board.D2
tft_cs = board.D9
tft_rst = board.D6

display_bus = FourWire(spi, command=tft_dc, chip_select=tft_cs, reset=tft_rst, baudrate=20000000)
display = GC9A01A(display_bus, width=240, height=240)
display.auto_refresh = False

i2c = busio.I2C(board.D5, board.D4)
mpu = adafruit_mpu6050.MPU6050(i2c, address=0x69)
rtc = adafruit_ds3231.DS3231(i2c)

button = digitalio.DigitalInOut(board.D3)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP 

buzzer = digitalio.DigitalInOut(board.D7)
buzzer.direction = digitalio.Direction.OUTPUT
buzzer.value = True

# ------------------------------------------------------------
# 2. STATE MEMORY VARIABLES
# ------------------------------------------------------------
mode_0 = "idle"
mode_1 = "5 minutes"
mode_2 = "25 minutes"
mode_3 = "45 minutes"
mode_4 = "60 minutes"
mode_5 = "finished"
mode_6 = "paused"
mode_7 = "reset"

time_duration = {
    mode_1: 300,
    mode_2: 1500,
    mode_3: 2700,
    mode_4: 3600
}

DOCKED_STATES = {"home", "timer", "tomo", "button_4", "dock_idle"}
MAX_INCREMENT_SECONDS = 99 * 60 + 59

orientation_buffer = []
buffer_size = 6

mode = mode_0 
previous_mode = mode_0
previous_active_mode = mode_0

time_remaining = 0 
last_tick_time = 0
last_battery_tick = 0
battery_interval = 3
last_clock_tick = 0
CLOCK_INTERVAL = 1.0

alarm_active = False
alarm_step = 0
alarm_next_time = 0
finished_from_mode = None
ALARM_GAP = 1.0
ALARM_ON_TIME = 0.12
ALARM_OFF_TIME = 0.13
ALARM_BEEPS_PER_BURST = 3
reset_release_required = False

was_docked = False
last_dock_state = "none"
current_timer_max = 900

# Dock stability / power-saving state
last_valid_dock_state = "none"
last_valid_dock_time = 0
DOCK_LOSS_GRACE = 0.40

last_display_refresh = 0
DOCKED_REFRESH_INTERVAL = 0.05
UNDOCKED_REFRESH_INTERVAL = 0.01

# Screen Management
current_screen = "clock"

# Focus tracker state, stored in microcontroller.nvm.
FOCUS_MAGIC = b"FCS1"
FOCUS_FORMAT = "<4sHBBHHHII"
FOCUS_RECORD_SIZE = 22

focus_year = 0
focus_month = 0
focus_day = 0
focus_streak = 0
focus_sessions_today = 0
focus_minutes_today = 0
focus_total_sessions = 0
focus_total_minutes = 0

# Petting & Idle Variables
is_petting = False
tomo_press_start_time = 0
pet_frame_index = 0
pet_start_time = 0
pet_sequence = (4, 0, 1, 2, 3)

idle_wait_time = 2.0
last_idle_action_time = 0

anim_frames = []
anim_durations = []
anim_index = 0
anim_next_time = 0

frames = [
    "/Tomo1.bmp",
    "/Tomo2.bmp",
    "/Tomo3.bmp",
    "/Tomo4.bmp",
    "/Tomo5.bmp",
    "/Tomo6.bmp",
    "/Tomo7.bmp",
    "/Tomo8.bmp"
]

# ------------------------------------------------------------
# 3. HELPER FUNCTIONS
# ------------------------------------------------------------
def is_leap_year(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def date_ordinal(year, month, day):
    month_days = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    total = 365 * (year - 1)
    total += (year - 1) // 4
    total -= (year - 1) // 100
    total += (year - 1) // 400
    for index in range(month - 1):
        total += month_days[index]
    if month > 2 and is_leap_year(year):
        total += 1
    return total + day


def load_focus_data():
    global focus_year, focus_month, focus_day
    global focus_streak, focus_sessions_today, focus_minutes_today
    global focus_total_sessions, focus_total_minutes
    try:
        nvm = microcontroller.nvm
        if nvm is None or len(nvm) < FOCUS_RECORD_SIZE:
            return
        stored = bytes(nvm[0:FOCUS_RECORD_SIZE])
        values = struct.unpack(FOCUS_FORMAT, stored)
        if values[0] != FOCUS_MAGIC:
            return
        (_, focus_year, focus_month, focus_day, focus_streak,
         focus_sessions_today, focus_minutes_today,
         focus_total_sessions, focus_total_minutes) = values
    except Exception as error:
        print("Focus data load error:", error)


def save_focus_data():
    try:
        nvm = microcontroller.nvm
        if nvm is None or len(nvm) < FOCUS_RECORD_SIZE:
            return
        packed = struct.pack(
            FOCUS_FORMAT,
            FOCUS_MAGIC,
            focus_year,
            focus_month,
            focus_day,
            focus_streak,
            focus_sessions_today,
            focus_minutes_today,
            focus_total_sessions,
            focus_total_minutes,
        )
        nvm[0:FOCUS_RECORD_SIZE] = packed
    except Exception as error:
        print("Focus data save error:", error)


def update_focus_display():
    try:
        focus_today_value.text = str(focus_sessions_today)
        focus_minutes_value.text = str(focus_minutes_today) + " min"
        focus_streak_value.text = str(focus_streak) + " days"
        focus_total_value.text = str(focus_total_sessions)
    except Exception:
        pass


def record_focus_session(duration_seconds):
    global focus_year, focus_month, focus_day
    global focus_streak, focus_sessions_today, focus_minutes_today
    global focus_total_sessions, focus_total_minutes
    try:
        now = rtc.datetime
        year = now.tm_year
        month = now.tm_mon
        day = now.tm_mday
    except Exception as error:
        print("RTC focus error:", error)
        return
    minutes = max(1, int(duration_seconds // 60))
    if focus_year == year and focus_month == month and focus_day == day:
        focus_sessions_today += 1
        focus_minutes_today += minutes
    else:
        if focus_year > 0:
            previous_day = date_ordinal(focus_year, focus_month, focus_day)
            current_day = date_ordinal(year, month, day)
            focus_streak = focus_streak + 1 if current_day - previous_day == 1 else 1
        else:
            focus_streak = 1
        focus_year = year
        focus_month = month
        focus_day = day
        focus_sessions_today = 1
        focus_minutes_today = minutes
    focus_total_sessions += 1
    focus_total_minutes += minutes
    save_focus_data()
    update_focus_display()


def get_battery_percentage():
    raw_reading = battery_pin.value
    pin_voltage = (raw_reading / 65535.0) * 3.3
    real_battery_voltage = pin_voltage * 2.0 
    percentage = ((real_battery_voltage - 3.2) / (4.2 - 3.2)) * 100
    percentage = max(0, min(100, int(percentage)))
    return percentage, real_battery_voltage

def play_beep(duration):
    buzzer.value = False
    time.sleep(duration)
    buzzer.value = True
    time.sleep(0.1)

def stop_buzzer():
    buzzer.value = True

def start_finished_alarm():
    global alarm_active, alarm_step, alarm_next_time, finished_from_mode
    global mode, previous_mode, time_remaining, reset_release_required

    finished_from_mode = mode
    alarm_active = True
    alarm_step = 0
    alarm_next_time = time.monotonic()
    mode = mode_5
    previous_mode = mode_5
    time_remaining = 0
    reset_release_required = False
    orientation_buffer.clear()
    time_label.text = "00:00"

    while len(bar_fill_group) > 0:
        bar_fill_group.pop()

def stop_finished_alarm():
    global alarm_active, alarm_step, alarm_next_time, finished_from_mode
    alarm_active = False
    alarm_step = 0
    alarm_next_time = 0
    stop_buzzer()

def reset_timer_state():
    global mode, previous_mode, previous_active_mode
    global time_remaining, current_timer_max, last_tick_time
    global reset_release_required

    stop_finished_alarm()
    mode = mode_7
    previous_mode = mode_7
    previous_active_mode = mode_0
    time_remaining = 0
    current_timer_max = 900
    last_tick_time = time.monotonic()
    reset_release_required = True
    orientation_buffer.clear()

    pause_string.hidden = True
    pause_bar_1.hidden = True
    pause_bar_2.hidden = True
    time_label.y = 110
    bar_outline.y = 145
    bar_fill_group.y = 0
    time_label.text = "00:00"

    while len(bar_fill_group) > 0:
        bar_fill_group.pop()

def handle_finished_orientation(detected):
    global mode, previous_mode, previous_active_mode
    global time_remaining, current_timer_max, last_tick_time
    global reset_release_required, finished_from_mode

    if detected is None or detected == "unknown":
        return False

    # Ignore the same face that started the timer which just finished.
    # The alarm keeps repeating until the cube is moved to a different state.
    if detected == finished_from_mode or detected == mode_5:
        return False

    stop_finished_alarm()
    orientation_buffer.clear()
    reset_release_required = True

    pause_string.hidden = True
    pause_bar_1.hidden = True
    pause_bar_2.hidden = True
    time_label.y = 110
    bar_outline.y = 145
    bar_fill_group.y = 0

    while len(bar_fill_group) > 0:
        bar_fill_group.pop()

    if detected in time_duration:
        mode = detected
        previous_mode = detected
        previous_active_mode = detected
        time_remaining = time_duration[detected]
        current_timer_max = time_duration[detected]
        last_tick_time = time.monotonic()

        minutes = time_remaining // 60
        seconds = time_remaining % 60
        time_label.text = f"{minutes:02d}:{seconds:02d}"
        bar_fill_group.append(Rect(21, 147, 198, 16, fill=0xffffff))

        if detected == mode_1:
            display.rotation = 180
        elif detected == mode_2:
            display.rotation = 90
        elif detected == mode_3:
            display.rotation = 0
        elif detected == mode_4:
            display.rotation = 270

    elif detected == mode_6:
        mode = mode_6
        previous_mode = mode_6
        previous_active_mode = mode_0
        time_remaining = 0
        current_timer_max = 900
        last_tick_time = time.monotonic()
        time_label.text = "00:00"
        pause_string.hidden = False
        pause_bar_1.hidden = False
        pause_bar_2.hidden = False
        time_label.y = 120
        bar_outline.y = 152
        bar_fill_group.y = 7

    elif detected == mode_7:
        reset_timer_state()

    else:
        return False

    finished_from_mode = None
    play_beep(0.1)
    return True

def update_finished_alarm(now):
    global alarm_step, alarm_next_time

    if not alarm_active or now < alarm_next_time:
        return

    if alarm_step < ALARM_BEEPS_PER_BURST * 2:
        if alarm_step % 2 == 0:
            buzzer.value = False
            alarm_next_time = now + ALARM_ON_TIME
        else:
            buzzer.value = True
            alarm_next_time = now + ALARM_OFF_TIME
        alarm_step += 1
    else:
        buzzer.value = True
        alarm_step = 0
        alarm_next_time = now + ALARM_GAP

def update_clock_display():
    clock_time = rtc.datetime
    hour_12 = clock_time.tm_hour % 12
    if hour_12 == 0: 
        hour_12 = 12
    time_str = f"{hour_12}:{clock_time.tm_min:02}"
    clock_label.text = time_str
    clock_label.x = (240 - len(time_str) * 36) // 2
    temp_c = rtc.temperature
    temp_f = (temp_c * 9/5) + 32
    calibrated_temp = temp_f - 13
    temp_string.text = str(int(calibrated_temp))

def auto_rotate():
    accel_x, accel_y, accel_z = mpu.acceleration
    if accel_z < -8.3 and abs(accel_x) < 6 and abs(accel_y) < 6: 
        display.rotation = 0
    elif accel_z > 8.3 and abs(accel_x) < 6 and abs(accel_y) < 6: 
        display.rotation = 180
    elif accel_x < -8.3 and abs(accel_y) < 6 and abs(accel_z) < 6: 
        display.rotation = 90
    elif accel_x > 8.3 and abs(accel_y) < 6 and abs(accel_z) < 6: 
        display.rotation = 270

def get_orientation():
    accel_x, accel_y, accel_z = mpu.acceleration

    abs_x = abs(accel_x)
    abs_y = abs(accel_y)
    abs_z = abs(accel_z)

    # Dominant-axis detection tolerates slight table or hand tilt.
    minimum_axis = 7.0
    dominance_margin = 1.5

    if (
        abs_z >= minimum_axis and
        abs_z >= abs_x + dominance_margin and
        abs_z >= abs_y + dominance_margin
    ):
        raw = mode_3 if accel_z < 0 else mode_1

    elif (
        abs_y >= minimum_axis and
        abs_y >= abs_x + dominance_margin and
        abs_y >= abs_z + dominance_margin
    ):
        raw = mode_6 if accel_y < 0 else mode_7

    elif (
        abs_x >= minimum_axis and
        abs_x >= abs_y + dominance_margin and
        abs_x >= abs_z + dominance_margin
    ):
        raw = mode_2 if accel_x < 0 else mode_4

    else:
        raw = "unknown"

    orientation_buffer.append(raw)

    if len(orientation_buffer) > buffer_size:
        orientation_buffer.pop(0)

    if (
        len(orientation_buffer) == buffer_size and
        len(set(orientation_buffer)) == 1
    ):
        return orientation_buffer[0]

    return None

def check_dock():
    total = 0

    # More averaging helps with USB power and contact noise.
    for _ in range(16):
        total += dock_pin.value
        time.sleep(0.0015)

    raw_val = total / 16

    # Uncomment temporarily to recalibrate after hardware changes:
    # print("Dock ADC:", raw_val)

    # Specific dock buttons.
    if raw_val >= 45000:
        return "home"
    elif 20000 <= raw_val <= 25000:
        return "timer"
    elif 15500 <= raw_val <= 19500:
        return "tomo"
    elif 13950 <= raw_val <= 14500:
        return "button_4"

    # The original dock circuit reports values above about 6000 whenever
    # physical dock contact exists. Keep the device in charging mode even
    # when voltage noise falls between the individual button windows.
    elif raw_val > 6000:
        return "dock_idle"

    return "none"


def get_stable_dock_state(now):
    global last_valid_dock_state, last_valid_dock_time

    detected = check_dock()

    if detected != "none":
        last_valid_dock_state = detected
        last_valid_dock_time = now
        return detected

    # Ignore very brief dropouts caused by USB/contact noise.
    if now - last_valid_dock_time <= DOCK_LOSS_GRACE:
        return last_valid_dock_state

    last_valid_dock_state = "none"
    return "none"

def show_docked_battery_ui():
    percent_label.hidden = True
    image_batcharge_tile.hidden = False
    battery_outline.hidden = True
    battery_tip.hidden = True

    for cell in battery_cells:
        cell.hidden = True

def show_undocked_battery_ui():
    image_batcharge_tile.hidden = True
    battery_outline.hidden = False
    battery_tip.hidden = False

def safe_get_orientation():
    try:
        return get_orientation()
    except Exception as error:
        print("MPU read error:", error)
        return None

def safe_check_dock(now):
    try:
        return get_stable_dock_state(now)
    except Exception as error:
        print("Dock read error:", error)
        return "none"

def safe_update_clock():
    try:
        update_clock_display()
    except Exception as error:
        print("RTC read error:", error)

def safe_auto_rotate():
    try:
        auto_rotate()
    except Exception as error:
        print("MPU rotate error:", error)

def start_idle_animation(frame_sequence, duration_sequence):
    global anim_frames, anim_durations
    global anim_index, anim_next_time, last_idle_action_time

    if not frame_sequence:
        return

    anim_frames = list(frame_sequence)
    anim_durations = list(duration_sequence)

    if len(anim_durations) < len(anim_frames):
        default_duration = (
            anim_durations[-1] if anim_durations else 0.1
        )
        while len(anim_durations) < len(anim_frames):
            anim_durations.append(default_duration)

    anim_index = 0
    set_idle_frame(anim_frames[0])
    anim_next_time = time.monotonic() + anim_durations[0]
    last_idle_action_time = time.monotonic()


def update_idle_animation(now):
    global anim_frames, anim_durations
    global anim_index, anim_next_time, last_idle_action_time

    if not anim_frames:
        return

    if now < anim_next_time:
        return

    anim_index += 1

    if anim_index >= len(anim_frames):
        anim_frames = []
        anim_durations = []
        anim_index = 0
        anim_next_time = 0
        set_idle_frame(0)
        last_idle_action_time = now
        return

    set_idle_frame(anim_frames[anim_index])
    anim_next_time = now + anim_durations[anim_index]


def set_idle_frame(frame_index):
    gc.collect()
    new_bmp = displayio.OnDiskBitmap(frames[frame_index])
    idle_tg.bitmap = new_bmp
    idle_tg.pixel_shader = new_bmp.pixel_shader

def group_contains(group, item):
    for child in group:
        if child is item:
            return True
    return False

def safe_remove(group, item):
    if group_contains(group, item):
        group.remove(item)

def switch_screen(new_screen):
    global current_screen, current_ui, mode, previous_mode
    global previous_active_mode, reset_release_required

    if current_screen == new_screen:
        return

    safe_remove(master_group, current_ui)

    if new_screen == "clock":
        current_ui = Idle_UI
        mode = mode_0
        previous_mode = mode_0
        previous_active_mode = mode_0
        reset_release_required = False
        orientation_buffer.clear()

    elif new_screen == "timer":
        current_ui = Timer_UI

        # Enter timer mode with clean state so returning from idle while
        # resting on the same face still restarts that timer.
        if not alarm_active:
            mode = mode_0
            previous_mode = mode_0
            previous_active_mode = mode_0
            reset_release_required = False
            orientation_buffer.clear()

    elif new_screen == "tomo":
        current_ui = Tomo_UI
        mode = mode_0
        previous_mode = mode_0
        previous_active_mode = mode_0
        reset_release_required = False
        orientation_buffer.clear()

    elif new_screen == "focus":
        current_ui = Focus_UI
        mode = mode_0
        previous_mode = mode_0
        previous_active_mode = mode_0
        reset_release_required = False
        orientation_buffer.clear()
        update_focus_display()

    else:
        return

    master_group.append(current_ui)
    current_screen = new_screen
    display.rotation = 0

# ------------------------------------------------------------
# 4. UI LAYER GENERATION
# ------------------------------------------------------------
master_group = displayio.Group()
display.root_group = master_group

# Global Elements wrapped in Groups for safety
circle_group = displayio.Group()
master_group.append(circle_group)

global_circle = Circle(120, 120, 117, outline=0xFFFFFF)
circle_group.append(global_circle)

battery_group = displayio.Group()
master_group.append(battery_group)

percent_label = label.Label(terminalio.FONT, text="67%", color=0xFFFFFF, x=111, y=185)
battery_group.append(percent_label)

batcharge_bitmap = displayio.OnDiskBitmap("/Battery_Charge.bmp")
image_batcharge_tile = displayio.TileGrid(batcharge_bitmap, pixel_shader=batcharge_bitmap.pixel_shader, x=95, y=193)
image_batcharge_tile.hidden = True
battery_group.append(image_batcharge_tile)

battery_outline = Rect(95, 193, 48, 18, outline=0xFFFFFF)
battery_tip = Rect(143, 197, 2, 10, fill=0xFFFFFF, outline=0xFFFFFF)
battery_group.append(battery_outline)
battery_group.append(battery_tip)

battery_cells = [
    Rect(97, 195, 8, 14, fill=0x4caf50, outline=0x4caf50),
    Rect(106, 195, 8, 14, fill=0x4caf50, outline=0x4caf50),
    Rect(115, 195, 8, 14, fill=0x4caf50, outline=0x4caf50),
    Rect(124, 195, 8, 14, fill=0x4caf50, outline=0x4caf50),
    Rect(133, 195, 8, 14, fill=0x4caf50, outline=0x4caf50)
]

for cell in battery_cells:
    battery_group.append(cell)

# ---- SCREEN 1: CLOCK UI ----
Idle_UI = displayio.Group()
clock_label = label.Label(terminalio.FONT, text="00:00", color=0xFFFFFF, x=30, y=125, scale=6)
Idle_UI.append(clock_label)

thermometer_bitmap = displayio.OnDiskBitmap("/thermometer.bmp")
image_thermometer_tile = displayio.TileGrid(thermometer_bitmap, pixel_shader=thermometer_bitmap.pixel_shader, x=74, y=45)
Idle_UI.append(image_thermometer_tile)

temperature_bitmap = displayio.OnDiskBitmap("/temperature.bmp")
image_temperature_tile = displayio.TileGrid(temperature_bitmap, pixel_shader=temperature_bitmap.pixel_shader, x=135, y=39)
Idle_UI.append(image_temperature_tile)

temp_string = label.Label(terminalio.FONT, text="0", color=0xFFFFFF, x=101, y=62, scale=3)
Idle_UI.append(temp_string)

# ---- SCREEN 2: TIMER UI ----
Timer_UI = displayio.Group()
time_label = label.Label(terminalio.FONT, text="00:00", color=0xFFFFFF, x=30, y=110, scale=6)
Timer_UI.append(time_label)

bar_outline = Rect(19, 145, 202, 20, outline=0xffffff)
Timer_UI.append(bar_outline)

bar_fill_group = displayio.Group()
Timer_UI.append(bar_fill_group)
bar_fill_group.append(Rect(21, 147, 198, 16, fill=0xffffff))

pause_bar_1 = Rect(124, 22, 9, 29, fill=0xffffff, outline=0xffffff)
pause_bar_1.hidden = True
pause_bar_2 = Rect(107, 22, 9, 29, fill=0xffffff, outline=0xffffff)
pause_bar_2.hidden = True

pause_string = label.Label(terminalio.FONT, text="Paused...", color=0xFFFFFF, x=79, y=77, scale=2)
pause_string.hidden = True

Timer_UI.append(pause_bar_1)
Timer_UI.append(pause_bar_2)
Timer_UI.append(pause_string)

# ---- SCREEN 3: TOMO UI ----
Tomo_UI = displayio.Group()

idle_bmp = displayio.OnDiskBitmap(frames[0])
idle_tg = displayio.TileGrid(idle_bmp, pixel_shader=idle_bmp.pixel_shader, width=1, height=1, tile_width=idle_bmp.width, tile_height=idle_bmp.height)
idle_tg.x = (240 - idle_bmp.width) // 2
idle_tg.y = (240 - idle_bmp.height) // 2
Tomo_UI.append(idle_tg)

pet_bmp = displayio.OnDiskBitmap("/pet_sheet.bmp")
pet_tg = displayio.TileGrid(pet_bmp, pixel_shader=pet_bmp.pixel_shader, width=5, height=1, tile_width=240, tile_height=240)
pet_tg.x = -20
pet_tg.y = -30 
pet_tg.hidden = True
Tomo_UI.append(pet_tg)

# ---- SCREEN 4: FOCUS TRACKER ----
Focus_UI = displayio.Group()

focus_title = label.Label(terminalio.FONT, text="STATS", color=0xFFFFFF, x=75, y=35, scale=3)
Focus_UI.append(focus_title)
focus_today_caption = label.Label(terminalio.FONT, text="Today:", color=0xFFFFFF, x=35, y=79, scale=2)
Focus_UI.append(focus_today_caption)
focus_today_value = label.Label(terminalio.FONT, text="0", color=0xFFFFFF, x=166, y=79, scale=2)
Focus_UI.append(focus_today_value)
focus_minutes_caption = label.Label(terminalio.FONT, text="Minutes:", color=0xFFFFFF, x=35, y=111, scale=2)
Focus_UI.append(focus_minutes_caption)
focus_minutes_value = label.Label(terminalio.FONT, text="0 min", color=0xFFFFFF, x=135, y=111, scale=2)
Focus_UI.append(focus_minutes_value)
focus_streak_caption = label.Label(terminalio.FONT, text="Streak:", color=0xFFFFFF, x=35, y=143, scale=2)
Focus_UI.append(focus_streak_caption)
focus_streak_value = label.Label(terminalio.FONT, text="0 days", color=0xFFFFFF, x=135, y=143, scale=2)
Focus_UI.append(focus_streak_value)
focus_total_caption = label.Label(terminalio.FONT, text="Total:", color=0xFFFFFF, x=35, y=175, scale=2)
Focus_UI.append(focus_total_caption)
focus_total_value = label.Label(terminalio.FONT, text="0", color=0xFFFFFF, x=166, y=175, scale=2)
Focus_UI.append(focus_total_value)

# ---- SHUTDOWN UI ----
Shutdown_UI = displayio.Group()
shut_string = label.Label(terminalio.FONT, text="Shutting", color=0xFFFFFF, x=48, y=116, scale=3)
down_string = label.Label(terminalio.FONT, text="Down", color=0xFFFFFF, x=74, y=165, scale=3)
moon_bitmap = displayio.OnDiskBitmap("/moon.bmp")
image_moon_tile = displayio.TileGrid(moon_bitmap, pixel_shader=moon_bitmap.pixel_shader, x=107, y=26)

Shutdown_UI.append(shut_string)
Shutdown_UI.append(down_string)
Shutdown_UI.append(image_moon_tile)

gc.collect()

# ------------------------------------------------------------
# 5. STARTUP INITIALIZATION
# ------------------------------------------------------------
load_focus_data()
update_focus_display()
current_ui = Idle_UI
master_group.append(current_ui)
safe_update_clock()
display.rotation = 0

batt_pct, _ = get_battery_percentage()
percent_label.text = f"{batt_pct}%"
last_battery_tick = time.monotonic()
last_clock_tick = time.monotonic()
tomo_press_start_time = time.monotonic()
display.refresh()

# ------------------------------------------------------------
# 6. MASTER LOOP
# ------------------------------------------------------------
while True:
    current_time = time.monotonic()
    dock_state = safe_check_dock(current_time)
    is_docked = dock_state in DOCKED_STATES

    update_finished_alarm(current_time)

    if alarm_active and not is_docked:
        detected = safe_get_orientation()
        if handle_finished_orientation(detected):
            switch_screen("timer")
    
    # --- 1. CONTINUOUS BATTERY LOGIC ---
    if current_time - last_battery_tick >= battery_interval:
        batt_pct, batt_volts = get_battery_percentage()
        last_battery_tick = current_time

        if is_docked:
            show_docked_battery_ui()
        else:
            show_undocked_battery_ui()
            percent_label.hidden = False
            percent_label.text = f"{batt_pct}%"

            if batt_pct >= 80:
                active_color = 0x4caf50
            elif batt_pct >= 60:
                active_color = 0xCDDC39
            elif batt_pct >= 40:
                active_color = 0xFFEB3B
            elif batt_pct >= 20:
                active_color = 0xFF9800
            else:
                active_color = 0xF44336

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

    # --- 2. DOCKING / BUTTON SWITCHING LOGIC ---
    if not alarm_active:
        dock_changed = is_docked and (
            not was_docked or dock_state != last_dock_state
        )

        if dock_changed:
            show_docked_battery_ui()
            display.rotation = 180

            if dock_state == "home":
                switch_screen("clock")
                display.rotation = 180
                safe_update_clock()

            elif dock_state == "timer":
                switch_screen("timer")
                display.rotation = 180
                play_beep(0.1)

                if mode != "increment":
                    mode = "increment"
                    previous_mode = "increment"
                    time_remaining = 900
                    current_timer_max = 900
                else:
                    time_remaining = min(
                        MAX_INCREMENT_SECONDS,
                        time_remaining + 900
                    )
                    current_timer_max = min(
                        MAX_INCREMENT_SECONDS,
                        current_timer_max + 900
                    )

                minutes = time_remaining // 60
                seconds = time_remaining % 60
                time_label.text = f"{minutes:02d}:{seconds:02d}"
                last_tick_time = time.monotonic()
                orientation_buffer.clear()

            elif dock_state == "tomo":
                switch_screen("tomo")
                display.rotation = 180
                tomo_press_start_time = current_time

            elif dock_state == "button_4":
                switch_screen("focus")
                display.rotation = 180
                update_focus_display()
                play_beep(0.1)

            elif dock_state == "dock_idle":
                # Physical dock contact without a specific button press.
                # Keep the charging UI active and preserve the current screen.
                pass

        elif not is_docked and was_docked:
            show_undocked_battery_ui()
            last_battery_tick = 0

    # --- 3. HOLDING TOMO LOGIC ---
    if not alarm_active and dock_state == "tomo":
        if not is_petting and (current_time - tomo_press_start_time > 1.5):
            is_petting = True
            pet_tg.hidden = False
            idle_tg.hidden = True
            circle_group.hidden = True
            battery_group.hidden = True
    else:
        if is_petting:
            is_petting = False
            pet_tg.hidden = True
            idle_tg.hidden = False
            circle_group.hidden = False
            battery_group.hidden = False
            set_idle_frame(0)

    was_docked = is_docked
    last_dock_state = dock_state

    # --- 4. SHUTDOWN & CUBE BUTTON LOGIC ---
    if not button.value:
        power_button = time.monotonic()
        show_shutdown = False
        ui_before_shutdown = current_ui
        screen_before_shutdown = current_screen
        alarm_was_active = alarm_active

        # The alarm scheduler cannot run inside the button-hold loop.
        # Force the active-low buzzer OFF so it cannot become stuck on.
        stop_buzzer()
        
        percent_label.hidden = True 
        image_batcharge_tile.hidden = True
        battery_outline.hidden = True
        battery_tip.hidden = True 
        
        for cell in battery_cells: 
            cell.hidden = True
        
        while not button.value:
            power_timer = time.monotonic() - power_button
            
            if power_timer >= 1 and not show_shutdown:
                if current_ui != Shutdown_UI:
                    safe_remove(master_group, current_ui)
                    current_ui = Shutdown_UI
                    master_group.append(current_ui)
                show_shutdown = True
                display.refresh()

            if power_timer >= 1:
                down_string.text = "Down"
            if power_timer >= 1.5:
                down_string.text = "Down."
            if power_timer >= 2:
                down_string.text = "Down.."
            if power_timer >= 2.5:
                down_string.text = "Down..."

            # display.auto_refresh is False, so manually draw each
            # shutdown animation step while the button remains held.
            if show_shutdown:
                display.refresh()

            if power_timer >= 3:
                stop_buzzer()
                play_beep(0.5)
                stop_buzzer()

                # Draw a real black frame before sleeping. Merely assigning an
                # empty group can leave the TFT showing its previous pixels.
                blank_bitmap = displayio.Bitmap(1, 1, 1)
                blank_palette = displayio.Palette(1)
                blank_palette[0] = 0x000000
                blank_tile = displayio.TileGrid(
                    blank_bitmap,
                    pixel_shader=blank_palette
                )
                blank_group = displayio.Group(scale=240)
                blank_group.append(blank_tile)
                display.root_group = blank_group
                display.refresh()
                time.sleep(0.15)

                # This turns the backlight off only when the display's BL pin
                # is connected to a backlight pin supported by the driver.
                try:
                    display.brightness = 0.0
                except Exception:
                    pass

                # The shutdown button is still being held at this point.
                # Wait for release so the NEXT press becomes the wake event.
                while not button.value:
                    time.sleep(0.02)

                button.deinit()
                time.sleep(0.05)

                pin_alarm = alarm.pin.PinAlarm(
                    pin=board.D3,
                    value=False,
                    edge=False,
                    pull=True
                )
                alarm.exit_and_deep_sleep_until_alarms(pin_alarm)
                
            time.sleep(0.05)
            
        if show_shutdown:
            safe_remove(master_group, current_ui)
            current_ui = ui_before_shutdown
            current_screen = screen_before_shutdown
            master_group.append(current_ui)
            down_string.text = "Down"
            
        else:
            if not is_docked:
                if alarm_active:
                    # Short press during the finished alarm:
                    # stop the alarm and return to the clock/idle screen.
                    stop_finished_alarm()
                    finished_from_mode = None
                    mode = mode_0
                    previous_mode = mode_0
                    previous_active_mode = mode_0
                    time_remaining = 0
                    current_timer_max = 900
                    reset_release_required = False
                    orientation_buffer.clear()

                    pause_string.hidden = True
                    pause_bar_1.hidden = True
                    pause_bar_2.hidden = True
                    time_label.y = 110
                    bar_outline.y = 145
                    bar_fill_group.y = 0
                    time_label.text = "00:00"

                    while len(bar_fill_group) > 0:
                        bar_fill_group.pop()

                    switch_screen("clock")
                    safe_update_clock()
                    play_beep(0.1)
                else:
                    play_beep(0.1)
                    if current_screen == "clock":
                        switch_screen("timer")
                        time_remaining = 0
                        current_timer_max = 900
                        last_tick_time = time.monotonic()
                        time_label.text = "00:00"

                        while len(bar_fill_group) > 0:
                            bar_fill_group.pop()

                    elif current_screen == "timer":
                        # Standalone cube only toggles between Clock and Timer.
                        switch_screen("clock")

                    else:
                        switch_screen("clock")

        last_battery_tick = 0
        time.sleep(0.2)
        continue
            
    # --- 5. SCREEN-SPECIFIC ROUTINES ---
    
    # A. Clock Screen
    if current_screen == "clock":
        if current_time - last_clock_tick >= CLOCK_INTERVAL:
            safe_update_clock()
            last_clock_tick = current_time
        if not is_docked:
            safe_auto_rotate()
            
    # B. Tomo Screen
    elif current_screen == "tomo":
        if is_petting:
            if current_time - pet_start_time > 0.08:
                pet_frame_index = (pet_frame_index + 1) % len(pet_sequence)
                pet_tg[0] = pet_sequence[pet_frame_index]
                pet_start_time = current_time
        else:
            if anim_frames:
                update_idle_animation(current_time)
            elif current_time - last_idle_action_time > idle_wait_time:
                dice_roll = random.randint(1, 100)

                if dice_roll <= 7:
                    start_idle_animation(
                        [3, 1, 4, 1, 3, 1, 4, 1, 3, 1, 4, 1],
                        [0.3] * 12
                    )
                elif dice_roll <= 17:
                    start_idle_animation(
                        [7, 0, 7, 0],
                        [1.0, 1.0, 1.0, 1.0]
                    )
                elif dice_roll <= 27:
                    start_idle_animation(
                        [5, 6, 5, 6],
                        [1.0, 1.0, 1.0, 1.0]
                    )
                else:
                    start_idle_animation(
                        [1, 2, 1],
                        [0.04, 0.1, 0.04]
                    )

    # C. Timer Screen
    elif current_screen == "timer":
        if not is_docked and not alarm_active:
            detected = safe_get_orientation()

            if reset_release_required:
                if detected in (None, "unknown"):
                    reset_release_required = False
                    orientation_buffer.clear()
            elif detected is not None and detected != "unknown":
                mode = detected

        if not alarm_active and mode != previous_mode:
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
                resuming = (
                    previous_mode == mode_6 and
                    time_remaining > 0 and
                    mode == previous_active_mode
                )
                if not resuming:
                    time_remaining = time_duration[mode]
                    current_timer_max = time_duration[mode]

            elif mode == mode_7:
                reset_timer_state()

            previous_mode = mode
            last_tick_time = time.monotonic()

            if mode == mode_1:
                display.rotation = 180
            elif mode == mode_2:
                display.rotation = 90
            elif mode == mode_3:
                display.rotation = 0
            elif mode == mode_4:
                display.rotation = 270

        if (
            not alarm_active and
            (mode in time_duration or mode == "increment") and
            time_remaining > 0
        ):
            if current_time - last_tick_time >= 1.0:
                elapsed_seconds = int(current_time - last_tick_time)
                time_remaining = max(0, time_remaining - elapsed_seconds)
                last_tick_time += elapsed_seconds

                minutes = time_remaining // 60
                seconds = time_remaining % 60
                time_label.text = f"{minutes:02d}:{seconds:02d}"

                total_time = (
                    current_timer_max
                    if mode == "increment"
                    else time_duration[mode]
                )
                if total_time <= 0:
                    total_time = 1

                bar_scaler = max(0.0, min(1.0, time_remaining / total_time))
                bar_width = int(198 * bar_scaler)

                while len(bar_fill_group) > 0:
                    bar_fill_group.pop()

                if bar_width > 0:
                    bar_fill_group.append(
                        Rect(21, 147, bar_width, 16, fill=0xffffff)
                    )

        if (
            not alarm_active and
            time_remaining <= 0 and
            (mode in time_duration or mode == "increment")
        ):
            completed_seconds = (
                current_timer_max
                if mode == "increment"
                else time_duration[mode]
            )
            record_focus_session(completed_seconds)
            start_finished_alarm()

    refresh_interval = (
        DOCKED_REFRESH_INTERVAL if is_docked
        else UNDOCKED_REFRESH_INTERVAL
    )

    if current_time - last_display_refresh >= refresh_interval:
        display.refresh()
        last_display_refresh = current_time

    time.sleep(0.005)
