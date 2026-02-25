# Fanimation BTCR9 FanSync Bluetooth — BLE Protocol Reference

*Reverse-engineered from [toddhutch/SimpleFanController](https://github.com/toddhutch/SimpleFanController) (Java/TinyB on Raspberry Pi 3B+)*

---

## 1. GATT Service & Characteristic UUIDs

### Service UUID

Not explicitly specified in the source code. The code iterates through ALL discovered GATT services to locate characteristics by UUID. The parent service UUID is never checked or filtered. Discover it during your first `bleak` connection (likely a custom service with short UUID in the `0xE0xx` range).

### Characteristic UUIDs

| UUID (Full 128-bit) | Short UUID | Role | Operations |
|---|---|---|---|
| `0000e001-0000-1000-8000-00805f9b34fb` | `0xE001` | **WRITE** | Write (with response) |
| `0000e002-0000-1000-8000-00805f9b34fb` | `0xE002` | **READ** | Read |

Both UUIDs use the Bluetooth Base UUID template (`0000xxxx-0000-1000-8000-00805f9b34fb`), meaning the 16-bit short forms `0xE001` and `0xE002` are the actual identifiers. These fall in the vendor/custom range — not standard Bluetooth SIG-assigned UUIDs. Standard services like Generic Access (`0x1800`) and Generic Attribute (`0x1801`) will also appear during service discovery but are not used by this protocol.

---

## 2. Command Packet Structure (10 bytes)

Every command written to `0xE001` is exactly **10 bytes**:

```
Index:  [0]    [1]    [2]      [3]        [4]      [5]        [6]      [7]      [8]      [9]
Field:  START  CMD    SPEED    DIRECTION  UPLIGHT  DOWNLIGHT  MIN_LO   MIN_HI   FANTYPE  CHECKSUM
```

| Byte | Field | Values | Notes |
|------|-------|--------|-------|
| `[0]` | Start byte | Always `0x53` | ASCII `'S'` — protocol start marker |
| `[1]` | Command type | `0x30` = GET_STATUS, `0x31` = SET_STATE | Only two commands observed |
| `[2]` | Fan speed | `0x00` = off, `0x01`–`0x0A`+ = speed levels | README example uses speed `10` (0x0A) |
| `[3]` | Fan direction | `0x00` = Forward, `0x01` = Reverse | Binary toggle |
| `[4]` | Uplight intensity | `0x00` (unused in source) | Likely 0–255 brightness for uplight |
| `[5]` | Downlight intensity | `0x00` (unused in source) | Likely 0–255 brightness for downlight |
| `[6]` | Minutes remaining (low) | `0x00` (unused in source) | Timer feature, little-endian low byte |
| `[7]` | Minutes remaining (high) | `0x00` (unused in source) | Timer feature, little-endian high byte |
| `[8]` | Fan type | `0x00` (unused in source) | Possibly selects motor type/model |
| `[9]` | Checksum | Sum of `[0]`–`[8]` & `0xFF` | Simple additive checksum, low byte only |

### Checksum Algorithm

```python
def compute_checksum(command: bytes) -> int:
    return sum(command[0:9]) & 0xFF
```

Sum all bytes except the last (indices 0 through 8), then truncate to the lower 8 bits.

---

## 3. Concrete Command Byte Sequences

### GET_FAN_STATUS — Query current state

```
Hex: 53 30 00 00 00 00 00 00 00 83
      S  CMD ── all zeros ──── CHK
```

Write to `0xE001`, then read from `0xE002` to get the response.

### SET_FAN_STATE — Set speed and direction

**Fan ON at speed 1, forward:**
```
53 31 01 00 00 00 00 00 00 85
```

**Fan ON at speed 6, forward:**
```
53 31 06 00 00 00 00 00 00 8A
```

**Fan ON at speed 10, forward:**
```
53 31 0A 00 00 00 00 00 00 8E
```

**Fan OFF (preserving forward direction):**
```
53 31 00 00 00 00 00 00 00 84
```

**Fan OFF (preserving reverse direction):**
```
53 31 00 01 00 00 00 00 00 85
```

**Speed 5, reverse direction:**
```
53 31 05 01 00 00 00 00 00 8A
```

### Quick-Reference Command Table

| Action | Byte[1] | Byte[2] | Byte[3] | Full Packet |
|--------|---------|---------|---------|-------------|
| Query status | `0x30` | `0x00` | `0x00` | `53 30 00 00 00 00 00 00 00 83` |
| Fan off (fwd) | `0x31` | `0x00` | `0x00` | `53 31 00 00 00 00 00 00 00 84` |
| Speed 1 fwd | `0x31` | `0x01` | `0x00` | `53 31 01 00 00 00 00 00 00 85` |
| Speed 2 fwd | `0x31` | `0x02` | `0x00` | `53 31 02 00 00 00 00 00 00 86` |
| Speed 3 fwd | `0x31` | `0x03` | `0x00` | `53 31 03 00 00 00 00 00 00 87` |
| Speed 4 fwd | `0x31` | `0x04` | `0x00` | `53 31 04 00 00 00 00 00 00 88` |
| Speed 5 fwd | `0x31` | `0x05` | `0x00` | `53 31 05 00 00 00 00 00 00 89` |
| Speed 6 fwd | `0x31` | `0x06` | `0x00` | `53 31 06 00 00 00 00 00 00 8A` |
| Speed 1 rev | `0x31` | `0x01` | `0x01` | `53 31 01 01 00 00 00 00 00 86` |
| Speed 6 rev | `0x31` | `0x06` | `0x01` | `53 31 06 01 00 00 00 00 00 8B` |

---

## 4. Response Packet Structure (Read from `0xE002`)

After writing a `0x30` (GET_STATUS) command to `0xE001`, read from `0xE002`:

| Byte | Field | Interpretation |
|------|-------|----------------|
| `[0]` | Unknown | Not parsed (likely start byte echo `0x53`) |
| `[1]` | Unknown | Not parsed (likely command type echo `0x30`) |
| `[2]` | **Fan speed** | `0` = off, `>0` = current speed level |
| `[3]` | **Fan direction** | `0` = Forward, `1` = Reverse |
| `[4]`–`[9]` | Unknown | Not parsed (likely echo remaining fields or zeros) |

The response format mirrors the command format — the same byte indices carry the same meaning. The original author's comments say "Assuming speed is at index 2" and "Assuming direction is at index 3", indicating this was reverse-engineered empirically. When connecting with `bleak`, dump the full response bytes to map the remaining fields — bytes `[4]` and `[5]` may report light state if your fan has a light kit.

---

## 5. Authentication / Pairing

**None.** The protocol is completely unauthenticated:

- No PIN code
- No passkey exchange
- No bonding
- No initial handshake
- No security level negotiation

The code connects directly and immediately accesses GATT characteristics. The `sudo` requirement in the source is for Linux BlueZ permissions, not BLE-level security.

---

## 6. Notification Handling

**Not used.** The codebase uses only synchronous GATT Read (`readValue()`) after writing a status query. There are no notification or indication subscriptions anywhere. The protocol is strictly request/response:

**Write status command → Read response.**

It is unknown whether `0xE002` supports notifications/indications — this needs probing.

---

## 7. Connection Flow

```
1. BLE Scan
   ├── Check BlueZ device cache first (manager.getDevices())
   ├── If empty: startDiscovery(), poll every 500ms
   └── Match by MAC address string (no name/UUID filtering)

2. Pre-connect Cleanup
   └── If device.getConnected() == true → device.disconnect()

3. Connect (with retry)
   ├── device.connect()
   ├── On failure: retry up to 10 times
   └── 200ms delay between retries

4. Service Discovery (automatic after connect in TinyB/bleak)
   └── device.getServices() returns all GATT services

5. Characteristic Lookup
   ├── Iterate ALL services → ALL characteristics
   ├── Match UUID "0000e001-..." → writeCharacteristic
   └── Match UUID "0000e002-..." → readCharacteristic

6. Ready to Send Commands
   ├── Write 10-byte packets to writeCharacteristic (0xE001)
   └── Read responses from readCharacteristic (0xE002)

7. Disconnect
   └── device.disconnect() when done
```

The source code disconnects and reconnects for each CLI invocation. For a Home Assistant integration, maintain a persistent connection or implement efficient connect/disconnect cycles.

---

## 8. Device Identification

### MAC Address

- Example from source: `78:04:73:19:77:BC`
- OUI prefix: `78:04:73` (can be looked up for the BLE chip manufacturer)
- Passed as a CLI argument — no hardcoded filtering in scan logic

### Scan Filtering

The source code applies **no scan filters**:

- No device name pattern matching (e.g., "FanSync", "BTCR9")
- No advertised service UUID filtering
- No manufacturer-specific data parsing
- Identification is 100% by MAC address

For a Home Assistant integration, add proper discovery: scan for the advertised service containing `0xE001`/`0xE002`, check the device name (use `bluetoothctl` or nRF Connect to see what the fan advertises), and use the OUI prefix `78:04:73` as a secondary filter.

---

## 9. Known Bug in Source Code

`setFanSpeed()` in `SimpleFanController.java:144` **resets direction to forward**:

```java
byte[] command = createCommand((byte) 0x31, (byte) speed, (byte) 0);
//                                                         ^^^^^^^^
//                                          direction hardcoded to 0 (forward)
```

Unlike `setFanDirection()` and `setFanPower()` which query current status first to preserve the other setting, `setFanSpeed()` always sends `direction=0`. In your implementation, always query status first and include the current direction when setting speed.

---

## 10. Python/bleak Reference Implementation

```python
import asyncio
from bleak import BleakClient, BleakScanner

WRITE_UUID = "0000e001-0000-1000-8000-00805f9b34fb"
READ_UUID  = "0000e002-0000-1000-8000-00805f9b34fb"

CMD_GET_STATUS = 0x30
CMD_SET_STATE  = 0x31
START_BYTE     = 0x53


def build_command(
    cmd_type: int,
    speed: int = 0,
    direction: int = 0,
    uplight: int = 0,
    downlight: int = 0,
    timer_minutes: int = 0,
    fan_type: int = 0,
) -> bytes:
    packet = bytearray(10)
    packet[0] = START_BYTE
    packet[1] = cmd_type
    packet[2] = speed
    packet[3] = direction
    packet[4] = uplight
    packet[5] = downlight
    packet[6] = timer_minutes & 0xFF         # low byte
    packet[7] = (timer_minutes >> 8) & 0xFF   # high byte
    packet[8] = fan_type
    packet[9] = sum(packet[0:9]) & 0xFF       # checksum
    return bytes(packet)


async def get_status(client: BleakClient) -> dict:
    cmd = build_command(CMD_GET_STATUS)
    await client.write_gatt_char(WRITE_UUID, cmd)
    resp = await client.read_gatt_char(READ_UUID)
    return {
        "speed": resp[2],
        "direction": "forward" if resp[3] == 0 else "reverse",
        "is_on": resp[2] > 0,
        "raw": resp.hex(" "),
    }


async def set_fan(
    client: BleakClient, speed: int, direction: int = 0
) -> None:
    cmd = build_command(CMD_SET_STATE, speed=speed, direction=direction)
    await client.write_gatt_char(WRITE_UUID, cmd)


async def main():
    MAC = "78:04:73:19:77:BC"  # Replace with your fan's MAC
    async with BleakClient(MAC) as client:
        status = await get_status(client)
        print(f"Current: {status}")

        # Set speed 3, preserve current direction
        cur_dir = 1 if status["direction"] == "reverse" else 0
        await set_fan(client, speed=3, direction=cur_dir)

asyncio.run(main())
```

---

## 11. What Is Known vs. What Needs Probing

| Area | Known | Needs Investigation |
|------|-------|---------------------|
| Write characteristic | `0xE001` | Confirm Write vs Write-Without-Response |
| Read characteristic | `0xE002` | Dump full response bytes; check if notifications are supported |
| Fan speed range | Works with 0–10 | Find the actual max (6? 10? 12?) |
| Direction | 0=fwd, 1=rev | Confirmed |
| Light control | Bytes `[4]`, `[5]` reserved | Experiment with values 0–255 |
| Timer | Bytes `[6]`, `[7]` reserved | Experiment with timer values |
| Fan type | Byte `[8]` reserved | May select AC vs DC motor profile |
| Service UUID | Not filtered in source | Discover with `bleak` and document |
| Device advertisement | Not analyzed in source | Scan for name, manufacturer data |
| Pairing | None observed | Confirm no encryption required |
| Full response format | Only bytes 2–3 parsed | Dump and document all 10 bytes |

---

## Source File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `SimpleFanController.java` | 238 | Main controller — on/off, speed, direction commands |
| `FanStatusChecker.java` | 171 | Status reader — query and interpret fan state |
| `fan_control.sh` | 22 | Shell wrapper with hardcoded MAC address |
| `README.md` | 61 | Installation and usage instructions |
