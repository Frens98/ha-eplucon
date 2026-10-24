# Home Assistant Eplucon Integration — zone control fork

This custom integration allows you to integrate your Eplucon devices into Home Assistant, providing access to real-time data and sensor values.

## Features

- Monitor indoor temperature, vent RPM, brine circulation pump, and more in real-time.
- Expose per-zone control panels of a zone controller (th-TOUCH) as devices, with
  temperature, humidity, battery, signal and call-for-heat sensors.
- Optionally expose each zone as a climate entity so Home Assistant can change
  its target temperature.
- Automatically update sensor data using Home Assistant's update coordinator.

## Installation

### HACS (Home Assistant Community Store)

1. Ensure you have [HACS](https://hacs.xyz/) installed in your Home Assistant instance.
2. Add `https://github.com/Frens98/ha-eplucon` as a custom integration repository in HACS.
3. Install this fork and restart Home Assistant.

### Manual Installation

1. Download the ZIP of the fork's [default branch](https://github.com/Frens98/ha-eplucon/archive/refs/heads/main.zip).
2. Extract the `custom_components/eplucon` folder into your `config/custom_components/` directory.
3. Restart Home Assistant.

## Configuration

### Step 1: Obtain API Token

To use this integration, you will need an API token from Eplucon. Follow these steps to get your token:

1. Log in to your Eplucon account.
2. Navigate to My Account and then the [API section](https://portaal.eplucon.nl/account/api_tokens).
3. Generate or copy your existing API token.

### Step 2: Add Integration in Home Assistant

1. Go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for "Eplucon" and select it.
3. Enter your API token and complete the setup. For read-only sensors, that is all
   you need. To enable room temperature control, expand **Room temperature control**
   and enter the username and password used to sign in to the Eplucon portal.

### Step 3: Sensors and Entities

After successful setup, Home Assistant will automatically add the available sensors. You can find them under the **Devices & Services** section in Home Assistant.

## Available Sensors

This integration provides all available sensors that can be retrieved from the [Eplucon API](https://portaal.eplucon.nl/docs/api#/) and adds them to your Home Assistant. Some of the available sensors include:

- **Indoor Temperature** (°C)
- **Vent RPM** (RPM)
- **Brine Circulation Pump** (RPM)
- **Outdoor Temperature** (°C) - if available
- **Heating Status** - if applicable

These sensors are automatically created based on the real-time information available from your Eplucon device.

### Zone control panels (th-TOUCH)

If your installation includes a zone controller (`zones_system_controller`), each
regulation zone / room is added as its own device with these entities:

- **Temperature** (°C) and **Target Temperature** (°C)
- **Humidity** (%)
- **Battery** (%) and **Signal Strength** (%) — diagnostic
- **Mode** and **Regulation** (heating/cooling) — diagnostic
- **Call for Heat** — binary sensor (the zone relay state)

Entities are named after their zone, so a zone called *Woonkamer* yields
`sensor.woonkamer_temperature`, `sensor.woonkamer_humidity` and so on. A zone
that drops out of the API (flat control-panel battery, lost wireless link) is
reported as unavailable rather than as a zero or an `off`.

Temperature control is optional and uses the portal's own web session route,
which is undocumented. It needs the separate portal username and password in
addition to the API token. Setting a target uses Eplucon's `constantTemp` route
and may replace that room's scheduled mode with a constant setpoint; switch the
room back to its schedule in the Eplucon app/portal when desired. If the portal
changes its login or write route, sensor reading should keep working but climate
control may need an update. See [`docs/zones-api.md`](docs/zones-api.md) for the
API investigation and [`docs/zone-climate-control.md`](docs/zone-climate-control.md)
for this fork's implementation notes.

### Screenshot

![Eplucon sensors added to Home assistant](https://github.com/user-attachments/assets/9183f9fa-da81-465a-96a1-e6ff9aae3869)

## Troubleshooting

### Common Issues

- **Sensor values not updating:** Ensure that your API token is correct and the Eplucon server is accessible. Check the Home Assistant logs for any errors.
- **Missing sensors:** Verify that your device supports the sensors you're trying to add. Only sensors with real-time data will be added.

### Logs

If you encounter any issues, check the Home Assistant logs for errors related to the Eplucon integration. Logs can be found under **Settings** > **System** > **Logs**.

Make sure to enable debug logging for this integration which can be toggled under **Settings** > **Devices & Services** > **Eplucon**.

## Development

### Mock data

Under **Developer tools** in the integration's setup and options dialog there is
a **Use mock data** switch. With it on, every value comes from the JSON fixtures
in `custom_components/eplucon/eplucon_api/mock/` instead of the Eplucon API: no
request is sent, the API token is ignored, and the API endpoint is left alone
(pointing it at a fake host only produces a DNS error). The mock account holds
one heat pump and one zone controller with five zones, so every entity type can
be worked on without a real installation. A warning is logged on every start
while the switch is on, and the section stays expanded so it can't be left
enabled unnoticed.

Each endpoint reads one fixture:

| Endpoint | Fixture |
| --- | --- |
| `/econtrol/modules` | `get_devices.json` |
| `/econtrol/modules/{id}/get_realtime_info` | `get_realtime_info.json` |
| `/econtrol/modules/{id}/heatloading_status` | `get_heatloading_status.json` |
| `/econtrol/modules/{id}/zones` | `get_zones.json` |

Fixtures are re-read on every refresh, so editing one shows up in Home Assistant
within the next update interval — no restart needed. Two optional extras help
model a less tidy account:

- **Per-module fixtures:** `get_zones.1007331.json` is used for module `1007331`
  and takes precedence over `get_zones.json`.
- **Non-200 responses:** add `"http_status": 406` to a fixture to mock an error
  response, for example a module that is not a zone controller.

## Contributing

Contributions are welcome! If you'd like to contribute to this integration, please fork the repository and submit a pull request. Be sure to follow the existing coding style and add appropriate tests.

## Support

If you have any issues or feature requests, please open an issue on the [GitHub Issues page](https://github.com/Frens98/ha-eplucon/issues).

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
