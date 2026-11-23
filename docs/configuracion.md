# Configurar las entidades de tu casa

Todos los IDs de esta página son **ejemplos ficticios**. Sustitúyelos por entidades verificadas. Si no dispones de una dependencia, deja su lista vacía o su valor `null`. No rellenes el mapa con nombres que simplemente parezcan razonables.

## Presencia

```yaml
presence:
  people: [person.resident_a, person.resident_b]
  witnesses: [binary_sensor.indoor_occupancy]
  max_age_seconds: 900
  quiet_seconds: 300
```

Incluye a TODOS los residentes y sensores interiores que cubran la vivienda. Las personas deben indicar `not_home`, tener `source` de tipo `device_tracker` y ese tracker debe confirmar `not_home` con un informe reciente. Una zona nombrada como `work` se considera desconocida en esta política conservadora.

Los testigos interiores vetan la ausencia si están ON o han pasado a OFF hace poco. Un testigo ausente, desconectado o antiguo bloquea la ausencia. Se requiere al menos una persona y un testigo: las listas vacías nunca equivalen a vivienda vacía.

En HA habilita `input_boolean.tesla_grok_presencia_revisada` solo después de comprobar la cobertura completa. `input_boolean.tesla_grok_visitas` debe estar ON mientras haya invitados, cuidadores o personas sin seguimiento. Si el detector no informa regularmente, la política bloqueará por antigüedad; comprueba su funcionamiento antes de ampliar el plazo.

Una persona quieta puede no generar movimiento. Esta combinación reduce errores, pero **no demuestra físicamente que no quede nadie**. No uses el proyecto para autorizar cerraduras, garajes o maquinaria.

## Seguridad: estados explícitos

Cada regla tiene ocho campos. Los estados se escriben entre comillas para que YAML no transforme `on`/`off` en booleanos.

```yaml
security:
  - entity: binary_sensor.door_demo
    label: Puerta de ejemplo
    category: puertas
    kind: states
    ok: ["off"]
    warning: ["on"]
    critical: []
    max_age_seconds: 3600
  - entity: binary_sensor.smoke_demo
    label: Humo de ejemplo
    category: humo
    kind: states
    ok: ["off"]
    warning: []
    critical: ["on"]
    max_age_seconds: 3600
```

Categorías: `puertas`, `ventanas`, `alarma`, `humo`, `agua`, `otros`. Para una cerradura, clasifica `locked` y `unlocked` según tu política; solo se consulta. Para una alarma puedes considerar `triggered` crítico, `disarmed` advertencia y los modos de armado conocidos OK. Un estado no clasificado se considera desconocido.

El informe indica categorías ausentes, por lo que no dará OK general si falta humo, agua, alarma, puertas o ventanas. Los valores conservados por HA pueden estar desactualizados: cada regla comprueba `last_reported`. Eso mide recepción en HA, no una prueba física de que el sensor funcione. Adapta el plazo al intervalo real de la integración.

## Homelab

```yaml
homelab:
  - entity: sensor.storage_used_demo
    label: Uso NAS ejemplo
    category: nas
    kind: above
    ok: []
    warning: 85
    critical: 95
    max_age_seconds: 1800
  - entity: sensor.ups_battery_demo
    label: Bateria UPS ejemplo
    category: ups
    kind: below
    ok: []
    warning: 40
    critical: 20
    max_age_seconds: 600
```

`above` alerta al alcanzar o superar el umbral; `below`, al alcanzarlo o bajar. Verifica unidades: un porcentaje y una fracción 0–1 no son intercambiables. `NaN`, infinito o texto no equivalen a cero.

Categorías: `servidores`, `nas`, `ups`, `docker`, `zabbix`. También puedes usar reglas `states`, con los valores exactos de tu integración. El resumen prioriza incidencias y muestra las dos primeras; los atributos guardan la lista y las fuentes sin datos. La cobertura por categoría significa que hay una regla, no que todos tus servidores estén monitorizados.

Si no tienes Zabbix integrado, deja esa cobertura ausente. No se instala ninguna API ni se solicita una contraseña. Una futura conexión debería usar una identidad de lectura limitada a los hosts necesarios y publicar métricas agregadas; nunca poner un token en este archivo o un comando administrativo accesible desde Grok.

Los informes expiran a los cinco minutos y se invalidan al arrancar HA. Ejecutar el script renueva la evaluación; consultar un resumen antiguo no equivale a haber realizado otra revisión.

## Luces, clima, alarma y cámaras

```yaml
lighting:
  arrival: light.entrance_demo
  leave: [light.common_demo]
  simulation: light.dedicated_demo
  max_minutes: 10
climate:
  arrival_script: script.local_climate_arrival
  away_script: script.local_climate_away
alarm:
  entity: alarm_control_panel.demo
  contacts: [binary_sensor.door_demo]
cameras:
  entrada: script.local_photo
```

La lista `leave` admite únicamente `light.*`. Un enchufe de servidor no tiene lugar aquí. Convierte un interruptor en luz solo después de comprobar su carga, siguiendo [extensiones](extensiones.md).

La simulación usa **una lámpara dedicada**, entre las 18:00 y las 23:00, solo de noche y con vacaciones, presencia y permisos válidos. Un disparo cada hora añade entre 1 y 15 minutos de variación. Cada encendido dura como máximo `max_minutes` mientras HA siga operativo y conserve la propiedad de la luz. No hay listas de toda la casa ni escenas de restauración general.

La reserva guarda entidad, plazo y `last_updated`; si alguien o una integración actualiza la luz, el proyecto cede su propiedad y no la apaga. Esto prioriza no interferir, pero puede dejarla encendida. Un comando manual idéntico que HA no refleje no puede distinguirse: usa una lámpara dedicada y considera un autoapagado propio del dispositivo. Después de una caída de HA revisa su estado manualmente.

El tiempo máximo del package controla las **luces**, no los adaptadores climáticos. Los adaptadores tienen su propia política de duración y restauración. No actives uno hasta revisar ese comportamiento. Los ejemplos climáticos conservan la consigna aplicada y no encienden un modo HVAC que estuviese apagado.

El armado solo se habilita con alarma y lista completa de contactos configuradas. Los contactos deben estar cerrados y tener un informe dentro de `presence.max_age_seconds`, también de noche. Debes verificar soporte de `alarm_arm_night`/`alarm_arm_away`, zonas y retardos en tu integración. Si exige código, este ejemplo no lo envía: la petición fallará y deberás revisar la integración sin exponer el código a Grok.
