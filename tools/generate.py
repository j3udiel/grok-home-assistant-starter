"""Offline compiler. Never connects to HA and never accepts authentication data."""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
P = "tesla_grok_"
BAD = ["unknown", "unavailable", "none", "", "None"]
CATEGORIES = ["servidores", "nas", "ups", "docker", "zabbix"]


class StrictLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError("Duplicate YAML key (check your local file)")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def load(path):
    return yaml.load(Path(path).read_text(), Loader=StrictLoader)


def keys(value, allowed, location):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError(f"Unexpected keys/type in {location}; do not store secrets here")


def entity(value, domains, optional=False):
    if optional and value is None:
        return
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]*\.[a-z0-9_]{1,90}", value):
        raise ValueError("Invalid entity ID (value intentionally omitted)")
    if value.split(".")[0] not in domains or value.split(".")[1].startswith(P):
        raise ValueError("Unexpected domain or recursive project entity")


def entity_list(value, domains):
    if not isinstance(value, list) or len(value) > 50 or len(set(value)) != len(value):
        raise ValueError("Entity list must be unique and contain at most 50 entries")
    for item in value:
        entity(item, domains)


def number(value, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError("Numeric setting outside the allowed range")


def validate(cfg):
    expected = load(ROOT / "config.example.yaml")
    keys(cfg, expected, "root")
    if set(cfg) != set(expected) or cfg["schema"] != 1:
        raise ValueError("Use the complete schema: 1 configuration")
    for group in ["presence", "lighting", "climate", "alarm"]:
        keys(cfg[group], expected[group], group)
        if set(cfg[group]) != set(expected[group]):
            raise ValueError(f"Missing settings in {group}")
    pr = cfg["presence"]
    entity_list(pr["people"], ["person"])
    entity_list(pr["witnesses"], ["binary_sensor"])
    number(pr["max_age_seconds"], 60, 3600)
    number(pr["quiet_seconds"], 60, 1800)
    light = cfg["lighting"]
    entity(light["arrival"], ["light"], True)
    entity(light["simulation"], ["light"], True)
    entity_list(light["leave"], ["light"])
    number(light["max_minutes"], 1, 30)
    for value in cfg["climate"].values():
        entity(value, ["script"], True)
    entity(cfg["alarm"]["entity"], ["alarm_control_panel"], True)
    entity_list(cfg["alarm"]["contacts"], ["binary_sensor"])
    if not isinstance(cfg["cameras"], dict) or len(cfg["cameras"]) > 8:
        raise ValueError("Configure at most eight fixed camera adapters")
    for key, value in cfg["cameras"].items():
        if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,24}", key):
            raise ValueError("Invalid camera keyword")
        entity(value, ["script"])
    for group in ["security", "homelab"]:
        checks = cfg[group]
        if not isinstance(checks, list) or len(checks) > 50:
            raise ValueError("Configure at most 50 checks per report")
        seen = set()
        for rule in checks:
            keys(rule, ["entity", "label", "kind", "ok", "warning", "critical", "category", "max_age_seconds"], group)
            if set(rule) != {"entity", "label", "kind", "ok", "warning", "critical", "category", "max_age_seconds"}:
                raise ValueError("Each check requires all eight documented fields")
            number(rule["max_age_seconds"], 60, 86400)
            entity(rule["entity"], ["sensor", "binary_sensor", "lock", "alarm_control_panel"])
            if rule["entity"] in seen:
                raise ValueError("Duplicate check entity")
            seen.add(rule["entity"])
            if not isinstance(rule["label"], str) or not 1 <= len(rule["label"]) <= 35 or any(x in rule["label"] for x in ["{", "}", "\n"]):
                raise ValueError("Use short, plain labels without templates")
            categories = CATEGORIES if group == "homelab" else ["puertas", "ventanas", "alarma", "humo", "agua", "otros"]
            if rule["category"] not in categories:
                raise ValueError("Unsupported coverage category")
            if rule["kind"] == "states":
                states = []
                for level in ["ok", "warning", "critical"]:
                    if not isinstance(rule[level], list) or any(not isinstance(s, str) or s in BAD for s in rule[level]):
                        raise ValueError("State lists must contain explicit quoted strings, never unknown/unavailable")
                    states += rule[level]
                if not rule["ok"] or len(states) != len(set(states)):
                    raise ValueError("State classifications must be disjoint and include a known OK value")
            elif rule["kind"] in ["above", "below"]:
                if rule["ok"] != []:
                    raise ValueError("Numeric rules use ok: []")
                for level in ["warning", "critical"]:
                    number(rule[level], -1000000, 1000000)
                if rule["warning"] == rule["critical"] or (rule["kind"] == "above") != (rule["warning"] < rule["critical"]):
                    raise ValueError("Thresholds are reversed or equal")
            else:
                raise ValueError("Unknown check kind")
    return cfg


