"""
Light Control Test — verifies we can control the downlight via BLE.

Strategy:
    1. Poll GET_STATUS to get current state
    2. Send SET_STATE with current state + changed light value
    3. Poll GET_STATUS again to confirm

Usage:
    python test_light.py 50:8C:B1:4A:16:A0
"""

import asyncio
import sys
import os
from datetime import datetime

from bleak import BleakClient

CHAR_WRITE  = "0000e001-0000-1000-8000-00805f9b34fb"
CHAR_NOTIFY = "0000e002-0000-1000-8000-00805f9b34fb"

START_BYTE     = 0x53
CMD_GET_STATUS = 0x30
CMD_SET_STATE  = 0x31

log_file = None
last_response = None


def log(msg: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{timestamp}] {msg}"
    print(line)
    if log_file:
        log_file.write(line + "\n")
        log_file.flush()


def format_bytes(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def build_command(cmd, speed=0, direction=0, uplight=0, downlight=0,
                  timer_lo=0, timer_hi=0, fan_type=0) -> bytes:
    packet = bytearray(10)
    packet[0] = START_BYTE
    packet[1] = cmd
    packet[2] = speed
    packet[3] = direction
    packet[4] = uplight
    packet[5] = downlight
    packet[6] = timer_lo
    packet[7] = timer_hi
    packet[8] = fan_type
    packet[9] = sum(packet[0:9]) & 0xFF
    return bytes(packet)


def notification_handler(sender, data: bytearray):
    global last_response
    last_response = list(data)
    log(f"NOTIFY: {format_bytes(data)}")
    b = last_response
    if len(b) >= 10:
        log(f"  speed={b[2]} dir={b[3]} uplight={b[4]} downlight={b[5]} "
            f"timer={b[6]|b[7]<<8} fantype={b[8]} chk=0x{b[9]:02X}")


async def get_status(client) -> list:
    global last_response
    last_response = None
    cmd = build_command(CMD_GET_STATUS)
    await client.write_gatt_char(CHAR_WRITE, cmd)
    await asyncio.sleep(1)
    return last_response


async def set_state(client, speed, direction, uplight, downlight,
                    timer_lo=0, timer_hi=0, fan_type=0) -> list:
    global last_response
    last_response = None
    cmd = build_command(CMD_SET_STATE, speed, direction, uplight, downlight,
                        timer_lo, timer_hi, fan_type)
    log(f"SEND SET_STATE: {format_bytes(cmd)}")
    await client.write_gatt_char(CHAR_WRITE, cmd)
    await asyncio.sleep(1)
    return last_response


def confirm(prompt: str) -> bool:
    while True:
        resp = input(f"\n{prompt} [y/n]: ").strip().lower()
        if resp in ("y", "yes"):
            return True
        if resp in ("n", "no"):
            return False


async def main():
    global log_file

    os.makedirs("logs", exist_ok=True)
    log_filename = f"logs/test_light_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_file = open(log_filename, "w", encoding="utf-8")

    mac = sys.argv[1] if len(sys.argv) > 1 else "50:8C:B1:4A:16:A0"
    log(f"Connecting to {mac}...")

    async with BleakClient(mac, timeout=20.0) as client:
        log("CONNECTED")
        await client.start_notify(CHAR_NOTIFY, notification_handler)

        # Step 1: Get current state
        log("")
        log("=== STEP 1: Get current state ===")
        status = await get_status(client)
        if not status:
            log("ERROR: No response to GET_STATUS")
            return

        cur_speed = status[2]
        cur_dir = status[3]
        cur_uplight = status[4]
        cur_downlight = status[5]
        log(f"Current: speed={cur_speed} dir={cur_dir} "
            f"uplight={cur_uplight} downlight={cur_downlight}")

        # Step 2: Test light ON with known-good value (65 = default from remote)
        log("")
        log("=== STEP 2: Turn light ON (downlight=65, preserving current speed/dir) ===")
        cmd_desc = (f"SET_STATE: speed={cur_speed} dir={cur_dir} "
                    f"uplight={cur_uplight} downlight=65")
        log(f"Will send: {cmd_desc}")
        if confirm("Send light ON (downlight=65)?"):
            await set_state(client, cur_speed, cur_dir, cur_uplight, 65)
            log("Polling status...")
            await get_status(client)
            input("\n>> Did the light turn on? (press Enter to continue) ")

        # Step 3: Test dimming (downlight=22)
        log("")
        log("=== STEP 3: Dim light (downlight=22) ===")
        if confirm("Send light DIM (downlight=22)?"):
            await set_state(client, cur_speed, cur_dir, cur_uplight, 22)
            log("Polling status...")
            await get_status(client)
            input("\n>> Did the light dim? (press Enter to continue) ")

        # Step 4: Test full brightness (downlight=100)
        log("")
        log("=== STEP 4: Full brightness (downlight=100) ===")
        if confirm("Send light FULL (downlight=100)?"):
            await set_state(client, cur_speed, cur_dir, cur_uplight, 100)
            log("Polling status...")
            await get_status(client)
            input("\n>> Did the light go to full brightness? (press Enter to continue) ")

        # Step 5: Test light OFF (downlight=0)
        log("")
        log("=== STEP 5: Light OFF (downlight=0) ===")
        if confirm("Send light OFF (downlight=0)?"):
            await set_state(client, cur_speed, cur_dir, cur_uplight, 0)
            log("Polling status...")
            await get_status(client)
            input("\n>> Did the light turn off? (press Enter to continue) ")

        # Step 6: Bonus — test if 255 works (DC fan range) vs 100
        log("")
        log("=== STEP 6: Test max value (downlight=255 — DC fan range) ===")
        if confirm("Send downlight=255 to test if 0-255 range works?"):
            await set_state(client, cur_speed, cur_dir, cur_uplight, 255)
            log("Polling status...")
            await get_status(client)
            input("\n>> Any response from the light? (press Enter to continue) ")

            # Turn off after test
            if confirm("Turn light OFF?"):
                await set_state(client, cur_speed, cur_dir, cur_uplight, 0)
                await get_status(client)

        log("")
        log("=== DONE ===")
        log("Disconnecting.")

    log("Disconnected.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("\nInterrupted.")
    finally:
        if log_file:
            log_file.close()
