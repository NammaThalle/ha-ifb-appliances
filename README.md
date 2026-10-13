<p align="center">
  <img src="https://raw.githubusercontent.com/NammaThalle/ha-ifb-appliances/main/icon.png" alt="IFB Appliances Logo" width="160" height="160">
</p>

# IFB Appliances Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/default)
[![GitHub Release](https://img.shields.io/github/v/release/NammaThalle/ha-ifb-appliances?style=for-the-badge)](https://github.com/NammaThalle/ha-ifb-appliances/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

A Home Assistant custom integration and standalone Python library for **IFB Smart Home Appliances** (Washing Machines, Washer-Dryers, and compatible IoT models), reverse-engineered from the official *My IFB* mobile application (`com.sqt_smartapp.ifb_remote`).

Built for modern IFB machines equipped with the **Espressif ESP32** cloud module, communicating securely via Adobe Commerce GraphQL and IFB IoT cloud services (`mqttesp.ifbcloud.in:8887`).

---

## Features

- **Real-Time Telemetry & Sensors**:
  - Machine State (`standby`, `washing`, `rinsing`, `spinning`, `drying`, `steam`, `paused`, `complete`, `error`)
  - Active Program Name
  - Time Remaining (countdown in minutes)
  - Cycle Progress (0–100%)
  - Motor Speed (RPM)
  - Water Temperature (°C)
  - Configured Spin Speed & Drying Mode
- **Binary Sensors**:
  - Running State (`binary_sensor.running`)
  - Door Locked (`binary_sensor.door_locked`)
  - Child Lock (`binary_sensor.child_lock`)
  - Problem / Fault Detection (`binary_sensor.problem` with error codes)
  - Steam / Prewash / Soak active flags
- **Controls & Selectors**:
  - Program Selector (Mix/Daily, Cotton, Express 15, Cradle Wash, Wash+Dry, Dry Only, etc.)
  - Spin Speed Selector (No Spin up to 1400 RPM)
  - Temperature Selector (Cold up to 95°C)
  - Drying Mode Selector (Cupboard Dry, Iron Dry, Extra Dry, Timed Dry)
  - Hardware Buttons: **Start**, **Pause**, **Stop / Power Off**, and **Refresh**
- **Adaptive Polling Coordinator**:
  - Automatically increases polling rate to every 5 seconds while an active cycle is in progress.
  - Relaxes to 15 seconds during standby/idle to save network and cloud resources.
- **Robust Authentication**:
  - Supports modern SMS OTP login (standard My IFB mobile flow), password login, or direct Bearer Token entry.
- **Zero External Dependencies**:
  - Fully bundled Python client library—no external pip packages required on Home Assistant Core.

---

## Installation

### Method 1: HACS (Recommended)

1. Open **HACS** in your Home Assistant sidebar.
2. Click the three dots in the top right corner and select **Custom repositories**.
3. Add the following repository:
   - **Repository**: `https://github.com/NammaThalle/ha-ifb-appliances`
   - **Type**: `Integration`
4. Click **Add**, find **IFB Appliances** in the store, and click **Download**.
5. Restart Home Assistant.

### Method 2: Manual Installation

1. Download the latest release `.zip` from [Releases](https://github.com/NammaThalle/ha-ifb-appliances/releases).
2. Copy the `custom_components/ifb_washer_cloud` directory into your Home Assistant `<config>/custom_components/` folder.
3. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings** -> **Devices & Services**.
2. Click **Add Integration** and search for **IFB Appliances**.
3. Choose your preferred authentication method:
   - **Mobile Number (SMS OTP)** *(Recommended)*: Enter your 10-digit registered mobile number. You will receive an SMS OTP to verify.
   - **Password**: Enter your registered phone number or email and password.
   - **Direct Bearer Token**: Paste an existing active bearer token if you already have one.
4. If your appliance is not automatically returned by the IFB cloud catalog, the setup wizard will seamlessly prompt you to enter your machine's **MAC address** (printed on the barcode sticker on your appliance, or visible in your Wi-Fi router's client list).

---

## Dashboard Card: Animated Appliance Card

For an animated drum with cycle stages, pair this integration with [`ha-appliance-card`](https://github.com/ADNPolymerase/ha-appliance-card).

### Lovelace Dashboard YAML

```yaml
type: vertical-stack
cards:
  - type: custom:ha-appliance-card
    appliance_type: washer
    name: "IFB Washer Dryer"
    state_entity: sensor.ifb_washer_dryer_machine_state
    program_entity: sensor.ifb_washer_dryer_active_program
    remaining_time_entity: sensor.ifb_washer_dryer_time_remaining
    remaining_time_unit: minutes
    progress_entity: sensor.ifb_washer_dryer_progress
    door_entity: binary_sensor.ifb_washer_dryer_door_locked
    door_invert: true
    start_entity: button.ifb_washer_dryer_start
    pause_entity: button.ifb_washer_dryer_pause
    stop_entity: button.ifb_washer_dryer_stop

  - type: entities
    title: "Cycle Settings & Controls"
    show_header_toggle: false
    entities:
      - entity: select.ifb_washer_dryer_program
        name: "Program"
      - entity: select.ifb_washer_dryer_temperature
        name: "Temperature"
      - entity: select.ifb_washer_dryer_spin_speed
        name: "Spin Speed"
      - entity: select.ifb_washer_dryer_dry_mode
        name: "Dry Mode"
      - type: divider
      - entity: button.ifb_washer_dryer_start
        name: "Start Cycle"
      - entity: button.ifb_washer_dryer_pause
        name: "Pause Cycle"
      - entity: button.ifb_washer_dryer_stop
        name: "Stop / Power Off"
```

---

## Standalone Python Library

The bundled `ifb_cloud` library can also be used in standalone scripts:

```python
import asyncio
from ifb_cloud import IfbCloudClient

async def main():
    client = IfbCloudClient()
    
    # 1. Request SMS OTP
    await client.request_otp("98XXXXXXXX", calling_code="+91")
    otp = input("Enter OTP received on SMS: ")
    
    # 2. Verify OTP
    await client.verify_otp("98XXXXXXXX", otp, calling_code="+91")
    
    # 3. Discover appliances
    devices = await client.get_all_devices()
    for dev in devices:
        print(f"Found: {dev.name} ({dev.mac}) - Status: {'Online' if dev.is_online else 'Offline'}")
        
        # 4. Fetch live cycle progress
        progress = await client.get_device_progress(dev.mac)
        print(f"State: {progress.state}, Time Remaining: {progress.time_remaining_minutes} min")

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Troubleshooting & FAQ

<details>
<summary><b>1. "Invalid or expired OTP" error during login</b></summary>
The official IFB OTP expires in 5 minutes. Make sure you enter the code promptly. If you requested multiple OTPs, only the most recent code is valid.
</details>

<details>
<summary><b>2. Appliance does not appear after authentication</b></summary>
Some IFB models connect directly to the MQTT cloud bridge without being linked in the warranty registration store. If your machine is not auto-detected, the setup flow will ask for your appliance's MAC address. You can find this on the barcode label on your machine or inside your home router's DHCP client list.
</details>

<details>
<summary><b>3. Is my local machine IP or MAC address shared publicly?</b></summary>
No. The integration connects solely from your Home Assistant instance to the IFB cloud endpoints using your own account credentials. No network traffic or telemetry is shared with third parties.
</details>

---

## License

This project is licensed under the [MIT License](LICENSE).
