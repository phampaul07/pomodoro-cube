import time
import board
import busio
import analogio
import terminalio
import displayio
import fourwire
from adafruit_gc9a01a import GC9A01A
from adafruit_display_text import label

# --- Display Setup ---
displayio.release_displays()
spi = busio.SPI(clock=board.D8, MOSI=board.D10)
# Notice we are using D9 for the chip_select here!
display_bus = fourwire.FourWire(spi, command=board.D2, chip_select=board.D9, reset=board.D6, baudrate=60000000)
display = GC9A01A(display_bus, width=240, height=240)

# --- Dock Pin Setup ---
# D3 is now acting as our Analog Reader
dock_pin = analogio.AnalogIn(board.A1) 

# --- UI Setup ---
main_group = displayio.Group()
display.root_group = main_group

status_label = label.Label(terminalio.FONT, text="Dock Idle", color=0xFFFFFF, scale=4)
status_label.x = 25
status_label.y = 120
main_group.append(status_label)

print("Dock Button Test Started!")

while True:
    raw_val = dock_pin.value
    
    # Based on your brilliant 10k Daisy-Chain Resistor Ladder:
    # Btn 1 (0 ohms added)  = ~3.3V  (Raw ADC: ~65000)
    # Btn 2 (10k ohms added)= ~1.65V (Raw ADC: ~32000)
    # Btn 3 (20k ohms added)= ~1.10V (Raw ADC: ~21000)
    # Btn 4 (30k ohms added)= ~0.82V (Raw ADC: ~16000)
    
    if raw_val > 50000:
        status_label.text = "Mode 1"
        status_label.x = 45
        print(f"Button 1 Pressed | Raw ADC: {raw_val}")
        
    elif raw_val > 27000:
        status_label.text = "Mode 2"
        status_label.x = 45
        print(f"Button 2 Pressed | Raw ADC: {raw_val}")
        
    elif raw_val > 18000:
        status_label.text = "Mode 3"
        status_label.x = 45
        print(f"Button 3 Pressed | Raw ADC: {raw_val}")
        
    elif raw_val > 10000:
        status_label.text = "Mode 4"
        status_label.x = 45
        print(f"Button 4 Pressed | Raw ADC: {raw_val}")
        
    else:
        # No button pressed (Reads close to 0)
        status_label.text = "Dock Idle"
        status_label.x = 25
        
    time.sleep(0.1) # Fast polling so it feels responsive
