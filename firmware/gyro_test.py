import time
import board
import busio
import adafruit_mpu6050

# Open the physical hardware bridge (SCL first, SDA second)
i2c = busio.I2C(board.D5, board.D4)
mpu = adafruit_mpu6050.MPU6050(i2c)

print("--- MPU-6050 SENSOR ONLINE ---")

while True:
    gyro_x,  gyro_y, gyro_z = mpu.gyro
    print(f"X_gyro: {gyro_x:.2f} | Y_gyro: {gyro_y:.2f}   | Z_gyro : {gyro_z:.2f}")
    
    time.sleep(0.2)
    