def eid(domain, key):
    return f"{domain}.{P}{key}"


def action(name, target=None, **data):
    result = {"action": name}
    if target is not None:
        result["target"] = {"entity_id": target}
    if data:
        result["data"] = data
    return result


def expr(value):
    return "{{ " + value + " }}"


def condition(value):
    return {"condition": "template", "value_template": expr(value)}


def branch(value, then, otherwise=None):
    result = {"if": [condition(value)], "then": then}
    if otherwise is not None:
        result["else"] = otherwise
    return result


def report(message):
    return {"event": P + "operacion", "event_data": {"summary": message, "at": "{{ now().isoformat() }}"}}


def block(value, message):
    return branch(value, [report(message), {"stop": message}])


def script(title, description, sequence, mode="single"):
    return {"alias": title, "description": description, "mode": mode, "max_exceeded": "silent",
            "trace": {"stored_traces": 10}, "sequence": sequence}


def template(name, key, state, attributes=None):
    result = {"name": name, "unique_id": P + key, "default_entity_id": eid("sensor", key), "state": state}
    if attributes:
        result["attributes"] = attributes
    return result


def presence_template(cfg):
    return (ROOT / "templates/presence.jinja").read_text().replace("__CONFIG__", repr(cfg["presence"]))


def check_template(checks, categories):
    return (ROOT / "templates/report.jinja").read_text().replace("__CHECKS__", repr(checks)).replace("__CATEGORIES__", repr(categories))


