# Example

## Delta X Robot Control Overview

- All Delta X Robotics delta robot product lines are controlled via standard G-code commands.
- You can connect over USB (COM serial port) or over Ethernet.
- Any device or programming language that can communicate with a serial COM port can control the robot.
- For the full list of supported G-code commands and device-specific details, see the official documentation: [Delta X Robot Docs](https://docs.deltaxrobot.com/).

### Command and Response Basics

- Every command you send to the robot must end with a newline character `\n`.
- After a G-code command is processed, the robot returns a response. Typically, it replies with `Ok\n` (every response also ends with `\n`).
- To query the current robot position, send the command `Position\n`.
- To verify that a COM port is connected to a Delta X robot, send `IsDelta\n`; the robot will respond with `YesDelta\n`.

### Serial Testing Tip (Windows)

- For quick G-code testing on Windows, use the Termite software.
- Download: [Termite (serial terminal)](https://www.compuphase.com/software_termite.htm)
- Suggested settings:
  - Port: the COM port assigned to your robot (e.g., `COM5`)
  - Baud rate: 115200 (or the value configured on your robot)
  - Transmit: append newline (`\n`) to each line
  - Receive: display newlines
- Example manual session (each line ends with `\n`):

```
>> G28
<< Ok
>> Position
<< 0.00,-0.00,-291.28
>> G1 Z-100 F1000
<< Ok
```

### Coordinate System and Safety Notes

- The end-effector Z value is negative during normal operation because the origin plane (Z = 0) lies on the plane of the three motor axes. The robot works below this plane.
- The home Z height depends on the specific Delta X robot model.
- From the home position, do not issue X/Y moves immediately. First move straight down along Z to enter the safe working volume (recommend around 100 mm), then perform any X/Y moves.

Safe start sequence (each line ends with `\n`):

```
G28
G1 Z-100
G1 X100 Y0
```

### Quick Example

Minimal G-code session (each line ends with `\n`):

Delta X 1
```
G28
Position
G1 X100 Y0 Z-250 F2000
```

Python example using a COM port (USB) with `pyserial`:

```python
import serial

ser = serial.Serial('COM5', 115200, timeout=1)

def send(command: str) -> None:
    ser.write((command + '\n').encode('utf-8'))
    response = ser.readline().decode('utf-8', errors='ignore').strip()
    print(response)  # e.g., 'Ok'

# Home, move, then read current position
send('G28')
send('G1 X100 Y0 Z-250 F500')
send('Position')  # e.g., 'X:100.000 Y:0.000 Z:-50.000'

ser.close()
```

For full command references and device details, see: [Delta X Robot Docs](https://docs.deltaxrobot.com/).