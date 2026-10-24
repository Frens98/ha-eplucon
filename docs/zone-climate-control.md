# Eplucon zone climate control

This fork adds a Home Assistant climate entity for each supported th-TOUCH
regulation zone. The current and target temperatures continue to come from the
documented read-only API.

## Credentials

The API token alone cannot change a room target. The integration also needs the
username and password for the Eplucon portal. Enter both in the optional
**Room temperature control** section in the integration setup/options. If both
fields are left empty, the integration remains sensor-only.

In the options dialog, use **Remove saved portal credentials** to turn climate
controls off again. Leaving the password field blank during an ordinary options
save keeps the stored password.

The password is stored in the Home Assistant config entry on the Home Assistant
system and is used only to create the Eplucon portal session. It is not sent to
the public source repository. Use a dedicated Eplucon account if the portal
supports one.

## What a temperature change does

Home Assistant calls the portal's session-authenticated
`/e-control/set_constant_temp` route, with a CSRF token and the internal IDs
provided in each zone's `raw_data`. The target range exposed is 5–35 °C in 0.1 °C
steps. The portal route sets `active_schedule=0` and `mode=constantTemp`; it may
replace the room's programmed schedule with a constant target. Restore the room
schedule in the Eplucon portal/app when needed.

## Limitations

The write route is undocumented and was observed in the Eplucon portal UI. It is
not part of the public API contract, so Eplucon can change its login, CSRF
handling, form fields, or response without notice. Sensor readings remain
separate and continue to use the documented API token. This implementation has
not been validated against every Eplucon installation or portal account type.