def build(cfg):
    cfg = validate(copy.deepcopy(cfg))
    bools = {
        "habilitado": ("Proyecto habilitado", True),
        "presencia_revisada": ("He revisado toda la cobertura de presencia", False),
        "visitas": ("Hay visitas o presencia no cubierta", True),
        "permitir_luces": ("Autorizar acciones sobre luces", False),
        "permitir_clima": ("Autorizar adaptadores de climatizacion", False),
        "permitir_simulacion": ("Autorizar simulacion con lampara dedicada", False),
        "permitir_alarma": ("Autorizar armado, nunca desarmado", False),
        "permitir_camaras": ("Autorizar envio a destino fijo", False),
        "ausencia": ("Ausencia solicitada", False),
        "vacaciones": ("Vacaciones solicitadas", False),
    }
    pkg = {"input_boolean": {P+k: {"name": "Tesla Grok " + n, "initial": v} for k, (n, v) in bools.items()},
           "input_text": {P+"reserva_luz": {"name": "Tesla Grok reserva interna", "max": 255}},
           "timer": {P+"luz": {"duration": "00:10:00", "restore": True}, P+"camara": {"duration": "00:02:00", "restore": True}},
           "template": [], "script": {}, "automation": []}
    presence = presence_template(cfg)
    pkg["template"].append({"sensor": [template("Tesla Grok presencia", "presencia", presence)]})
    for key, categories in [("seguridad", ["puertas", "ventanas", "alarma", "humo", "agua"]), ("homelab", CATEGORIES)]:
        source = "security" if key == "seguridad" else "homelab"
        event = P + "informe_" + key
        attrs = {k: expr(f"trigger.event.data.get('{k}') if trigger.platform == 'event' else this.attributes.get('{k}')")
                 for k in ["summary", "level", "missing", "issues", "uncovered", "at"]}
        attrs["at"] = "{{ trigger.event.data.at if trigger.platform == 'event' else none if trigger.platform == 'homeassistant' else this.attributes.get('at') }}"
        state = """{% set d = trigger.event.data if trigger.platform == 'event' else this.attributes %}
{% set stamp = as_timestamp(d.get('at'), 0) %}
{% if trigger.platform == 'homeassistant' or not stamp %}SIN REVISION: ejecuta el informe.
{% elif as_timestamp(now()) - stamp > 300 %}CADUCADO: ejecuta una nueva revision.
{% else %}{{ (d.get('summary', 'Desconocido') ~ ' [' ~ d.get('at','')[11:19] ~ ']')[:255] }}{% endif %}"""
        pkg["template"].append({"triggers": [{"trigger": "event", "event_type": event}, {"trigger": "homeassistant", "event": "start"}, {"trigger": "time_pattern", "minutes": "/1"}],
                                "sensor": [template("Tesla Grok " + key, key, state, attrs)]})
        name = "revision_seguridad" if key == "seguridad" else "estado_homelab"
        pkg["script"][P+name] = script("Tesla Grok " + name.replace("_", " "),
            "Solo consulta. Ejecuta y lee sensor.tesla_grok_" + key + ". Sin datos nunca significa seguro.",
            [{"variables": {"result": check_template(cfg[source], categories)}},
             {"event": event, "event_data": {**{k: expr("result."+k) for k in ["summary", "level", "missing", "issues", "uncovered"]}, "at": "{{ now().isoformat() }}"}}])
    pkg["template"].append({"triggers": [{"trigger": "event", "event_type": P+"operacion"}, {"trigger": "homeassistant", "event": "start"}],
        "sensor": [template("Tesla Grok ultima operacion", "ultima_operacion",
             "{{ ('HISTORICO [' ~ trigger.event.data.at[11:19] ~ '] ' ~ trigger.event.data.summary)[:255] if trigger.platform == 'event' else 'Reiniciado: sin resultado confirmado de esta sesion' }}") ]})
    pkg["template"].append({"sensor": [template("Tesla Grok modos", "modos",
        "{{ 'Proyecto: ' ~ states('input_boolean.tesla_grok_habilitado') ~ '; vacaciones: ' ~ states('input_boolean.tesla_grok_vacaciones') ~ '; ausencia: ' ~ states('input_boolean.tesla_grok_ausencia') ~ '; luz temporal: ' ~ states('timer.tesla_grok_luz') }}")]})

    enabled = "is_state('input_boolean.tesla_grok_habilitado','on')"
    # Evaluate the whole policy now, not the possibly lagging summary sensor.
    empty = "presence_now == 'Vacia verificada'"
    on = lambda k: action("input_boolean.turn_on", eid("input_boolean", k))
    off = lambda k: action("input_boolean.turn_off", eid("input_boolean", k))
    guarded = [block("not ("+enabled+")", "Bloqueado: proyecto deshabilitado")]
    vac_off = [off("vacaciones"), off("ausencia"), report("Vacaciones desactivadas. No se restauran consignas ni se apagan luces ajenas.")]
    # Release only an expired/cancelled lease whose light has not changed since our write.
    release = [{"variables": {"lease": "{{ states('input_text.tesla_grok_reserva_luz')[6:] | from_json({}) if states('input_text.tesla_grok_reserva_luz').startswith('lease:') else {} }}"}},
        branch("lease is mapping and lease.get('entity') and (as_timestamp(now()) >= lease.get('until',0)|float(0) or not ("+enabled+") or not ("+empty+") or not is_state('input_boolean.tesla_grok_permitir_luces','on') or (lease.get('kind') == 'simular' and (not is_state('input_boolean.tesla_grok_vacaciones','on') or not is_state('input_boolean.tesla_grok_permitir_simulacion','on'))))",
            [branch("lease.get('entity') in allowed_lamps and is_state(lease.entity,'on') and as_timestamp(states[lease.entity].last_updated,0) == lease.get('stamp',-1)",
                    [action("light.turn_off", "{{ lease.entity }}")]),
             action("input_text.set_value", eid("input_text", "reserva_luz"), value=""), action("timer.cancel", eid("timer", "luz"))])]

    def climate(which):
        adapter = cfg["climate"][which+"_script"]
        if not adapter:
            return []
        return [{"variables": {"presence_climate": presence}},
                block("not ("+enabled+")", "Clima bloqueado: proyecto deshabilitado"),
                block("presence_climate != 'Vacia verificada'", "Clima bloqueado: presencia cambio"),
                branch("is_state('input_boolean.tesla_grok_permitir_clima','on')", [block("states('"+adapter+"') != 'off'", "Clima no disponible u ocupado; consulta trazas"), action(adapter)])]

    def lamp(entity_id, kind):
        if not entity_id:
            return [report("Sin luz configurada para esta funcion; no se ha encendido ninguna.")]
        return [{"variables": {"presence_lamp": presence}},
                block("not ("+enabled+")", "Luz bloqueada: proyecto deshabilitado"),
                block("presence_lamp != 'Vacia verificada'", "Luz bloqueada: presencia cambio"),
                block("not is_state('input_boolean.tesla_grok_permitir_luces','on')", "Luces desautorizadas; sin encendidos"),
                block("not is_state('sun.sun','below_horizon')", "Sin encendidos: no se ha confirmado que sea de noche"),
                block("not is_state('timer.tesla_grok_luz','idle') or states('input_text.tesla_grok_reserva_luz') not in ['', 'unknown']", "Preparacion anterior pendiente; revisa su temporizador"),
                block("not is_state('"+entity_id+"','off')", "Luz encendida o sin datos: no se modifica"),
                action("light.turn_on", entity_id),
                {"wait_template": expr("is_state('"+entity_id+"','on')"), "timeout": "00:00:05", "continue_on_timeout": False},
                action("input_text.set_value", eid("input_text", "reserva_luz"), value=expr("'lease:' ~ (dict(entity='"+entity_id+"',stamp=as_timestamp(states['"+entity_id+"'].last_updated),until=as_timestamp(now())+"+str(cfg["lighting"]["max_minutes"]*60)+",kind='"+kind+"') | to_json)")),
                action("timer.start", eid("timer", "luz"), duration=int(cfg["lighting"]["max_minutes"]*60)),
                report("Luz temporal activada. El apagado requiere conservar su propiedad; consulta timer.tesla_grok_luz.")]

    choice = [
        {"conditions": expr("operation == 'liberar'"), "sequence": release},
        {"conditions": expr("operation == 'vacaciones_off'"), "sequence": vac_off + release},
        {"conditions": expr("operation == 'llegada'"), "sequence": guarded + [block("not ("+empty+")", "Llegada limitada: casa ocupada o presencia desconocida; sin cambios fisicos"), block("is_state('input_boolean.tesla_grok_vacaciones','on')", "Desactiva vacaciones antes de preparar llegada")] + climate("arrival") + lamp(cfg["lighting"]["arrival"], "llegada")},
        {"conditions": expr("operation in ['salir','vacaciones_on']"), "sequence": guarded + [block("not ("+empty+")", "Bloqueado: vivienda ocupada o presencia desconocida"),
             branch("operation == 'vacaciones_on'", [on("vacaciones")]), on("ausencia"),
             branch("is_state('input_boolean.tesla_grok_permitir_luces','on')", [
                 {"repeat": {"for_each": cfg["lighting"]["leave"], "sequence": [
                     {"variables": {"presence_again": presence}},
                     block("not ("+enabled+") or not is_state('input_boolean.tesla_grok_permitir_luces','on')", "Interrumpido: autorizacion retirada"),
                     block("presence_again != 'Vacia verificada'", "Interrumpido: la presencia cambio durante la operacion"),
                     branch("is_state(repeat.item,'on')", [action("light.turn_off", "{{ repeat.item }}")])]}}] if cfg["lighting"]["leave"] else [report("Sin luces autorizadas configuradas")]),
             *climate("away"), action(eid("script", "revision_seguridad")),
             report("Modo solicitado registrado. Consulta seguridad para incidencias y trazas para acciones; permisos fisicos independientes.")]},
        {"conditions": expr("operation == 'simular'"), "sequence": guarded + [
             condition(empty+" and is_state('input_boolean.tesla_grok_vacaciones','on') and is_state('input_boolean.tesla_grok_permitir_simulacion','on') and 18 <= now().hour < 23"),
             *lamp(cfg["lighting"]["simulation"], "simular")]},
    ]
    alarm = cfg["alarm"]["entity"]
    contacts = cfg["alarm"]["contacts"]
    for mode in ["noche", "fuera"]:
        seq = guarded + [block("not is_state('input_boolean.tesla_grok_permitir_alarma','on')", "Armado desautorizado")]
        if alarm and contacts:
            if mode == "fuera":
                seq += [block("not ("+empty+")", "Armado fuera bloqueado por presencia")]
            seq += [block("not is_state('"+alarm+"','disarmed')", "Alarma sin estado desarmado conocido; no se modifica"),
                    {"variables": {"perimeter": "{% set ns=namespace(ok=true) %}{% for e in " + repr(contacts) + " %}{% if not is_state(e,'off') or not (0 <= as_timestamp(now()) - as_timestamp(states[e].last_reported,0) <= " + str(cfg['presence']['max_age_seconds']) + ") %}{% set ns.ok=false %}{% endif %}{% endfor %}{{ ns.ok }}"}},
                    block("not perimeter", "Armado bloqueado: contacto abierto o sin datos"),
                    action("alarm_control_panel.alarm_arm_" + ("night" if mode == "noche" else "away"), alarm),
                    report("Armado solicitado, NO confirmado. Consulta el estado real de la alarma; no se ha enviado codigo ni bypass.")]
        else:
            seq += [report("No configurado: falta alarma o lista de contactos verificada")]
        choice.append({"conditions": expr("operation == 'alarma_"+mode+"'"), "sequence": seq})
    motor = [{"variables": {"presence_now": presence, "allowed_lamps": [e for e in [cfg["lighting"]["arrival"],cfg["lighting"]["simulation"]] if e]}},
             report("En curso; resultado final aun no confirmado. Si no cambia, consulta trazas."),
             {"choose": choice, "default": [report("Operacion desconocida; sin cambios")]}]
    # A release tick must not overwrite the last user-facing operation result.
    motor[1] = branch("operation != 'liberar'", [motor[1]])
    pkg["script"][P+"motor"] = script("Tesla Grok motor interno", "NO EXPONER. Serializa las acciones fisicas y reevalua presencia.", motor, "queued")
    pkg["script"][P+"motor"]["max"] = 5
    public = {"preparar_llegada": "llegada", "salir_de_casa": "salir", "activar_vacaciones": "vacaciones_on", "desactivar_vacaciones": "vacaciones_off", "armar_alarma_noche": "alarma_noche", "armar_alarma_fuera": "alarma_fuera"}
    for name, operation in public.items():
        pkg["script"][P+name] = script("Tesla Grok " + name.replace("_", " "), "Ejecuta la politica local; consulta sensor.tesla_grok_ultima_operacion y sensor.tesla_grok_modos. No repitas si esta en curso.", [action(eid("script", "motor"), operation=operation)])
    camera_seq = guarded + [block("not is_state('input_boolean.tesla_grok_permitir_camaras','on')", "Envio de fotos desautorizado"),
        {"variables": {"catalog": cfg["cameras"], "selection": "{{ camara | default('') }}"}},
        block("selection is not string or selection not in catalog", "Camara no configurada o fuera de la lista"),
        block("not is_state('timer.tesla_grok_camara','idle')", "Espera al menos dos minutos entre peticiones"),
        block("states(catalog[selection]) != 'off'", "Adaptador de camara ocupado o indisponible"),
        action("timer.start", eid("timer", "camara")), report("Envio solicitado; pendiente de confirmacion del adaptador"),
        {"action": "{{ catalog[selection] }}", "response_variable": "delivery"},
        block("delivery is not mapping or not delivery.get('accepted',false)", "Envio no confirmado por el adaptador; revisa Telegram y trazas"),
        report("Telegram ha aceptado la foto segun el adaptador local. No se ha analizado la imagen ni confirmado su lectura.")]
    pkg["script"][P+"camaras_telegram"] = script("Tesla Grok enviar foto a Telegram", "Una foto actual al destino fijo configurado. Parametro camara: palabra exacta de la lista. Lee sensor.tesla_grok_ultima_operacion.", camera_seq)
    pkg["script"][P+"camaras_telegram"]["fields"] = {"camara": {"description": "Camara configurada localmente", "required": True, "selector": {"select": {"options": list(cfg["cameras"]) or ["no_configurada"]}}}}
    pkg["automation"].append({"id": P+"conciliar", "alias": "Tesla Grok conciliar reserva y presencia", "mode": "single", "triggers": [
        {"trigger": "time_pattern", "minutes": "/1"}, {"trigger": "homeassistant", "event": "start"},
        {"trigger": "event", "event_type": "timer.finished", "event_data": {"entity_id": eid("timer", "luz")}},
        {"trigger": "state", "entity_id": [eid("sensor","presencia"),eid("input_boolean","habilitado"),eid("input_boolean","vacaciones"),eid("input_boolean","permitir_luces"),eid("input_boolean","permitir_simulacion")]}],
        "actions": [action(eid("script", "motor"), operation="liberar"),
            branch("not is_state('sensor.tesla_grok_presencia','Vacia verificada')", [off("ausencia"),off("vacaciones")])]})
    if cfg["lighting"]["simulation"]:
        pkg["automation"].append({"id": P+"simulacion", "alias": "Tesla Grok simulacion limitada", "mode": "single", "triggers": [{"trigger": "time_pattern", "minutes": "0"}],
            "conditions": [condition("is_state('input_boolean.tesla_grok_vacaciones','on') and is_state('input_boolean.tesla_grok_permitir_simulacion','on')")],
            "actions": [{"delay": {"minutes": "{{ range(1,16) | random }}"}}, action(eid("script","motor"), operation="simular")]})
    return pkg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.example.yaml")
    parser.add_argument("--output", default="output/tesla_grok.yaml")
    parser.add_argument("--inventory", help="Optional local JSON array of real entity IDs; no tokens")
    args = parser.parse_args()
    try:
        cfg = validate(load(args.config))
        package = build(cfg)
        if args.inventory:
            inventory = json.loads(Path(args.inventory).read_text())
            if not isinstance(inventory, list) or any(not isinstance(e,str) for e in inventory):
                raise ValueError("Inventory must be a JSON list of entity IDs")
            refs = external_entities(cfg)
            if refs - set(inventory):
                raise ValueError(f"{len(refs-set(inventory))} configured entities absent from local inventory; no package written")
        output = Path(args.output)
        if output.exists():
            raise ValueError("Output already exists; back it up and choose a new filename")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x") as stream:
            stream.write("# Generated offline. Physical authorizations reset OFF at every HA start.\n")
            yaml.safe_dump(package, stream, sort_keys=False, allow_unicode=True, width=110)
        print("Package generated locally. Validate in Home Assistant before installation.")
    except (ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
        # YAML parser errors may include secret-containing source lines.
        parser.exit(2, "Invalid local configuration; check schema and syntax. No input values logged.\n")


def external_entities(cfg):
    found = set()
    def visit(value):
        if isinstance(value, dict):
            for key, v in value.items():
                if key in {"entity", "arrival", "simulation", "arrival_script", "away_script"} and v:
                    found.add(v)
                else:
                    visit(v)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, str) and re.fullmatch(r"(?:person|binary_sensor|sensor|script|light|alarm_control_panel|lock)\.[a-z0-9_]+", value):
            found.add(value)
    visit(cfg)
    return found


if __name__ == "__main__":
    main()
