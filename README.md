# Hive Home Local

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)
[![Release](https://img.shields.io/github/v/release/gashwell/Hive-Home-Local)](https://github.com/gashwell/Hive-Home-Local/releases)

Unified local Home Assistant integration for the **complete Hive heating ecosystem**.  
No Hive cloud. No subscription. Full local control via Zigbee2MQTT and MQTT.

---

## Credits

This integration merges two projects:

### [HA-Hive-Local-Thermostat](https://github.com/andrew-codechimp/HA-Hive-Local-Thermostat) by [@andrew-codechimp](https://github.com/andrew-codechimp)

Provides all hub device support — SLR1, SLR2, and OTR1 receivers. The coordinator, entity files, and all MQTT protocol logic for heating and hot water control are his work. See the [NOTICE](NOTICE) file for full attribution.

### [Hive-TRV-Local](https://github.com/gashwell/Hive-TRV-Local) by [@gashwell](https://github.com/gashwell)

Provides TRV radiator valve support — UK7004240 / TRV001 — including auto-discovery, mode scheduling, room groups, holiday mode, geofencing, and boiler demand management.

---

## Supported devices

| Device | Model | Family | Features |
|---|---|---|---|
| Radiator Valve | UK7004240 / TRV001 | TRV | Setpoint, modes, schedules, room groups, boost, holiday, geofencing |
| Single Channel Receiver | SLR1 | Hub | Heating control, boost |
| Dual Channel Receiver | SLR2 | Hub | Heating + hot water, boost |
| Thermostat Receiver | OTR1 | Hub | Heating control |

---

## Requirements

- Home Assistant 2024.1 or newer
- Zigbee2MQTT with your devices already paired
- MQTT broker (Mosquitto add-on or external)
- The HA **MQTT** integration configured

---

## Installation

### Via HACS (recommended)

1. HACS → Integrations → ⋮ → **Custom repositories**
2. Add `https://github.com/gashwell/Hive-Home-Local` — type **Integration**
3. Install **Hive Home Local** and restart Home Assistant

### Manual

Copy `custom_components/hive_home_local/` into your HA `config/custom_components/` directory and restart.

---

## Setup

**Settings → Integrations → Add Integration → Hive Home Local**

A menu asks which device type to add. You can add both — one config entry per device family, running side by side.

### Hub (SLR1 / SLR2 / OTR1)

Select your hub model. The MQTT topic and other settings are configured via Configure after install.

### TRVs (UK7004240 / TRV001)

Enter your Zigbee2MQTT base topic (default: `zigbee2mqtt`). TRVs appear automatically within 30 seconds as Z2M publishes device data.

---

## Configuration (after install)

**Settings → Integrations → Hive Home Local → Configure**

### Hub configuration

| Option | Description |
|---|---|
| MQTT Topic | Zigbee2MQTT topic for your hub device, e.g. `zigbee2mqtt/Hive Hub` |
| Model | SLR1 / SLR2 / OTR1 |
| Show Schedule mode for heating | Exposes Schedule as a preset on the heating climate entity |
| Show Schedule mode for hot water | Exposes Schedule as a preset on the hot water climate entity (SLR2 only) |

### TRV configuration

A menu presents two sections:

**Device settings**

| Option | Description |
|---|---|
| Boiler / receiver entity | HA entity turned on/off based on aggregate TRV heat demand. Supports `climate`, `switch`, and `input_boolean`. |
| People to track for geofencing | When all selected people leave home, all TRVs drop to frost protection automatically. |
| Enable diagnostic logging | Writes `HIVE_DIAG` entries to the HA log at WARNING level. |

**Manage room groups**

Create virtual room groups that control multiple TRVs together as a single climate entity.

**Add a room group** — a 3-step wizard:

1. **Room name** — e.g. `Living Room`
2. **Devices** — pick from a dropdown of all discovered TRVs. Only devices not already in a group are shown. One device can only belong to one group.
3. **Extra temperature sensors** (optional) — additional HA temperature sensors to include in the room average

**Remove a room group** — select from a dropdown of existing rooms. Individual TRV entities are unaffected.

Changes take effect immediately — no restart required.

---

## Entities created

### Per hub device

| Platform | Entity | Notes |
|---|---|---|
| `climate` | Heating | Temperature, mode, boost preset |
| `climate` | Hot water | SLR2 only |
| `binary_sensor` | Heat boost active | |
| `binary_sensor` | Water boost active | SLR2 only |
| `sensor` | Boost remaining (heating) | |
| `sensor` | Boost remaining (water) | SLR2 only |
| `sensor` | Local temperature | |
| `number` | Heating boost duration | |
| `number` | Heating boost temperature | |
| `number` | Frost prevention temperature | |
| `number` | Water boost duration | SLR2 only |
| `select` | Hot water mode | Schedule / Manual / Off (SLR2 only) |
| `button` | Boost heating | |
| `button` | Boost water | SLR2 only |

### Per TRV

| Platform | Entity | Notes |
|---|---|---|
| `climate` | Main control | Temperature, mode, presets |
| `sensor` | Battery | % |
| `sensor` | Heating demand | PI demand 0–100% |
| `number` | Setpoint offset | ±2.5 °C calibration |
| `number` | Boost temperature | Default boost target |
| `number` | Boost duration | Default boost duration (minutes) |
| `select` | Keypad lock | unlock / lock1 / lock2 |
| `button` | Run adaptation | Valve calibration |
| `button` | Enter mounting mode | For valve re-installation |

Room groups create an additional `climate` entity per group.

---

## Services

### Hub services

| Service | Description |
|---|---|
| `hive_home_local.boost_heating` | Start a timed heating boost |
| `hive_home_local.cancel_boost_heating` | Cancel an active heating boost |
| `hive_home_local.boost_water` | Start a timed hot water boost (SLR2 only) |
| `hive_home_local.cancel_boost_water` | Cancel an active hot water boost |

### TRV / room group services

| Service | Description |
|---|---|
| `hive_home_local.boost_trv` | Start a timed boost on a TRV or room group |
| `hive_home_local.end_boost_trv` | Cancel an active boost |
| `hive_home_local.set_trv_schedule` | Set a weekly heating schedule |
| `hive_home_local.clear_trv_schedule` | Remove the schedule |
| `hive_home_local.advance_trv_schedule` | Skip to the next scheduled slot immediately |

### Whole-home services

| Service | Description |
|---|---|
| `hive_home_local.set_holiday` | Frost protection for a date range; all TRVs restore automatically |
| `hive_home_local.cancel_holiday` | Cancel an active or pending holiday |

### Room group services (alternative to UI)

| Service | Description |
|---|---|
| `hive_home_local.add_room` | Create a room group via service call |
| `hive_home_local.remove_room` | Remove a room group via service call |

---

## Updates via HACS

Update in HACS, then **restart Home Assistant**. Existing configuration is preserved — no need to remove and re-add the integration.

---

## Troubleshooting

**TRVs not appearing** — check Z2M is running and publishing to the correct base topic. TRVs appear within 30 seconds of Z2M publishing its device list.

**Hub not controlling heating** — go to Configure → Hub and confirm the MQTT topic matches exactly what Z2M shows for your hub device.

**Diagnostic logging** — Configure → Device settings → Enable diagnostic logging. Search for `HIVE_DIAG` in Settings → System → Logs → Load Full Log.

**Room group devices not available** — a device already in a group won't appear in the Add room wizard. Remove it from its current group first.

---

## License

MIT

---

*Hub device support based on [HA-Hive-Local-Thermostat](https://github.com/andrew-codechimp/HA-Hive-Local-Thermostat) © Andrew Codechimp. Brand logo from the [Home Assistant brands repository](https://github.com/home-assistant/brands).*
