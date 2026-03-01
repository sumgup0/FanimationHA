"""
Fanimation BTCR9 BLE Protocol Diagnostic Script

Connects to a CEILINGFAN BLE device and systematically probes
GATT characteristics to map the fan control protocol.

Usage:
    python probe_fan.py                          # Scan for CEILINGFAN devices
    python probe_fan.py 50:8C:B1:4A:16:A0       # Connect to specific MAC
"""

import asyncio
import sys
import os
from datetime import datetime

from bleak import BleakClient, BleakScanner

# ── Known UUIDs (from nRF Connect scan of BTCR9) ──────────────────────

# Fan Controller service
SVC_FAN_CONTROLLER = "0000e000-0000-1000-8000-00805f9b34fb"
CHAR_WRITE         = "0000e001-0000-1000-8000-00805f9b34fb"
CHAR_NOTIFY        = "0000e002-0000-1000-8000-00805f9b34fb"

# Unknown service (possibly BLE UART / serial bridge)
SVC_UNKNOWN        = "539c6813-0ad0-2137-4f79-bf1a11984790"
CHAR_UNKNOWN_1     = "539c6813-0ad0-2137-4f79-bf1a11984790"  # same as service UUID
CHAR_UNKNOWN_2     = "539c6813-0ad2-2137-4f79-bf1a11984790"

# ── Protocol constants (from toddhutch DC fan, unverified on BTCR9) ───

START_BYTE     = 0x53  # ASCII 'S'
CMD_GET_STATUS = 0x30
CMD_SET_STATE  = 0x31

# ── Globals ───────────────────────────────────────────────────────────

log_file = None
notification_log = []


