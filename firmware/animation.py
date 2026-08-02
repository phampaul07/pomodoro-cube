import board
import busio
import displayio
import fourwire
import time
import random
import gc
from adafruit_gc9a01a import GC9A01A

# 1. Release any existing displays
displayio.release_displays()

# 2. Set up the SPI bus EXACTLY like your main code
spi = busio.SPI(clock=board.D8, MOSI=board.D10)

tft_dc = board.D2
tft_cs = board.D9
tft_rst = board.D6 

# 3. Create the display bus and display object
FourWire = fourwire.FourWire
display_bus = FourWire(spi, command=tft_dc, chip_select=tft_cs, reset=tft_rst, baudrate=60000000)
display = GC9A01A(display_bus, width=240, height=240)

# 4. Create the main UI group
main_group = displayio.Group()
display.root_group = main_group

# 5. File paths for ALL 5 frames
frames = [
    "/Tomo1.bmp", # Index 0: Open
    "/Tomo2.bmp", # Index 1: Half
    "/Tomo3.bmp", # Index 2: Closed
    "/Tomo4.bmp", # Index 3: Left
    "/Tomo5.bmp"  # Index 4: Right
]

# 6. Initial Load (Eyes Open)
gc.collect()
bitmap = displayio.OnDiskBitmap(frames[0])

# 7. Wrap it in a TileGrid 
tile_grid = displayio.TileGrid(
    bitmap,
    pixel_shader=bitmap.pixel_shader,
    width=1,
    height=1,
    tile_width=bitmap.width,
    tile_height=bitmap.height
)

# 8. Center the image dynamically! 
tile_grid.x = (240 - bitmap.width) // 2
tile_grid.y = (240 - bitmap.height) // 2

# 9. Put it on the screen!
main_group.append(tile_grid)

# --- HELPER FUNCTION FOR MEMORY-SAFE SWAPPING ---
def set_frame(frame_index):
    gc.collect() # Clean up RAM before loading the new image
    new_bmp = displayio.OnDiskBitmap(frames[frame_index])
    tile_grid.bitmap = new_bmp
    tile_grid.pixel_shader = new_bmp.pixel_shader

# 10. The Idle Animation Loop
print("Tomo Idle Animation Running (Now with dancing)!")

while True:
    try:
        # Step A: Keep eyes open for a random amount of time (between 2 and 5 seconds)
        set_frame(0)
        time.sleep(random.uniform(2.0, 5.0))
        
        # Roll a 10-sided dice!
        dice_roll = random.randint(1, 10)
        
        # 20% Chance to Dance
        if dice_roll <= 2: 
            # The Dance Sequence (Loops 3 times)
            for _ in range(3):
                set_frame(3) # Left
                time.sleep(0.3)
                
                set_frame(1) # Half Closed
                time.sleep(0.3)
                
                set_frame(4) # Right
                time.sleep(0.3)
                
                set_frame(1) # Half Closed
                time.sleep(0.3)
                
        # 80% Chance to do a normal blink
        else:
            set_frame(1) # Half
            time.sleep(0.04) 
            
            set_frame(2) # Closed
            time.sleep(0.1)  
            
            set_frame(1) # Half
            time.sleep(0.04) 
        
    except MemoryError:
        # Just in case the ESP32 hiccups, catch it and reset the loop
        print("Memory collected, continuing animation...")
        gc.collect()
        time.sleep(0.5)