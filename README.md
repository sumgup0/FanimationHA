# FanimationHA

[Home Assistant](https://www.home-assistant.io/) HACS custom component for **local Bluetooth control** of Fanimation ceiling fans using the BTCR9 FanSync Bluetooth receiver. No cloud, no app dependency. Includes the fully reverse-engineered BLE protocol and diagnostic tools.

## What Works

The BTCR9 BLE protocol has been fully reverse-engineered and verified against real hardware:

| Feature | Range | Status |
|---------|-------|--------|
| Fan speed | Off / Low / Medium / High | Verified |
| Fan direction | Forward / Reverse | Verified |
| Downlight brightness | 0-100% | Verified |
| Sleep timer | 0-360 minutes | Verified |

## Installation (Home Assistant)

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots menu → **Custom repositories**
3. Add `https://github.com/sumgup0/FanimationHA` as an **Integration**
4. Search for "Fanimation" in HACS and install it
5. Restart Home Assistant
6. The fan should be auto-discovered via Bluetooth. If not, go to **Settings → Devices & Services → Add Integration → Fanimation BLE Ceiling Fan** and enter the MAC address manually.

### Manual

1. Copy the `custom_components/fanimation/` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Add the integration via **Settings → Devices & Services**

### What You Get

Three entities per fan, grouped under one device:

| Entity | Type | Controls |
|--------|------|----------|
| Fan | `fan` | Speed (off/low/med/high), direction (forward/reverse) |
| Downlight | `light` | On/off, brightness (0-100%) |
| Sleep Timer | `number` | 0-360 minutes (turns off fan + light on expiry) |

Works with ESP32 Bluetooth proxies — no special configuration needed.

## Protocol Reference

See **[docs/BTCR9-BLE-Protocol-Reference.md](docs/BTCR9-BLE-Protocol-Reference.md)** for the complete protocol documentation, including:

- GATT service and characteristic UUIDs
- 10-byte packet format with checksum
- Command and response details
- Gotchas and edge cases
- A working Python quick-start example

## Diagnostic Tools

The `tools/` directory contains Python scripts used to probe and verify the protocol:

| Script | Purpose |
|--------|---------|
| `probe_fan.py` | Full GATT enumeration and interactive speed/direction/light probing |
| `sniff_light.py` | Remote button sniffer — shows which bytes change when you use the physical remote |
| `test_light.py` | Targeted downlight control verification |
| `test_timer.py` | Timer functionality testing |

### Running the tools

```bash
# Set up a Python virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r tools/requirements.txt

# Run a script (replace MAC with your fan's address)
python tools/probe_fan.py 50:8C:B1:4A:16:A0
```

Find your fan's MAC address using any BLE scanner app (nRF Connect, LightBlue) — look for a device named `CeilingFan`.

## Compatible Hardware

- **BLE receiver**: Fanimation BTCR9 FanSync Bluetooth Receiver
- **Physical remote**: Fanimation BTT9 (3 speeds, downlight, no reverse)
- **Smartphone app**: FanSync (Android / iOS)
- **Motor type**: AC (3-speed capacitor-switched)

Other Fanimation FanSync Bluetooth models likely share the same protocol but have not been tested.

## Project History

This project is forked from [toddhutch/SimpleFanController](https://github.com/toddhutch/SimpleFanController), which targeted DC Bluetooth fans using Java/TinyB. The original code is preserved in `legacy/`. This fork shifts to Python/bleak and targets the BTCR9 AC motor variant with a Home Assistant integration as the end goal.

## License

This project is licensed under the MIT License.
