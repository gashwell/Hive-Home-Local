# Hive Home Local

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)

A unified local Home Assistant integration for the **complete Hive heating ecosystem** — all devices, no Hive cloud, no subscription.

---

## Credits

This integration would not exist without the work of two projects:

### [HA-Hive-Local-Thermostat](https://github.com/andrew-codechimp/HA-Hive-Local-Thermostat) by [@andrew-codechimp](https://github.com/andrew-codechimp)

Andrew's integration provides the hub device support (SLR1, SLR2, OTR1) that is incorporated here. His coordinator, entity, and platform files form the entire hub family of this integration. The MQTT protocol handling, boost logic, hot water control, and diagnostics for hub devices are entirely his work.

If you use a Hive hub (SLR/OTR), Andrew's standalone integration is also a great option and is independently maintained.

### [Hive-TRV-Local](https://github.com/gashwell/Hive-TRV-Local) by [@gashwell](https://github.com/gashwell)

The TRV radiator valve support (UK7004240 / TRV001) including auto-discovery, the mode state machine, weekly schedules, room groups, holiday mode, geofencing, and boiler demand management.

---

## Supported devices

| Device | Model | Family | Features |
|---|---|---|---|
| Hive Radiator Valve | UK7004240 / TRV001 | TRV | Setpoint, boost, weekly schedule, room groups, holiday, geofencing |
| Single Channel Receiver | SLR1 | Hub | Heating control, boost |
| Dual Channel Receiver | SLR2 | Hub | Heating + hot water control, boost |
| Thermostat Receiver | OTR1 | Hub | Heating control |

---

## Requirements

- Home Assistant 2024.1+
- Zigbee2MQTT (any version supporting your devices)
- MQTT broker (Mosquitto)
- Devices already paired to Zigbee2MQTT

---

## Installation

### Via HACS

1. HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/gashwell/Hive-Home-Local` as type **Integration**
3. Install **Hive Home Local** and restart HA

### Manual

Copy `custom_components/hive_home_local/` to your HA `config/custom_components/` directory and restart.

---

## Setup

Settings → Integrations → Add → **Hive Home Local**

You will be asked which device type to add. You can add **both** — one config entry per device family, running happily side by side.

### Hub (SLR1 / SLR2 / OTR1)

Enter the Zigbee2MQTT MQTT topic for your hub device (e.g. `zigbee2mqtt/Hive Hub`) and select the model. For SLR2, optionally enable the Schedule preset for heating and hot water independently.

### TRVs (UK7004240 / TRV001)

Enter your Zigbee2MQTT base topic (default: `zigbee2mqtt`). TRVs are discovered automatically — no need to list device names. Optionally configure a boiler entity and person entities for geofencing.

---

## TRV features

- **Auto-discovery** from Z2M `bridge/devices` with a 30-second sweep fallback
- **Mode state machine**: off / manual / schedule / boost / away / holiday
- **Weekly schedules** — HA manages the schedule, pushes setpoints to TRVs
- **Advance schedule** — skip to the next slot immediately
- **Timed boost** — override at a configurable temperature, restores automatically on expiry
- **Room groups** — aggregate multiple TRVs and external temperature sensors into one climate entity with averaged temperature
- **Holiday mode** — frost protection for a date range, restores all previous modes automatically on return
- **Geofencing** — all tracked persons away → frost protection activates automatically
- **Boiler demand management** — drives your boiler/receiver entity based on aggregate heat demand across all TRVs

## Hub features

- **Heating control** — set temperature, switch modes, boost
- **Hot water control** — SLR2: hot water boost and mode (schedule / manual / off)
- **Timed boost** — configurable duration and temperature for both heating and hot water
- **Diagnostics** — full MQTT payload exposed via HA diagnostics

---

## Services

### Hub services

| Service | Description |
|---|---|
| `hive_home_local.boost_heating` | Start a timed heating boost |
| `hive_home_local.cancel_boost_heating` | Cancel an active heating boost |
| `hive_home_local.boost_water` | Start a timed hot water boost (SLR2 only) |
| `hive_home_local.cancel_boost_water` | Cancel an active hot water boost |

### TRV services

| Service | Description |
|---|---|
| `hive_home_local.boost_trv` | Start a timed boost on a TRV or room group |
| `hive_home_local.end_boost_trv` | Cancel an active TRV boost |
| `hive_home_local.set_trv_schedule` | Set a weekly heating schedule |
| `hive_home_local.clear_trv_schedule` | Remove the schedule |
| `hive_home_local.advance_trv_schedule` | Skip to the next scheduled slot immediately |
| `hive_home_local.set_holiday` | Activate frost protection for a date range |
| `hive_home_local.cancel_holiday` | Cancel an active or pending holiday |
| `hive_home_local.add_room` | Create a room group |
| `hive_home_local.remove_room` | Remove a room group |

---

## Entities created

### Per hub device

| Platform | Entity |
|---|---|
| `climate` | Heating control (temperature, mode, boost preset) |
| `binary_sensor` | Heat boost active, Water boost active |
| `sensor` | Boost remaining (heating), Boost remaining (water), Local temperature, Running state |
| `number` | Heating boost duration, Heating boost temperature, Frost prevention temperature, Water boost duration |
| `select` | Hot water mode (SLR2) |
| `button` | Boost heating, Boost water |

### Per TRV

| Platform | Entity |
|---|---|
| `climate` | Main control (temperature, mode, presets) |
| `sensor` | Battery, Heating demand |
| `number` | Setpoint offset, Boost temperature, Boost duration |
| `select` | Keypad lock |
| `button` | Run adaptation, Enter mounting mode |

---

## License

MIT

---

*Brand logo from the [Home Assistant brands repository](https://github.com/home-assistant/brands). Hub device integration based on [HA-Hive-Local-Thermostat](https://github.com/andrew-codechimp/HA-Hive-Local-Thermostat) © Andrew Codechimp, used with thanks.*
