"""Offline behavioral tests: fake states and recorded actions, never physical IO."""
import copy
import datetime as dt
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from jinja2.nativetypes import NativeEnvironment

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import generate as g

NOW = dt.datetime(2030, 1, 1, 20, 0, tzinfo=dt.timezone.utc)


class States:
    def __init__(self):
        self.data = {}
    def put(self, entity, state, age=0, changed=600, **attrs):
        self.data[entity] = SimpleNamespace(state=str(state), attributes=attrs,
            last_reported=NOW-dt.timedelta(seconds=age),
            last_updated=NOW-dt.timedelta(seconds=age),
            last_changed=NOW-dt.timedelta(seconds=changed))
    def __call__(self, entity):
        return self.data[entity].state if entity in self.data else "unknown"
    def __getitem__(self, entity):
        return self.data.get(entity, SimpleNamespace(state="unknown", attributes={}, last_reported=None,last_updated=None,last_changed=None))


def timestamp(value, default=0):
    try:
        if isinstance(value, dt.datetime):
            return value.timestamp()
        if isinstance(value, str):
            return dt.datetime.fromisoformat(value).timestamp()
        return float(value)
    except (TypeError, ValueError):
        return default


def is_number(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def from_json(value, default=None):
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class Halt(Exception):
    pass


class Runner:
    def __init__(self, config):
        self.pkg = g.build(config)
        self.states = States()
        self.env = NativeEnvironment()
        self.env.globals.update(states=self.states, is_state=lambda e,v:self.states(e)==v,
            state_attr=lambda e,a:self.states[e].attributes.get(a), now=lambda:NOW,
            as_timestamp=timestamp, is_number=is_number)
        self.env.filters.update(from_json=from_json, to_json=json.dumps)
        self.actions, self.events = [], []
        self.adapter_response = {"accepted": True}
        self.after_action = None
        for key, value in self.pkg["input_boolean"].items():
            self.states.put("input_boolean."+key, "on" if value["initial"] else "off")
        for key in self.pkg["timer"]:
            self.states.put("timer."+key, "idle")
        self.states.put("input_text.tesla_grok_reserva_luz", "")
        self.states.put("sun.sun", "below_horizon")
    def render(self, value, variables=None):
        variables = variables or {}
        if isinstance(value, str) and ("{{" in value or "{%" in value):
            result = self.env.from_string(value).render(variables)
            return result.strip() if isinstance(result,str) else result
        if isinstance(value, dict):
            return {k:self.render(v,variables) for k,v in value.items()}
        if isinstance(value, list):
            return [self.render(v,variables) for v in value]
        return value
    def call(self, key, **variables):
        try:
            self.run(self.pkg["script"][g.P+key]["sequence"], variables)
        except Halt:
            pass
    def run(self, steps, variables):
        for step in steps:
            if "variables" in step:
                for k,v in step["variables"].items():
                    variables[k] = self.render(v, variables)
            elif "if" in step:
                truth = all(bool(self.render(c["value_template"],variables)) for c in step["if"])
                self.run(step["then"] if truth else step.get("else",[]), variables)
            elif "choose" in step:
                chosen = step.get("default", [])
                for c in step["choose"]:
                    if self.render(c["conditions"],variables):
                        chosen = c["sequence"]
                        break
                self.run(chosen, variables)
            elif "condition" in step:
                if not self.render(step["value_template"],variables):
                    raise Halt()
            elif "stop" in step:
                raise Halt()
            elif "event" in step:
                self.events.append((step["event"], self.render(step["event_data"],variables)))
            elif "repeat" in step:
                for item in self.render(step["repeat"]["for_each"], variables):
                    self.run(step["repeat"]["sequence"], {**variables,"repeat":{"item":item}})
            elif "wait_template" in step:
                if not self.render(step["wait_template"],variables):
                    raise Halt()
            elif "action" in step:
                name = self.render(step["action"],variables)
                target = self.render(step.get("target",{}).get("entity_id"), variables)
                data = self.render(step.get("data",{}),variables)
                if name.startswith("script."+g.P):
                    self.call(name.removeprefix("script."+g.P), **data)
                    continue
                self.actions.append((name,target,data))
                if name in ["light.turn_on", "light.turn_off", "input_boolean.turn_on", "input_boolean.turn_off"]:
                    self.states.put(target, "on" if name.endswith("turn_on") else "off")
                elif name == "input_text.set_value":
                    self.states.put(target,data["value"])
                elif name.startswith("timer."):
                    self.states.put(target,"active" if name=="timer.start" else "idle")
                elif name.startswith("script.") and "response_variable" in step:
                    variables[step["response_variable"]] = self.adapter_response
                if self.after_action:
                    self.after_action(name,target)
            else:
                raise AssertionError("Unsupported test instruction: "+str(step))
    def physical(self):
        return [a for a in self.actions if a[0].split('.')[0] in ["light","climate","alarm_control_panel"] or a[0].startswith("script.local_")]


def configured():
    cfg = g.load(g.ROOT/"config.example.yaml")
    cfg["presence"].update(people=["person.resident_a","person.resident_b"],witnesses=["binary_sensor.indoor_occupancy"])
    cfg["lighting"].update(arrival="light.entrance_demo", leave=["light.common_demo"], simulation="light.dedicated_demo")
    cfg["alarm"].update(entity="alarm_control_panel.demo",contacts=["binary_sensor.door_demo"])
    cfg["climate"].update(arrival_script="script.local_climate_arrival",away_script="script.local_climate_away")
    cfg["cameras"] = {"entrada":"script.local_photo"}
    return cfg


def empty_house(r):
    for key in ["presencia_revisada", "permitir_luces", "permitir_clima", "permitir_simulacion", "permitir_alarma", "permitir_camaras"]:
        r.states.put(g.eid("input_boolean",key),"on")
    r.states.put(g.eid("input_boolean","visitas"),"off")
    for who in ["a","b"]:
        r.states.put("person.resident_"+who,"not_home",source="device_tracker.resident_"+who)
        r.states.put("device_tracker.resident_"+who,"not_home")
    for entity in ["binary_sensor.indoor_occupancy","binary_sensor.door_demo", "light.entrance_demo","light.common_demo","light.dedicated_demo","script.local_climate_arrival","script.local_climate_away","script.local_photo"]:
        r.states.put(entity,"off")
    r.states.put("alarm_control_panel.demo","disarmed")


class PresenceTests(unittest.TestCase):
    def setUp(self):
        self.cfg = configured(); self.r = Runner(self.cfg); empty_house(self.r)
    def policy(self):
        return self.r.render(g.presence_template(self.cfg))
    def test_verified_empty(self):
        self.assertEqual(self.policy(),"Vacia verificada")
    def test_either_resident_home(self):
        for person in ["person.resident_a","person.resident_b"]:
            with self.subTest(person=person):
                empty_house(self.r); self.r.states.put(person,"home")
                self.assertEqual(self.policy(),"Ocupada")
    def test_unknown_missing_and_unavailable(self):
        for state in ["unknown","unavailable","work"]:
            with self.subTest(state=state):
                self.r.states.put("person.resident_b",state)
                self.assertEqual(self.policy(),"Desconocida")
    def test_old_or_future_tracker(self):
        for age in [901,-2]:
            self.r.states.put("device_tracker.resident_b","not_home",age=age)
            self.assertEqual(self.policy(),"Desconocida")
    def test_indoor_veto_and_quiet_period(self):
        self.r.states.put("binary_sensor.indoor_occupancy","on")
        self.assertEqual(self.policy(),"Ocupada")
        self.r.states.put("binary_sensor.indoor_occupancy","off",changed=10)
        self.assertEqual(self.policy(),"Ocupada")
    def test_witness_off_but_stale(self):
        self.r.states.put("binary_sensor.indoor_occupancy","off",age=1000)
        self.assertEqual(self.policy(),"Desconocida")
    def test_no_family_or_no_independent_witness(self):
        for key in ["people","witnesses"]:
            cfg=copy.deepcopy(self.cfg); cfg["presence"][key]=[]
            self.assertEqual(self.r.render(g.presence_template(cfg)),"Desconocida")
    def test_local_authorization_required(self):
        self.r.states.put(g.eid("input_boolean","presencia_revisada"),"off")
        self.assertEqual(self.policy(),"Desconocida")
    def test_guest_veto_overrides_unknown(self):
        self.r.states.put(g.eid("input_boolean","visitas"),"on")
        self.r.states.put("person.resident_a","unknown")
        self.assertEqual(self.policy(),"Ocupada")


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.r=Runner(configured()); empty_house(self.r)
    def test_defaults_never_act(self):
        r=Runner(configured())
        for key in ["preparar_llegada","salir_de_casa","activar_vacaciones","armar_alarma_noche","armar_alarma_fuera"]:
            r.call(key)
        r.call("camaras_telegram",camara="entrada")
        self.assertEqual(r.physical(),[])
    def test_occupied_blocks_all_absence_actions(self):
        self.r.states.put("person.resident_b","home")
        for key in ["preparar_llegada","salir_de_casa","activar_vacaciones","armar_alarma_fuera"]:
            self.r.call(key)
        self.assertEqual(self.r.physical(),[])
        self.assertEqual(self.r.states(g.eid("input_boolean","ausencia")),"off")
    def test_unknown_blocks_all_absence_actions(self):
        self.r.states.put("person.resident_b","unavailable")
        for key in ["preparar_llegada","salir_de_casa","activar_vacaciones","armar_alarma_fuera"]:
            self.r.call(key)
        self.assertEqual(self.r.physical(),[])
    def test_leave_only_allowlisted_lights(self):
        self.r.states.put("light.common_demo","on")
        self.r.states.put("light.unlisted_demo","on")
        self.r.call("salir_de_casa")
        self.assertEqual(self.r.states("light.common_demo"),"off")
        self.assertEqual(self.r.states("light.unlisted_demo"),"on")
    def test_master_blocks_but_vacation_off_always_works(self):
        self.r.states.put(g.eid("input_boolean","habilitado"),"off")
        self.r.states.put(g.eid("input_boolean","vacaciones"),"on")
        self.r.call("preparar_llegada"); self.r.call("desactivar_vacaciones")
        self.assertEqual(self.r.physical(),[])
        self.assertEqual(self.r.states(g.eid("input_boolean","vacaciones")),"off")
    def test_lease_created_and_expired_light_released(self):
        self.r.call("preparar_llegada")
        raw=self.r.states(g.eid("input_text","reserva_luz"))
        lease=from_json(raw[6:]); self.assertIsInstance(lease,dict)
        self.assertEqual(lease["entity"],"light.entrance_demo")
        lease["until"]=0
        self.r.states.put(g.eid("input_text","reserva_luz"),'lease:'+json.dumps(lease))
        self.r.call("motor",operation="liberar")
        self.assertEqual(self.r.states("light.entrance_demo"),"off")
    def test_release_preserves_light_changed_by_someone_else(self):
        self.r.call("preparar_llegada")
        lease=from_json(self.r.states(g.eid("input_text","reserva_luz"))[6:]); lease["until"]=0
        self.r.states.put(g.eid("input_text","reserva_luz"),'lease:'+json.dumps(lease))
        self.r.states.put("light.entrance_demo","on",age=-1,brightness=200)
        self.r.call("motor",operation="liberar")
        self.assertEqual(self.r.states("light.entrance_demo"),"on")
    def test_forged_lease_cannot_target_unlisted_light(self):
        self.r.states.put("light.unlisted_demo","on")
        self.r.states.put(g.eid("input_text","reserva_luz"),'lease:'+json.dumps(dict(entity="light.unlisted_demo",stamp=NOW.timestamp(),until=0)))
        self.r.call("motor",operation="liberar")
        self.assertEqual(self.r.physical(),[])
    def test_arrival_never_takes_over_already_on_lamp(self):
        self.r.states.put("light.entrance_demo","on")
        self.r.call("preparar_llegada")
        self.assertFalse(any(a[0]=="light.turn_on" for a in self.r.physical()))
    def test_daytime_or_unknown_sun_blocks_light(self):
        for sun in ["above_horizon","unavailable"]:
            self.r.states.put("sun.sun",sun); self.r.call("preparar_llegada")
        self.assertFalse(any(a[0]=="light.turn_on" for a in self.r.physical()))
    def test_presence_rechecked_after_climate_adapter(self):
        def arrival(name,target):
            if name=="script.local_climate_arrival": self.r.states.put("person.resident_b","home")
        self.r.after_action=arrival; self.r.call("preparar_llegada")
        self.assertFalse(any(a[0]=="light.turn_on" for a in self.r.physical()))
    def test_simulation_requires_vacations(self):
        self.r.call("motor",operation="simular")
        self.assertEqual(self.r.physical(),[])
        self.r.states.put(g.eid("input_boolean","vacaciones"),"on")
        self.r.call("motor",operation="simular")
        self.assertEqual(self.r.states("light.dedicated_demo"),"on")
        self.r.call("desactivar_vacaciones")
        self.assertEqual(self.r.states("light.dedicated_demo"),"off")
    def test_camera_schema_is_not_the_authorization(self):
        for value in ["../other","unknown", "script.evil", "", {}, [], None]:
            self.r.call("camaras_telegram",camara=value)
        self.assertEqual(self.r.physical(),[])
    def test_camera_fixed_adapter_and_rate_limit(self):
        self.r.call("camaras_telegram",camara="entrada")
        self.r.call("camaras_telegram",camara="entrada")
        self.assertEqual([a[0] for a in self.r.physical()],["script.local_photo"])
    def test_unconfirmed_camera_result_is_reported(self):
        self.r.adapter_response={"accepted":False}
        self.r.call("camaras_telegram",camara="entrada")
        self.assertIn("no confirmado",self.r.events[-1][1]["summary"])
    def test_open_unknown_alarm_contacts_block(self):
        for state in ["on","unknown","unavailable"]:
            self.r.states.put("binary_sensor.door_demo",state)
            self.r.call("armar_alarma_noche")
        self.assertEqual(self.r.physical(),[])
    def test_arm_only_no_disarm(self):
        self.r.call("armar_alarma_noche")
        self.assertEqual(self.r.physical()[0][0],"alarm_control_panel.alarm_arm_night")
        self.assertNotIn("alarm_disarm",json.dumps(self.r.pkg))
        self.assertNotIn("lock.unlock",json.dumps(self.r.pkg))
    def test_stale_closed_alarm_contact_blocks(self):
        self.r.states.put("binary_sensor.door_demo","off",age=1000)
        self.r.call("armar_alarma_noche")
        self.assertEqual(self.r.physical(),[])


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.r=Runner(configured())
        self.rule=dict(entity="sensor.storage_demo",label="Disco demo",kind="above",ok=[],warning=85,critical=95,category="nas",max_age_seconds=3600)
    def report(self,state,age=0):
        self.r.states.put(self.rule["entity"],state,age=age)
        return self.r.render(g.check_template([self.rule],["nas"]))
    def test_numeric_severity_and_bounds(self):
        for value,level in [(84,"OK"),(85,"Advertencia"),(95,"Critico")]:
            self.assertEqual(self.report(value)["level"],level)
    def test_unknown_non_numeric_and_nonfinite(self):
        for value in ["unknown","unavailable","garbage","nan","inf"]:
            self.assertEqual(self.report(value)["level"],"Desconocido")
    def test_ancient_data_is_not_a_current_safe_report(self):
        self.assertEqual(self.report(10,age=4000)["level"],"Desconocido")
    def test_unknown_state_not_classified_ok(self):
        self.rule.update(kind="states",ok=["normal"],warning=["attention"],critical=["failed"])
        self.assertEqual(self.report("new_vendor_state")["level"],"Desconocido")
    def test_no_checks_is_unknown(self):
        result=self.r.render(g.check_template([], ["nas","ups"]))
        self.assertEqual(result["level"],"Desconocido")
        self.assertEqual(result["uncovered"],["nas","ups"])
    def test_summary_expiry_and_restart(self):
        sensor=self.r.pkg["template"][1]["sensor"][0]
        attrs={"at":(NOW-dt.timedelta(minutes=10)).isoformat(),"summary":"OK"}
        context={"trigger":{"platform":"time_pattern"},"this":{"attributes":attrs}}
        self.assertIn("CADUCADO",self.r.render(sensor["state"],context))
        context["trigger"]["platform"]="homeassistant"
        self.assertIn("SIN REVISION",self.r.render(sensor["state"],context))
    def test_reports_perform_no_physical_actions(self):
        self.r.call("revision_seguridad"); self.r.call("estado_homelab")
        self.assertEqual(self.r.physical(),[])


class CompilerTests(unittest.TestCase):
    def test_rejects_credentials_arbitrary_services_and_recursion(self):
        for change in [lambda c:c.update(token="dummy"),lambda c:c["cameras"].update(x="shell_command.anything"),lambda c:c["climate"].update(arrival_script="script.tesla_grok_motor")]:
            cfg=configured(); change(cfg)
            with self.assertRaises(ValueError):g.validate(cfg)
    def test_duplicate_yaml_keys_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"test.yaml"; path.write_text("schema: 1\nschema: 2\n")
            with self.assertRaises(ValueError):g.load(path)
    def test_indefinite_light_duration_rejected(self):
        for value in [0,31,float('nan'),True]:
            cfg=configured();cfg["lighting"]["max_minutes"]=value
            with self.assertRaises(ValueError):g.validate(cfg)
    def test_inventory_contains_every_external_reference(self):
        refs=g.external_entities(configured())
        self.assertIn("script.local_photo",refs)
        self.assertIn("person.resident_b",refs)
        self.assertIn("light.common_demo",refs)
    def test_equal_numeric_thresholds_are_rejected(self):
        for kind in ["above","below"]:
            cfg=configured()
            cfg["homelab"]=[dict(entity="sensor.number_demo",label="Example",category="ups",kind=kind,ok=[],warning=40,critical=40,max_age_seconds=600)]
            with self.assertRaises(ValueError):g.validate(cfg)
    def test_generated_yaml_is_reproducible(self):
        import yaml
        baseline=g.load(g.ROOT/"examples/tesla_grok.yaml")
        self.assertEqual(baseline,g.build(g.load(g.ROOT/"config.example.yaml")))


if __name__=="__main__":unittest.main()
