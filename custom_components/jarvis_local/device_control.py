"""Best-effort, individually verified lighting commands.

A Tuya rejection does not abort unrelated lights. Retry once only when
Home Assistant still reports the opposite state; reported state is not proof
of physical operation.
"""
import asyncio
from homeassistant.exceptions import HomeAssistantError
from .verify import verify, pending


async def apply_lighting(hass, domain, service, data, context):
    succeeded = []
    failed = []
    unverified = []
    for entity_id in data["entity_id"]:
        single = {**data, "entity_id": [entity_id]}
        errors = []
        for attempt in range(2):
            # Check state before retrying; commands may have succeeded before
            # a cloud timeout/rejection was reported.
            if attempt and not pending(hass, domain, service, single):
                break
            try:
                await hass.services.async_call(
                    domain, service, single, blocking=True, context=context
                )
                break
            except HomeAssistantError as exc:
                errors.append(str(exc))
                if attempt == 0:
                    await asyncio.sleep(0.15)
            except ValueError as exc:
                errors.append(str(exc))
                break
        if errors and pending(hass, domain, service, single):
            failed.append(entity_id)
            continue
        if await verify(hass, domain, service, single):
            unverified.append(entity_id)
        else:
            succeeded.append(entity_id)
    return succeeded, failed, unverified


def lighting_report(failed, unverified):
    parts = []
    if failed:
        parts.append(
            "I couldn't control " + ", ".join(failed)
            + ". The device or cloud rejected the request."
        )
    if unverified:
        parts.append(
            "Home Assistant hasn't confirmed " + ", ".join(unverified) + "."
        )
    return " ".join(parts)
