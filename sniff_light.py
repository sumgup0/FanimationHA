"""
Remote Sniffing Script — monitors fan state while you use the physical remote.

Usage:
    python sniff_light.py 50:8C:B1:4A:16:A0

Instructions:
    1. Run this script (it connects and listens)
    2. Use your physical remote — press any button
    3. Press Enter after each remote action to send GET_STATUS
    4. Watch which bytes change in the response
    5. Press Ctrl+C when done

Confirmed protocol (BTCR9):
    Byte[0] = 0x53 start byte
    Byte[1] = 0x32 status response
    Byte[2] = speed (0=off, 1=low, 2=med, 3=high)
    Byte[3] = direction (0=forward, 1=reverse)
    Byte[4] = ? (uplight on DC fans — unverified on BTCR9)
    Byte[5] = ? (downlight on DC fans — unverified on BTCR9)
    Byte[6] = ? (timer low on DC fans)
    Byte[7] = ? (timer high on DC fans)
    Byte[8] = ? (fan type on DC fans)
    Byte[9] = checksum (sum of bytes[0:9] & 0xFF)
"""

import asyncio
import sys
import os
from datetime import datetime

from bleak import BleakClient, BleakScanner

CHAR_WRITE  = "0000e001-0000-1000-8000-00805f9b34fb"
CHAR_NOTIFY = "0000e002-0000-1000-8000-00805f9b34fb"

START_BYTE     = 0x53
CMD_GET_STATUS = 0x30

SPEED_NAMES = {0: "off", 1: "low", 2: "med", 3: "high"}
DIR_NAMES   = {0: "fwd", 1: "rev"}

log_file = None
prev_status = None  # track previous response for diff highlighting


def log(msg: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{timestamp}] {msg}"
    print(line)
    if log_file:
        log_file.write(line + "\n")
        log_file.flush()


def format_bytes(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def parse_status(data: bytearray) -> None:
    """Parse and display a 10-byte status response, highlighting changes."""
    global prev_status
    b = list(data)
    if len(b) < 10:
        log(f"  (short response, only {len(b)} bytes)")
        return

    # Check which bytes changed from previous poll
    changed = set()
    if prev_status and len(prev_status) >= 10:
        for i in range(10):
            if b[i] != prev_status[i]:
                changed.add(i)

    labels = [
        "start",
        "cmd",
        f"speed ({SPEED_NAMES.get(b[2], '?')})",
        f"dir ({DIR_NAMES.get(b[3], '?')})",
        "byte4 (uplight?)",
        "byte5 (downlight?)",
        "byte6 (timer lo?)",
        "byte7 (timer hi?)",
        "byte8 (fan type?)",
        "checksum",
    ]

    log("  Parsed status response:")
    for i in range(10):
        marker = " <<<< CHANGED" if i in changed else ""
        if i == 9:
            log(f"    [{i}] 0x{b[i]:02X} ({labels[i]}){marker}")
        else:
            log(f"    [{i}] {b[i]:>3d}  0x{b[i]:02X}  ({labels[i]}){marker}")

    if changed:
        log(f"  ** Bytes that changed: {sorted(changed)} **")
    else:
        log("  (no changes from previous poll)")

    # Verify checksum
    expected_chk = sum(b[0:9]) & 0xFF
    if b[9] == expected_chk:
        log(f"  Checksum OK (0x{expected_chk:02X})")
    else:
        log(f"  Checksum MISMATCH: got 0x{b[9]:02X}, expected 0x{expected_chk:02X}")

    prev_status = b


def notification_handler(sender, data: bytearray):
    log(f"NOTIFY: {format_bytes(data)}")
    parse_status(data)


async def main():
    global log_file

    os.makedirs("logs", exist_ok=True)
    log_filename = f"logs/sniff_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_file = open(log_filename, "w", encoding="utf-8")

    mac = sys.argv[1] if len(sys.argv) > 1 else "50:8C:B1:4A:16:A0"
    log(f"Connecting to {mac}...")

    async with BleakClient(mac, timeout=20.0) as client:
        log(f"CONNECTED")

        await client.start_notify(CHAR_NOTIFY, notification_handler)
        log("Subscribed to notifications.")
        log("")
        log("=== REMOTE SNIFFING MODE ===")
        log("Press any button on your physical remote, then press ENTER here.")
        log("The script will poll GET_STATUS and show which bytes changed.")
        log("")
        log("Suggested test order (BTT9 remote):")
        log("  1. Baseline (just press Enter)")
        log("  2. Fan speed: low button")
        log("  3. Fan speed: med button")
        log("  4. Fan speed: high button")
        log("  5. Fan off button")
        log("  6. Light on")
        log("  7. Light dim (hold or press dim button)")
        log("  8. Light brighten")
        log("  9. Light off")
        log(" 10. Any other buttons on your remote")
        log("")
        log("Press Ctrl+C when done.")
        log("")

        # Build GET_STATUS command using proper checksum
        cmd = bytearray(10)
        cmd[0] = START_BYTE
        cmd[1] = CMD_GET_STATUS
        cmd[9] = sum(cmd[0:9]) & 0xFF
        cmd = bytes(cmd)

        log(f"--- Initial GET_STATUS (baseline) ---")
        await client.write_gatt_char(CHAR_WRITE, cmd)
        await asyncio.sleep(1)

        poll_count = 0
        while True:
            label = await asyncio.get_event_loop().run_in_executor(
                None, input,
                "\n>> What did you press? (type label + ENTER, or just ENTER): "
            )
            poll_count += 1
            label = label.strip() or f"poll #{poll_count}"
            log(f"--- GET_STATUS after: {label} ---")
            await client.write_gatt_char(CHAR_WRITE, cmd)
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("\nDone.")
    finally:
        if log_file:
            log_file.close()
