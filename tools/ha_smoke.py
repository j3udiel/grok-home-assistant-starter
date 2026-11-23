"""Run inside the official HA image with --network none. All device calls are fake.

No production configuration is read. This checks the real HA script/template engine.
"""
import asyncio
import json
import tempfile
from datetime import timedelta
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1]/"tests")]
from homeassistant.core import HomeAssistant, State
from homeassistant import bootstrap, loader
from homeassistant.util import dt as dt_util
import generate as g
from test_policy import configured


async def main():
    with tempfile.TemporaryDirectory() as directory:
        hass = HomeAssistant(directory)
        loader.async_setup(hass)
        hass.config.time_zone = "UTC"
        cfg = configured()
        pkg = g.build(cfg)
        # Automations are verified with check_config; run only explicit commands here.
        config={domain:pkg[domain] for domain in ["input_boolean", "input_text", "timer", "script", "template"]}
        config["homeassistant"]={"name":"Isolated test", "latitude":0, "longitude":0,
                                 "elevation":0, "unit_system":"metric", "time_zone":"UTC"}
        assert await bootstrap.async_from_config_dict(config,hass) is hass
        await hass.async_start()
        await hass.async_block_till_done()
        calls=[]
        async def light_service(call):
            calls.append(call.service)
            targets=call.data["entity_id"]
            for entity in targets if isinstance(targets,list) else [targets]:
                hass.states.async_set(entity,"on" if call.service=="turn_on" else "off")
        for service in ["turn_on","turn_off"]:
            hass.services.async_register("light", service, light_service)
        reports=[]
        hass.bus.async_listen("tesla_grok_informe_homelab",lambda event:reports.append(event.data))
        async def run(name, **data):
            await hass.services.async_call("script",g.P+name,data,blocking=True)
            await hass.async_block_till_done()
        try:
            await run("estado_homelab")
            assert reports[-1]["level"] == "Desconocido"
            assert isinstance(reports[-1]["missing"],list)
            for name in ["preparar_llegada","salir_de_casa","activar_vacaciones","desactivar_vacaciones","armar_alarma_noche","armar_alarma_fuera"]:
                await run(name)
            await run("camaras_telegram",camara="../invalid")
            assert not calls, "Default configuration reached a device action"
            for key in ["presencia_revisada","permitir_luces"]:
                await hass.services.async_call("input_boolean","turn_on",{"entity_id":g.eid("input_boolean",key)},blocking=True)
            await hass.services.async_call("input_boolean","turn_off",{"entity_id":g.eid("input_boolean","visitas")},blocking=True)
            for person in cfg["presence"]["people"]:
                source=person.replace("person.","device_tracker.")
                hass.states.async_set(source,"not_home")
                hass.states.async_set(person,"not_home",{"source":source})
            witness="binary_sensor.indoor_occupancy"
            # Direct insertion ONLY in this isolated test gives the witness an old last_changed.
            hass.states._states[witness] = State(witness,"off",last_changed=dt_util.utcnow()-timedelta(minutes=10))
            hass.states.async_set("light.entrance_demo","off")
            hass.states.async_set("sun.sun","below_horizon")
            await run("preparar_llegada")
            assert calls==["turn_on"],calls
            saved=hass.states.get(g.eid("input_text","reserva_luz")).state
            assert saved.startswith("lease:"),saved
            lease=json.loads(saved[6:]); lease["until"]=0
            await hass.services.async_call("input_text","set_value",{"entity_id":g.eid("input_text","reserva_luz"),"value":"lease:"+json.dumps(lease)},blocking=True)
            await run("motor",operation="liberar")
            assert calls==["turn_on","turn_off"],calls
            print("HA engine smoke test passed: typed reports, guarded defaults, simulated light lease and release.")
        finally:
            await hass.async_stop()


if __name__ == "__main__":
    asyncio.run(main())
