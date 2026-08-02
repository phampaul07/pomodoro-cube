import time
import board
import digitalio

# Setup the active buzzer on D1
buzzer = digitalio.DigitalInOut(board.D1)
buzzer.direction = digitalio.Direction.OUTPUT

def play_beep(duration):
    buzzer.value = False   # Power ON (Beep!)
    time.sleep(duration)
    buzzer.value = True  # Power OFF (Silence)
    time.sleep(0.1)       # Tiny gap between consecutive beeps

# Play a double-beep
play_beep(0.1)
print ("Done!")


 