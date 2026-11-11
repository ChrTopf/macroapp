#!/usr/bin/env python3
"""
Turn the button of an Arduino buzzer into a shell command on this machine.

The Arduino sends one line per button press:

    KEY:<index>

Every press executes the shell command given with --command, regardless of the
index. The command is started in the background, so a long-running command does
not block further button presses.

If --port or --baud is omitted, the program asks for it interactively.

Usage:  python3 serial_keyboard.py --port /dev/ttyUSB0 --baud 9600 --command "notify-send GO"
"""

import subprocess
import sys
from argparse import ArgumentParser, ArgumentTypeError, Namespace

from serial import SerialException
from serial.tools.list_ports import comports

from serial_input.arduino_interface import DEFAULT_BAUD_RATE, ArduinoInterface


def non_empty_command(text: str) -> str:
    if not text.strip():
        raise ArgumentTypeError("The command must not be empty.")
    return text


def execute(command: str) -> None:
    """Starts the shell command in the background without waiting for it to finish."""
    try:
        subprocess.Popen(command, shell=True)
    except OSError as e:
        print(f"Failed to execute '{command}': {e}")
        return
    print(f"Executed '{command}'")


def choose_port() -> str:
    ports = sorted(comports(), key=lambda port_info: port_info.device)
    if not ports:
        print("No serial ports found.")
        sys.exit(1)

    print("Available ports:")
    for number, port_info in enumerate(ports, start=1):
        print(f"  [{number}] {port_info.device}: {port_info.description}")

    while True:
        choice = input(f"Choose a port [1-{len(ports)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(ports):
            return ports[int(choice) - 1].device
        print("Invalid choice.")


def choose_baud_rate() -> int:
    while True:
        choice = input(f"Baud rate [{DEFAULT_BAUD_RATE}]: ").strip()
        if not choice:
            return DEFAULT_BAUD_RATE
        if choice.isdigit():
            return int(choice)
        print("Invalid baud rate.")


def parse_arguments() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument("--port", help="The serial port of the Arduino, e.g. /dev/ttyUSB0 or COM3 (asked for if omitted).", type=str)
    parser.add_argument("--baud", help=f"The baud rate of the serial connection (asked for if omitted, default {DEFAULT_BAUD_RATE}).", type=int)
    parser.add_argument("--command", help="The shell command executed on every button press, e.g. 'notify-send GO'.", type=non_empty_command, required=True)
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    port = arguments.port or choose_port()
    baud_rate = arguments.baud or choose_baud_rate()

    print(f"Connecting to Arduino on {port} at {baud_rate} baud...")
    try:
        with ArduinoInterface(port, baud_rate) as arduino:
            print(f"Connected! Command: {arguments.command}")
            print("Press Ctrl+C to exit")
            while True:
                if arduino.read_index() is not None:
                    execute(arguments.command)
    except SerialException as e:
        print(f"Serial error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()
