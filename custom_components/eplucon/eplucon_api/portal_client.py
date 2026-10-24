"""Session-based client for Eplucon portal zone setpoints.

The public Eplucon API token can read zones, but the portal's setpoint route
requires its web session and CSRF token. This client mirrors that portal flow.
The route is undocumented and may change independently of the public API.
"""

from __future__ import annotations

import asyncio
import logging
from html.parser import HTMLParser
from urllib.parse import urlencode

import aiohttp

_LOGGER = logging.getLogger(__name__)
PORTAL_URL = "https://portaal.eplucon.nl"
LOGIN_URL = f"{PORTAL_URL}/login"
ZONES_URL = f"{PORTAL_URL}/e-control/zones"


class PortalAuthError(Exception):
    """Portal login or session authentication failed."""


class PortalRequestError(Exception):
    """Portal rejected or failed a setpoint request."""


class _LoginFormParser(HTMLParser):
    """Extract CSRF meta and hidden login form fields without extra deps."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.csrf_token: str | None = None
        self.hidden_inputs: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        if tag == "meta" and attributes.get("name", "").lower() == "csrf-token":
            self.csrf_token = attributes.get("content")
        elif tag == "input":
            name = attributes.get("name")
            input_type = attributes.get("type", "").lower()
            if name and input_type == "hidden":
                self.hidden_inputs[name] = attributes.get("value", "")
            elif name and name.startswith("my_name_"):
                # The portal uses blank name fields as anti-bot honeypots.
                self.hidden_inputs[name] = ""


class EpluconPortalClient:
    """Login to the portal and set a regulation zone's target temperature."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._csrf_token: str | None = None
        self._lock = asyncio.Lock()

    async def async_login(self) -> None:
        """Create a portal session and refresh its CSRF token."""
        async with self._session.get(LOGIN_URL) as response:
            if response.status != 200:
                raise PortalAuthError(
                    f"Eplucon portal login page returned HTTP {response.status}"
                )
            page = await response.text()

        parser = _LoginFormParser()
        parser.feed(page)
        token = parser.csrf_token or parser.hidden_inputs.get("_token")
        if not token:
            raise PortalAuthError("Eplucon login page did not contain a CSRF token")

        fields = dict(parser.hidden_inputs)
        fields.update(
            {
                "_token": token,
                "username": self._username,
                "password": self._password,
                "remember": "1",
            }
        )

        async with self._session.post(
            LOGIN_URL,
            data=fields,
            headers={"Referer": LOGIN_URL},
            allow_redirects=True,
        ) as response:
            await response.read()
            if response.status >= 400:
                raise PortalAuthError(
                    f"Eplucon portal login failed with HTTP {response.status}"
                )

        async with self._session.get(
            ZONES_URL,
            headers={"Referer": LOGIN_URL},
            allow_redirects=True,
        ) as response:
            if response.status != 200 or "/login" in str(response.url):
                raise PortalAuthError("Eplucon portal rejected the login credentials")
            zones_page = await response.text()

        parser = _LoginFormParser()
        parser.feed(zones_page)
        self._csrf_token = parser.csrf_token
        if not self._csrf_token:
            # Avoid including response HTML or credential-related data in logs.
            _LOGGER.debug("Authenticated Eplucon zones page did not expose CSRF meta")
            raise PortalAuthError("Eplucon portal session has no CSRF token")

    async def async_set_zone_temperature(
        self,
        account_module_index: str,
        zone,
        temperature: float,
    ) -> None:
        """Set a zone to a constant target temperature, in Celsius."""
        if not all((account_module_index, zone.control_zone_id, zone.parent_id, zone.mode_id)):
            raise PortalRequestError(
                "This zone is missing the internal IDs needed for temperature control"
            )

        deci_degrees = round(float(temperature) * 10)
        if not 50 <= deci_degrees <= 350:
            raise PortalRequestError("Target temperature must be between 5.0 and 35.0 °C")

        fields = {
            "_token": "",
            "active_schedule": "0",
            "mode": "constantTemp",
            "mode_id": str(zone.mode_id),
            "zone_id": str(zone.control_zone_id),
            "parent_id": str(zone.parent_id),
            "constant_temp": str(deci_degrees),
        }
        url = (
            f"{PORTAL_URL}/e-control/set_constant_temp?"
            f"{urlencode({'account_module_index': account_module_index})}"
        )

        async with self._lock:
            for attempt in range(2):
                if not self._csrf_token:
                    await self.async_login()

                fields["_token"] = self._csrf_token
                headers = {
                    "X-CSRF-TOKEN": self._csrf_token,
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": ZONES_URL,
                    "Origin": PORTAL_URL,
                }
                async with self._session.post(url, data=fields, headers=headers) as response:
                    body = (await response.text()).strip()
                    if (
                        response.status == 419 or "/login" in str(response.url)
                    ) and attempt == 0:
                        self._csrf_token = None
                        continue
                    if response.status != 200 or body != "1":
                        raise PortalRequestError(
                            "Eplucon did not accept the temperature change "
                            f"(HTTP {response.status})"
                        )
                    return

            raise PortalAuthError("Eplucon portal session expired; please retry")

    async def async_close(self) -> None:
        """Close the dedicated portal session."""
        await self._session.close()
