# Instalación y rollback

## Antes de instalar

Se necesita Home Assistant con acceso a archivos, scripts YAML, templates y el servidor MCP. Este proyecto se ha preparado para Core 2026.11.2. Comprueba tu versión en Información del sistema; no presupongas que una versión anterior tiene los mismos endpoints, selectores o servicios.

El ordenador que genera el paquete necesita Python 3.10 o posterior. No instales estas herramientas dentro del entorno Python administrado de Home Assistant: usa un venv aparte.

1. Haz un backup de Home Assistant y una copia de `configuration.yaml` y de cualquier archivo que vayas a modificar. Conserva la copia fuera de `packages/`.
2. Busca `tesla_grok_` en tu configuración y en Entidades. Si ya existe, no instales este package encima. No es una actualización automática de otros proyectos con ese prefijo.
3. Revisa integraciones, estados, unidades, disponibilidad y servicios en Herramientas para desarrolladores. No pegues estados completos en un issue: pueden incluir coordenadas.
4. Mantén los archivos personales dentro de `local/`. Nunca copies `.storage`, `secrets.yaml`, bases de datos, backups o fotos al repositorio.

## Generar

El README incluye la preparación del entorno. Completa `local/config.yaml` según [configuración](configuracion.md). Puedes generar primero con las listas vacías: los informes indicarán que falta cobertura.

Opcionalmente, genera una lista de entidades en Herramientas para desarrolladores → Plantillas:

```jinja
{{ states | map(attribute='entity_id') | list | to_json }}
```

Guarda solo ese JSON en `local/entities.json` y verifica referencias al generar:

```bash
.venv/bin/python tools/generate.py --config local/config.yaml --inventory local/entities.json --output output/tesla_grok.yaml
```

Esto comprueba existencia en el inventario suministrado. No comprueba que un enchufe sea realmente una luz, que un termostato esté bien configurado o que un servicio tenga permisos; esa revisión corresponde al instalador.

## Cargar en Home Assistant

Si ya usas packages, respeta su estructura. Si no, añade **dentro del bloque `homeassistant:` existente**, sin duplicarlo:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

El archivo generado se copia como `/config/packages/tesla_grok.yaml`. Su contenido comienza por `input_boolean:`, `input_text:`, etc.; **no** debe envolverse otra vez en `tesla_grok:` con este tipo de include. Adapta la carga si utilizas `!include_dir_merge_named`. [Packages en Home Assistant](https://www.home-assistant.io/docs/configuration/packages/).

Ejecuta la comprobación de configuración antes de cargarlo. En HA OS/Supervised, desde el terminal del administrador:

```bash
ha core check
```

En Container usa el método de comprobación disponible para tu instalación. También puedes usar la comprobación YAML de Herramientas para desarrolladores. No asumas que pasar un parser YAML equivale a pasar la validación de Home Assistant.

La primera instalación añade varios tipos de helpers y puede requerir reiniciar **Home Assistant** en una ventana de mantenimiento. No reinicies el host. Si un agente administra tu instalación, pide aprobación antes del reinicio. El generador nunca instala ni reinicia nada.

Comprueba que los IDs resultantes coinciden con los documentados y no terminan en `_2`. Revisa Reparaciones y logs. No continúes si hay duplicados o errores.

## Autorizaciones locales

Los permisos de luces, clima, simulación, alarma y fotos vuelven a **OFF al arrancar Home Assistant**. El operador vuelve a habilitarlos después de revisar el estado. `visitas` arranca ON como veto conservador; `presencia_revisada` arranca OFF. Esto es deliberado, aunque implique reautorizar después de un reinicio.

Estos helpers se gestionan desde Home Assistant, sin exponerlos a Grok. Usa una tarjeta Entidades en un panel privado del operador. Añade un botón para `script.tesla_grok_desactivar_vacaciones`, que funciona sin MCP.

Al deshabilitar `input_boolean.tesla_grok_habilitado` se bloquean nuevas acciones; el conciliador todavía puede apagar una luz temporal que conserva una reserva válida. No puede cancelar un efecto que un dispositivo ya ha aceptado. Los informes de consulta siguen disponibles.

## Actualización y retirada

1. Deshabilita el proyecto y sus permisos físicos. Desactiva vacaciones desde su script. Revisa luces y adaptadores pendientes.
2. Guarda el package anterior fuera de `packages/`; genera uno nuevo con otro nombre en `output/`.
3. Compara cambios, verifica referencias y ejecuta la validación de HA antes de sustituir el archivo. Recarga los dominios que tu versión permita o programa un reinicio de HA.
4. Para rollback, restaura los archivos respaldados y vuelve a validar. Si retiras el proyecto, elimina su exposición en Assist y sus automatizaciones antes de retirar el package. Borra solo entidades huérfanas con este prefijo después de comprobarlas.
5. Revisa manualmente luces y consignas que hubiesen cambiado. El proyecto no restaura escenas completas ni inventa estados previos. Revoca la autorización OAuth de Grok si dejas de utilizar el conector.

Nunca edites directamente `.storage` ni borres todo el bloque `homeassistant:` para retirar un package.
