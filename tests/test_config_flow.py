"""Config-flow tests with a temporary shared Modbus unit."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hisense_b544.config_flow import HisenseB544ConfigFlow
from custom_components.hisense_b544.const import (
    CONF_BAUDRATE,
    CONF_DEVICE,
    CONF_MODEL,
    CONF_NAME,
    CONF_UNIT_ID,
)


class TemporaryUnit:
    """Async context manager returned by HA's temporary-unit API."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def user_input(**changes):
    data = {
        CONF_DEVICE: "/dev/serial/by-id/b544",
        CONF_BAUDRATE: 19200,
        CONF_UNIT_ID: 1,
        CONF_NAME: "ADT52 P1",
        CONF_MODEL: "ADT52UX4RCL8",
    }
    data.update(changes)
    return data


def flow():
    result = HisenseB544ConfigFlow()
    result.hass = SimpleNamespace()
    result.async_set_unique_id = AsyncMock()
    result._abort_if_unique_id_configured = MagicMock()
    result.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    result.async_show_form = MagicMock(return_value={"type": "form"})
    return result


@pytest.mark.asyncio
async def test_form_is_shown_when_no_input_is_provided():
    current = flow()
    assert await current.async_step_user() == {"type": "form"}
    assert current.async_show_form.call_args.kwargs["step_id"] == "user"


@pytest.mark.asyncio
async def test_valid_flow_probes_two_blocks_then_creates_entry():
    current = flow()
    temporary = TemporaryUnit()
    with (
        patch(
            "custom_components.hisense_b544.config_flow.async_get_temporary_unit",
            return_value=temporary,
        ) as get_temporary,
        patch(
            "custom_components.hisense_b544.config_flow.B544Device.async_read_state",
            new=AsyncMock(),
        ) as read_state,
    ):
        assert await current.async_step_user(user_input()) == {"type": "create_entry"}

    current.async_set_unique_id.assert_awaited_once_with("serial:/dev/serial/by-id/b544:1")
    current._abort_if_unique_id_configured.assert_called_once()
    get_temporary.assert_called_once()
    read_state.assert_awaited_once()
    current.async_create_entry.assert_called_once_with(title="ADT52 P1", data=user_input())


@pytest.mark.asyncio
async def test_invalid_unit_id_is_rejected_without_probing():
    current = flow()
    assert await current.async_step_user(user_input(unit_id=0)) == {"type": "form"}
    assert current.async_show_form.call_args.kwargs["errors"] == {CONF_UNIT_ID: "invalid_unit_id"}
    current.async_set_unique_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_probe_failure_returns_cannot_connect():
    current = flow()
    with patch(
        "custom_components.hisense_b544.config_flow.async_get_temporary_unit",
        side_effect=ValueError("offline"),
    ):
        assert await current.async_step_user(user_input()) == {"type": "form"}
    assert current.async_show_form.call_args.kwargs["errors"] == {"base": "cannot_connect"}
