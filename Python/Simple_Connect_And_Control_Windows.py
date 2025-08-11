#Windows OS
#install: pip install pyserial

import serial
import time

ser = serial.Serial('COM19',115200, timeout = 1)  # open serial port
time.sleep(2)    
print(ser.readline())

gcodes = []
gcodes.append('G28')
gcodes.append('G01 Z-320')
gcodes.append('G01 X-100')
gcodes.append('G01 Z-350')

gcodes.append('G01 Z-320')
gcodes.append('G01 X100')
gcodes.append('G01 Z-350')

gcodes.append('G01 Z-320')
gcodes.append('G01 X100 Y100')
gcodes.append('G01 Z-350')

gcodes.append('G01 X-100 Y-100 Z-320')
gcodes.append('G01 Z-350')
gcodes.append('G28')

for gcode in gcodes:
    print(gcode)
    gcodeLine = gcode + '\n'
    ser.write(gcodeLine.encode())
    while 1:
        response = ser.readline()
        print(response)
        if (response.find('Ok'.encode()) > -1):
            break

ser.close()