def log(msg: str) -> None:
    """Print to console and write to log file."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{timestamp}] {msg}"
    print(line)
    if log_file:
        log_file.write(line + "\n")
        log_file.flush()


def build_command(
    cmd_type: int,
    speed: int = 0,
    direction: int = 0,
    uplight: int = 0,
    downlight: int = 0,
    timer_minutes: int = 0,
    fan_type: int = 0,
) -> bytes:
    """Build a 10-byte command packet with checksum."""
    packet = bytearray(10)
    packet[0] = START_BYTE
    packet[1] = cmd_type
    packet[2] = speed
    packet[3] = direction
    packet[4] = uplight
    packet[5] = downlight
    packet[6] = timer_minutes & 0xFF
    packet[7] = (timer_minutes >> 8) & 0xFF
    packet[8] = fan_type
    packet[9] = sum(packet[0:9]) & 0xFF
    return bytes(packet)


def format_bytes(data: bytes) -> str:
    """Format bytes as hex string like '53 30 00 00 00 00 00 00 00 83'."""
    return " ".join(f"{b:02X}" for b in data)


def confirm(prompt: str) -> bool:
    """Ask user for y/n confirmation."""
    while True:
        resp = input(f"\n{prompt} [y/n]: ").strip().lower()
        if resp in ("y", "yes"):
            return True
        if resp in ("n", "no"):
            return False
        print("  Please enter 'y' or 'n'.")


async def scan_for_fan(target_mac: str | None = None) -> str:
    """Scan for CEILINGFAN BLE devices. Returns MAC address."""
    log("Scanning for BLE devices (10 seconds)...")
    discovered = await BleakScanner.discover(timeout=10.0, return_adv=True)

    # discovered is dict[str, tuple[BLEDevice, AdvertisementData]]
    fans = []
    for addr, (d, adv) in discovered.items():
        name = d.name or adv.local_name or ""
        rssi = adv.rssi
        if target_mac and addr.upper() == target_mac.upper():
            log(f"  FOUND target: {name} ({addr}) RSSI={rssi}")
            return addr
        if "CEILINGFAN" in name.upper() or "FANSYNC" in name.upper() or "FAN" in name.upper():
            fans.append((d, adv))
            log(f"  FOUND fan candidate: {name} ({addr}) RSSI={rssi}")

    # Helper to list all devices sorted by RSSI
    def log_all_devices():
        for a, (dev, ad) in sorted(discovered.items(), key=lambda x: x[1][1].rssi or -999, reverse=True):
            n = dev.name or ad.local_name or "(unnamed)"
            log(f"    {n} ({a}) RSSI={ad.rssi}")

    if target_mac:
        log(f"  Target MAC {target_mac} not found.")
        log("  All discovered devices:")
        log_all_devices()
        sys.exit(1)

    if not fans:
        log("  No fan devices found. All discovered devices:")
        log_all_devices()
        sys.exit(1)

    if len(fans) == 1:
        d, adv = fans[0]
        log(f"  Using: {d.name or adv.local_name} ({d.address})")
        return d.address

    log("  Multiple fans found. Select one:")
    for i, (d, adv) in enumerate(fans):
        log(f"    [{i}] {d.name or adv.local_name} ({d.address}) RSSI={adv.rssi}")
    choice = int(input("  Enter number: "))
    return fans[choice][0].address


async def enumerate_gatt(client: BleakClient) -> None:
    """Print the full GATT service/characteristic/descriptor table."""
    log("")
    log("═══ GATT TABLE ═══════════════════════════════════════════")
    for service in client.services:
        log(f"SERVICE: {service.uuid}  ({service.description})")
        for char in service.characteristics:
            props = ", ".join(char.properties)
            log(f"  CHAR: {char.uuid} | {props}")
            for desc in char.descriptors:
                try:
                    val = await client.read_gatt_descriptor(desc.handle)
                    try:
                        val_str = val.decode("utf-8")
                    except (UnicodeDecodeError, AttributeError):
                        val_str = format_bytes(val)
                    log(f"    DESC {desc.uuid}: {val_str}")
                except Exception as e:
                    log(f"    DESC {desc.uuid}: <read error: {e}>")
    log("═════════════════════════════════════════════════════════")
    log("")


def make_notification_handler(char_uuid: str):
    """Create a notification handler that logs received data."""
    def handler(sender, data: bytearray):
        log(f"NOTIFY {char_uuid}: {format_bytes(data)}")
        notification_log.append({
            "time": datetime.now().isoformat(),
            "char": char_uuid,
            "data": data.hex(),
            "bytes": list(data),
        })
    return handler


async def subscribe_notifications(client: BleakClient) -> None:
    """Subscribe to all notification-capable characteristics."""
    notify_chars = [
        (CHAR_NOTIFY, "FanController 0xE002"),
        (CHAR_UNKNOWN_1, "Unknown Service Char 1"),
        (CHAR_UNKNOWN_2, "Unknown Service Char 2"),
    ]
    for uuid, label in notify_chars:
        try:
            await client.start_notify(uuid, make_notification_handler(uuid))
            log(f"SUBSCRIBED to notifications: {label} ({uuid})")
        except Exception as e:
            log(f"FAILED to subscribe {label}: {e}")

    # Wait a moment for any spontaneous notifications
    log("Waiting 3 seconds for spontaneous notifications...")
    await asyncio.sleep(3)
    if not notification_log:
        log("  No spontaneous notifications received.")


async def send_and_wait(
    client: BleakClient,
    char_uuid: str,
    data: bytes,
    label: str,
    wait_secs: float = 2.0,
) -> list:
    """Write data to a characteristic and wait for notification responses."""
    log(f"WRITE {char_uuid}: {format_bytes(data)}  ({label})")

    before_count = len(notification_log)
    await client.write_gatt_char(char_uuid, data)

    # Wait for notifications
    await asyncio.sleep(wait_secs)

    new_notifications = notification_log[before_count:]
    if not new_notifications:
        log(f"  No notification response after {wait_secs}s")
    return new_notifications


async def probe_status(client: BleakClient) -> None:
    """Send GET_STATUS command and display the response."""
    cmd = build_command(CMD_GET_STATUS)
    log("")
    log("─── GET_STATUS Probe ────────────────────────────────────")
    log(f"Command: {format_bytes(cmd)}")

    if not confirm("Send GET_STATUS command to 0xE001?"):
        log("Skipped.")
        return

    responses = await send_and_wait(client, CHAR_WRITE, cmd, "GET_STATUS")
    for r in responses:
        b = r["bytes"]
        log(f"  Parsed response:")
        log(f"    Byte[0] = 0x{b[0]:02X}  (start byte?)")
        log(f"    Byte[1] = 0x{b[1]:02X}  (command echo?)")
        log(f"    Byte[2] = {b[2]}        (speed)")
        log(f"    Byte[3] = {b[3]}        (direction: {'fwd' if b[3]==0 else 'rev'})")
        log(f"    Byte[4] = {b[4]}        (uplight?)")
        log(f"    Byte[5] = {b[5]}        (downlight?)")
        log(f"    Byte[6] = {b[6]}        (timer low?)")
        log(f"    Byte[7] = {b[7]}        (timer high?)")
        if len(b) > 8:
            log(f"    Byte[8] = {b[8]}        (fan type?)")
        if len(b) > 9:
            log(f"    Byte[9] = 0x{b[9]:02X}  (checksum?)")
        if len(b) > 10:
            log(f"    Extra bytes: {format_bytes(bytes(b[10:]))}")
    log("────────────────────────────────────────────────────────")


async def probe_fan_control(client: BleakClient) -> None:
    """Interactive probing of fan speed, direction, and lights."""
    log("")
    log("─── Fan Control Probing ─────────────────────────────────")
    log("This will send SET_STATE commands to test each parameter.")
    log("Your fan WILL respond to these commands.")
    log("")

    # Speed probing
    if confirm("Probe fan SPEED? (will cycle through speeds 0-6)"):
        for speed in range(7):
            cmd = build_command(CMD_SET_STATE, speed=speed, direction=0)
            label = f"SET speed={speed}, dir=forward"
            log(f"\nNext: {label}")
            log(f"  Bytes: {format_bytes(cmd)}")
            if confirm(f"  Send speed={speed}?"):
                await send_and_wait(client, CHAR_WRITE, cmd, label)
            else:
                log("  Skipped.")
        # Turn off after speed test
        cmd = build_command(CMD_SET_STATE, speed=0)
        if confirm("Turn fan OFF (speed=0)?"):
            await send_and_wait(client, CHAR_WRITE, cmd, "SET speed=0 (off)")

    # Direction probing
    if confirm("\nProbe fan DIRECTION? (will test forward and reverse at speed 1)"):
        for direction in [0, 1]:
            dir_name = "forward" if direction == 0 else "reverse"
            cmd = build_command(CMD_SET_STATE, speed=1, direction=direction)
            label = f"SET speed=1, dir={dir_name}"
            log(f"\nNext: {label}")
            log(f"  Bytes: {format_bytes(cmd)}")
            if confirm(f"  Send direction={dir_name}?"):
                await send_and_wait(client, CHAR_WRITE, cmd, label)
            else:
                log("  Skipped.")
        # Turn off
        cmd = build_command(CMD_SET_STATE, speed=0)
        if confirm("Turn fan OFF?"):
            await send_and_wait(client, CHAR_WRITE, cmd, "SET speed=0 (off)")

    # Downlight probing
    if confirm("\nProbe DOWNLIGHT? (byte[5], will try 0, 128, 255)"):
        for brightness in [255, 128, 0]:
            cmd = build_command(CMD_SET_STATE, downlight=brightness)
            label = f"SET downlight={brightness}"
            log(f"\nNext: {label}")
            log(f"  Bytes: {format_bytes(cmd)}")
            if confirm(f"  Send downlight={brightness}?"):
                await send_and_wait(client, CHAR_WRITE, cmd, label)
            else:
                log("  Skipped.")

    # Uplight probing
    if confirm("\nProbe UPLIGHT? (byte[4], will try 0, 128, 255)"):
        for brightness in [255, 128, 0]:
            cmd = build_command(CMD_SET_STATE, uplight=brightness)
            label = f"SET uplight={brightness}"
            log(f"\nNext: {label}")
            log(f"  Bytes: {format_bytes(cmd)}")
            if confirm(f"  Send uplight={brightness}?"):
                await send_and_wait(client, CHAR_WRITE, cmd, label)
            else:
                log("  Skipped.")

    log("────────────────────────────────────────────────────────")


async def probe_unknown_service(client: BleakClient) -> None:
    """Probe the unknown 539c6813... service characteristics."""
    log("")
    log("─── Unknown Service Probing (539c6813...) ─────────────")
    log("This service has two characteristics that support WRITE + NOTIFY.")
    log("We'll try sending various payloads to see if anything responds.")
    log("")

    chars = [
        (CHAR_UNKNOWN_1, "Char 1 (same UUID as service)"),
        (CHAR_UNKNOWN_2, "Char 2 (0ad2 variant)"),
    ]

    for char_uuid, label in chars:
        if not confirm(f"Probe {label}?"):
            log(f"  Skipped {label}.")
            continue

        # Try GET_STATUS command (same as fan controller)
        cmd = build_command(CMD_GET_STATUS)
        log(f"\n  Trying GET_STATUS command on {label}")
        log(f"    Bytes: {format_bytes(cmd)}")
        if confirm(f"    Send GET_STATUS to {label}?"):
            await send_and_wait(client, char_uuid, cmd, f"GET_STATUS → {label}")

        # Try single bytes
        for probe in [b"\x00", b"\x01", b"\x53", b"\x30"]:
            log(f"\n  Trying probe byte: {format_bytes(probe)}")
            if confirm(f"    Send {format_bytes(probe)} to {label}?"):
                try:
                    await send_and_wait(client, char_uuid, probe, f"Probe {format_bytes(probe)} → {label}")
                except Exception as e:
                    log(f"    Write error: {e}")

    log("────────────────────────────────────────────────────────")


async def main():
    global log_file

    # Set up log file
    os.makedirs("logs", exist_ok=True)
    log_filename = f"logs/probe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_file = open(log_filename, "w", encoding="utf-8")
    log(f"Log file: {log_filename}")

    # Parse CLI args
    target_mac = sys.argv[1] if len(sys.argv) > 1 else None
    if target_mac:
        log(f"Target MAC: {target_mac}")
    else:
        log("No MAC specified — will scan for CEILINGFAN devices")

    # Scan
    mac = await scan_for_fan(target_mac)
    log(f"Will connect to: {mac}")

    # Connect
    log(f"Connecting to {mac}...")
    async with BleakClient(mac, timeout=20.0) as client:
        if not client.is_connected:
            log("ERROR: Failed to connect")
            return
        log(f"CONNECTED to {mac}")

        # Enumerate GATT table
        await enumerate_gatt(client)

        # Subscribe to all notifications
        await subscribe_notifications(client)

        # Stage 1: GET_STATUS
        await probe_status(client)

        # Stage 2: Fan control probing (speed, direction, lights)
        await probe_fan_control(client)

        # Stage 3: Unknown service probing
        await probe_unknown_service(client)

        # Summary
        log("")
        log("═══ SESSION SUMMARY ══════════════════════════════════════")
        log(f"Total notifications received: {len(notification_log)}")
        for n in notification_log:
            log(f"  [{n['time']}] {n['char']}: {n['data']}")
        log("═════════════════════════════════════════════════════════")
        log("Done. Disconnecting.")
    log("Disconnected.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("Interrupted by user. Exiting.")
    finally:
        if log_file:
            log_file.close()
