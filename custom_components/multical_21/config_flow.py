"""Adds config flow for multical 21."""

from __future__ import annotations

import serialx
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import persistent_notification
from homeassistant.const import CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_BAUDRATE,
    DEFAULT_BAUDRATE,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SUPPORTED_BAUDRATES,
)


def _test_serial_port(port: str, baudrate: int) -> None:
    """Test if the serial port can be opened (blocking, run in executor)."""
    ser = serialx.serial_for_url(port, baudrate=baudrate, read_timeout=DEFAULT_TIMEOUT)
    ser.open()
    ser.close()


def _port_and_name_schema(default_port: str | None, default_name: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_PORT, default=default_port): selector.SerialPortSelector(),
            vol.Optional(CONF_NAME, default=default_name): str,
        }
    )


class KamstrupFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for multical 21."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._errors: dict[str, str] = {}

    # -- Setup (Add Integration) --------------------------------------------

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            return await self._validate_and_create(
                port=user_input.get(CONF_PORT),
                name=user_input.get(CONF_NAME, DEFAULT_NAME),
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_port_and_name_schema(None, DEFAULT_NAME),
            errors=self._errors,
        )

    # -- Reconfigure (change device without deleting the entry) ------------

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        """Allow changing the serial port / name of an existing entry."""
        self._errors = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            return await self._validate_and_update(
                entry,
                port=user_input.get(CONF_PORT),
                name=user_input.get(CONF_NAME),
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_port_and_name_schema(
                entry.data.get(CONF_PORT), entry.data.get(CONF_NAME, DEFAULT_NAME)
            ),
            errors=self._errors,
        )

    # -- Shared validation ---------------------------------------------------

    async def _validate_and_create(self, port: str | None, name: str) -> FlowResult:
        if not port:
            self._errors["base"] = "port"
            return self.async_show_form(
                step_id="user",
                data_schema=_port_and_name_schema(None, name),
                errors=self._errors,
            )

        await self.async_set_unique_id(port)
        self._abort_if_unique_id_configured()

        try:
            await self.hass.async_add_executor_job(_test_serial_port, port, DEFAULT_BAUDRATE)
        except (OSError, TimeoutError, serialx.SerialException):
            self._errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="user",
                data_schema=_port_and_name_schema(port, name),
                errors=self._errors,
            )

        return self.async_create_entry(
            title=name or port,
            data={CONF_PORT: port, CONF_NAME: name},
        )

    async def _validate_and_update(
        self, entry: config_entries.ConfigEntry, port: str | None, name: str | None
    ) -> FlowResult:
        if not port:
            self._errors["base"] = "port"
            return await self.async_step_reconfigure()

        try:
            await self.hass.async_add_executor_job(_test_serial_port, port, DEFAULT_BAUDRATE)
        except (OSError, TimeoutError, serialx.SerialException):
            self._errors["base"] = "cannot_connect"
            return await self.async_step_reconfigure()

        return self.async_update_reload_and_abort(
            entry,
            title=name or entry.data.get(CONF_NAME) or port,
            data={
                **entry.data,
                CONF_PORT: port,
                CONF_NAME: name or entry.data.get(CONF_NAME),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return KamstrupOptionsFlowHandler()


class KamstrupOptionsFlowHandler(config_entries.OptionsFlow):
    """Kamstrup config flow options handler."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            scan_input = user_input.pop("scan_registers", "").strip()
            if scan_input:
                try:
                    registers = [
                        int(register.strip(), 0)
                        for register in scan_input.split(",")
                        if register.strip()
                    ]
                    if not 1 <= len(registers) <= 32 or any(
                        register < 0 or register > 65535 for register in registers
                    ):
                        raise ValueError
                except (TypeError, ValueError):
                    return self.async_show_form(
                        step_id="init",
                        data_schema=self._options_schema(scan_input),
                        errors={"base": "invalid_registers"},
                    )

                coordinator = self.hass.data.get(DOMAIN, {}).get(
                    self.config_entry.entry_id
                )
                if coordinator is None:
                    return self.async_abort(reason="scan_failed")

                try:
                    results = await coordinator.async_scan_registers(registers)
                    output = (
                        "\n".join(
                            f"{register} (0x{register:04X}): {value} {unit or ''} "
                            f"[unit_code={unit_code}, response={response_hex or '-'}]"
                            for register, (value, unit, unit_code, response_hex) in sorted(
                                results.items()
                            )
                        )
                        if results
                        else "Keine lesbaren Register gefunden."
                    )
                    persistent_notification.async_create(
                        self.hass,
                        f"Gefundene Register:\n\n{output}",
                        title="Multical 21: Register-Scan abgeschlossen",
                        notification_id="multical_21_register_scan",
                    )
                except Exception:
                    return self.async_abort(reason="scan_failed")

            return self.async_create_entry(
                title=self.config_entry.data.get(
                    CONF_NAME, self.config_entry.data.get(CONF_PORT)
                ),
                data=user_input,
            )

        return self.async_show_form(step_id="init", data_schema=self._options_schema())

    def _options_schema(self, scan_default: str = "") -> vol.Schema:
        """Build the combined options and optional scan schema."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=86400)),
                vol.Required(
                    CONF_TIMEOUT,
                    default=self.config_entry.options.get(
                        CONF_TIMEOUT, DEFAULT_TIMEOUT
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=5.0)),
                vol.Required(
                    CONF_BAUDRATE,
                    default=self.config_entry.options.get(
                        CONF_BAUDRATE, DEFAULT_BAUDRATE
                    ),
                ): vol.In(SUPPORTED_BAUDRATES),
                vol.Optional("scan_registers", default=scan_default): str,
            }
        )
