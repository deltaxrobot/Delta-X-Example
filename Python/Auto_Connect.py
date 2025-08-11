import time

import serial
from serial.tools import list_ports


BAUD = 115200


def send_gcode(ser: serial.Serial, command: str, timeout: float = 2.0) -> str:
    """Send one G-code line and return the immediate response.

    - Clears any stale bytes before sending to avoid delayed prints.
    - Appends "\n" if missing.
    - Waits up to `timeout` seconds for the first non-empty response line.
    - Skips an echoed line identical to the sent command (if any).
    """
    # Clear any leftover from previous transactions so we only read fresh response
    try:
        ser.reset_input_buffer()
    except Exception:
        pass

    sent_line = command if command.endswith("\n") else command + "\n"
    ser.write(sent_line.encode("utf-8"))
    try:
        ser.flush()
    except Exception:
        pass

    deadline = time.monotonic() + timeout
    sent_stripped = command.strip()
    while time.monotonic() < deadline:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if not line:
            continue
        # Ignore possible echo of our command
        if line == sent_stripped:
            continue
        return line
    return ""


def connect_delta_robot(baud: int = BAUD, timeout: float = 1.0) -> serial.Serial | None:
    """Scan COM ports, identify Delta X by 'IsDelta' → 'YesDelta', and return an OPEN serial port.

    The returned port is left OPEN for further use by the caller.
    """
    for port in list_ports.comports():
        name = port.device
        try:
            ser = serial.Serial(name, baud, timeout=timeout)
            time.sleep(0.3)
            ser.reset_input_buffer()

            ser.write(b"IsDelta\n")
            reply = ser.readline().decode("utf-8", errors="ignore").strip()
            if "YesDelta" in reply:
                return ser  # KEEP OPEN

            ser.close()
        except Exception:
            # Ignore ports that cannot be opened or read
            pass
    return None


def main():
    print(f"Scanning COM ports at {BAUD} baud...")
    ser = connect_delta_robot(BAUD, timeout=1)
    if ser is None:
        print("No Delta X robot found.")
        return

    print(f"Found Delta X robot on {ser.port}")

    # Example: query current position using the helper, keep port OPEN
    pos = send_gcode(ser, "Position")
    print(f"Position: {pos}")

    # Optional simple interactive loop, type 'exit' to quit
    print("You can now type G-code lines to send (type 'exit' to quit):")
    try:
        while True:
            line = input(">> ").strip()
            if not line:
                continue
            if line.lower() in {"exit", "quit"}:
                break
            response = send_gcode(ser, line)
            print(f"<< {response}")
    except KeyboardInterrupt:
        pass

    # Note: not closing the port here so it can be reused if imported elsewhere.


if __name__ == "__main__":
    main()


def send_gcode(ser: serial.Serial, command: str) -> str:
    """Send a single G-code line to the robot and return the first response line.

    - Ensures the command ends with a newline "\n".
    - Returns the decoded line with surrounding whitespace trimmed. May be 'Ok' or data.
    """
    if not command.endswith("\n"):
        command = command + "\n"
    ser.write(command.encode("utf-8"))
    return ser.readline().decode("utf-8", errors="ignore").strip()


