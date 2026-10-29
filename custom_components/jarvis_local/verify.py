"""Check Home Assistant reported state after a lighting command."""
import asyncio

def pending(hass, domain, action, data):
    missing=[]
    for entity in data['entity_id']:
        state=hass.states.get(entity)
        wanted='off' if action=='turn_off' else 'on'
        if state is None or state.state!=wanted:
            missing.append(entity);continue
        if 'brightness_pct' in data:
            value=state.attributes.get('brightness')
            if not isinstance(value,(int,float)) or abs(value/255*100-data['brightness_pct'])>4:
                missing.append(entity)
    return missing

async def verify(hass, domain, action, data):
    # Reported state may be optimistic; this is not physical verification.
    for delay in (0.05, 0.05, 0.1, 0.2, 0.2, 0.2, 0.2):
        remaining=pending(hass,domain,action,data)
        if not remaining:return []
        await asyncio.sleep(delay)
    return pending(hass,domain,action,data)
