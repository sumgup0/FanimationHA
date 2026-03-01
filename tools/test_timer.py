"""
Timer Control Test — verifies timer functionality via BLE.

Strategy:
    1. Poll GET_STATUS to get current state
    2. Send SET_STATE with timer values
    3. Poll GET_STATUS to see if timer is reflected
    4. Wait and re-poll to see if timer counts down

Usage:
    python test_timer.py 50:8C:B1:4A:16:A0
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


def parse_timer(b6, b7):
    """Parse little-endian 16-bit timer value in minutes."""
    return b6 | (b7 << 8)


def notification_handler(sender, data: bytearray):
    global last_response
    last_response = list(data)
    log(f"NOTIFY: {format_bytes(data)}")
    b = last_response
    if len(b) >= 10:
        timer_min = parse_timer(b[6], b[7])
        timer_str = f"{timer_min}min" if timer_min > 0 else "off"
        log(f"  speed={b[2]} dir={b[3]} uplight={b[4]} downlight={b[5]} "
            f"timer={timer_str} ({b[6]:02X} {b[7]:02X}) fantype={b[8]} chk=0x{b[9]:02X}")


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
    log_filename = f"logs/test_timer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
        cur_downlight = status[5]
        log(f"Current: speed={cur_speed} dir={cur_dir} downlight={cur_downlight}")

        # Step 2: Turn fan on first (timer might need fan running)
        log("")
        log("=== STEP 2: Turn fan ON (speed=1) so timer has something to turn off ===")
        if confirm("Turn fan to speed 1?"):
            await set_state(client, speed=1, direction=cur_dir, uplight=0,
                            downlight=cur_downlight)
            await get_status(client)

        # Step 3: Test timer = 1 minute (smallest useful value)
        log("")
        log("=== STEP 3: Set timer to 1 minute ===")
        log("Timer bytes: [6]=0x01 (1 minute low), [7]=0x00 (high)")
        if confirm("Send timer=1 minute? (fan should turn off in ~1 min)"):
            await set_state(client, speed=1, direction=cur_dir, uplight=0,
                            downlight=cur_downlight, timer_lo=1, timer_hi=0)
            log("Polling status immediately...")
            await get_status(client)

            log("")
            log("Waiting 30 seconds, then polling to see if timer counts down...")
            await asyncio.sleep(30)
            log("--- GET_STATUS after 30s ---")
            await get_status(client)

            log("")
            log("Waiting another 40 seconds (past 1 minute)...")
            await asyncio.sleep(40)
            log("--- GET_STATUS after ~70s total ---")
            await get_status(client)
            input("\n>> Did the fan turn off? (press Enter to continue) ")

        # Step 4: Test timer = 60 minutes (1 hour)
        log("")
        log("=== STEP 4: Set timer to 60 minutes (1 hour) ===")
        log("Timer bytes: [6]=0x3C (60 low), [7]=0x00 (high)")
        log("We won't wait the full hour — just check if the value is accepted")
        if confirm("Send timer=60 minutes?"):
            await set_state(client, speed=1, direction=cur_dir, uplight=0,
                            downlight=cur_downlight, timer_lo=60, timer_hi=0)
            log("Polling status...")
            await get_status(client)
            input("\n>> Note the timer value in the response (press Enter to continue) ")

        # Step 5: Cancel timer (set to 0)
        log("")
        log("=== STEP 5: Cancel timer (set to 0) ===")
        if confirm("Send timer=0 to cancel?"):
            await set_state(client, speed=1, direction=cur_dir, uplight=0,
                            downlight=cur_downlight, timer_lo=0, timer_hi=0)
            log("Polling status...")
            await get_status(client)

        # Step 6: Turn fan off
        log("")
        log("=== STEP 6: Turn fan OFF ===")
        if confirm("Turn fan off?"):
            await set_state(client, speed=0, direction=cur_dir, uplight=0,
                            downlight=0)
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
