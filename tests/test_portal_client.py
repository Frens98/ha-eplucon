"""Tests for the optional Eplucon portal setpoint client."""

import pytest

from custom_components.eplucon.eplucon_api.DTO.ZoneDTO import ZoneDTO
from custom_components.eplucon.eplucon_api.portal_client import (
    EpluconPortalClient,
    PortalRequestError,
)


class FakeResponse:
    def __init__(self, body="", status=200, url="https://portaal.eplucon.nl/"):
        self.body = body
        self.status = status
        self.url = url

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def text(self):
        return self.body

    async def read(self):
        return self.body.encode()


class FakeSession:
    def __init__(self, get_responses, post_responses):
        self.get_responses = list(get_responses)
        self.post_responses = list(post_responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.get_responses.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.post_responses.pop(0)


async def test_set_zone_temperature_logs_in_and_posts_deci_degrees():
    session = FakeSession(
        [
            FakeResponse('<meta name="csrf-token" content="login-csrf">'),
            FakeResponse('<meta name="csrf-token" content="session-csrf">'),
        ],
        [FakeResponse(), FakeResponse("1")],
    )
    client = EpluconPortalClient(session, "user@example.com", "secret")
    zone = ZoneDTO(
        id=3073,
        name="Woonkamer",
        control_zone_id=9010,
        parent_id=9010,
        mode_id=9012,
    )

    await client.async_set_zone_temperature("module-index", zone, 20.6)

    login_fields = session.calls[1][2]["data"]
    assert login_fields["username"] == "user@example.com"
    assert login_fields["password"] == "secret"

    set_url = session.calls[3][1]
    set_request = session.calls[3][2]
    assert "account_module_index=module-index" in set_url
    assert set_request["data"] == {
        "_token": "session-csrf",
        "active_schedule": "0",
        "mode": "constantTemp",
        "mode_id": "9012",
        "zone_id": "9010",
        "parent_id": "9010",
        "constant_temp": "206",
    }
    assert set_request["headers"]["X-CSRF-TOKEN"] == "session-csrf"


async def test_set_zone_temperature_rejects_missing_internal_ids():
    session = FakeSession([], [])
    client = EpluconPortalClient(session, "user@example.com", "secret")
    zone = ZoneDTO(id=3073, name="Woonkamer")

    with pytest.raises(PortalRequestError, match="missing the internal IDs"):
        await client.async_set_zone_temperature("module-index", zone, 20.0)

    assert session.calls == []
