# Conectar Grok y probar desde el Tesla

## Endpoint y usuario

1. Configura un acceso HTTPS válido a HA que sea alcanzable por el servicio de Grok. Usa el acceso remoto que ya tengas; no abras puertos ni desactives comprobaciones TLS como parte de esta guía.
2. Crea en HA una cuenta dedicada **no administradora**, con contraseña exclusiva. No escribas su contraseña en Grok, el repositorio o un script.
3. En Ajustes → Sistema → IA, habilita MCP si procede y copia la URL individual **Device control**. Debe terminar en `/api/mcp/assist`. Ejemplo reservado para documentación: `https://ha.example.com/api/mcp/assist`.
4. En `https://grok.com/connectors`, crea un conector Custom y completa el inicio de sesión OAuth en HA con esa cuenta. Evita que una sesión previa del navegador seleccione al administrador.

El endpoint principal `/api/mcp` puede ofrecer conjuntos administrativos. Esta guía usa la URL individual de Device control, cuyos permisos no se configuran mediante las opciones de la URL principal. [MCP de Home Assistant](https://www.home-assistant.io/integrations/mcp_server/), [conectores personalizados de Grok](https://docs.x.ai/grok/connectors).

## Exposición mínima

En las entidades expuestas a los asistentes de voz/conversación, habilita estos scripts según las funciones configuradas:

| Orden | Entidad |
|---|---|
| Revisar seguridad | `script.tesla_grok_revision_seguridad` |
| Informar homelab | `script.tesla_grok_estado_homelab` |
| Preparar llegada | `script.tesla_grok_preparar_llegada` |
| Salir de casa | `script.tesla_grok_salir_de_casa` |
| Activar vacaciones | `script.tesla_grok_activar_vacaciones` |
| Desactivar vacaciones | `script.tesla_grok_desactivar_vacaciones` |
| Armar de noche, opcional | `script.tesla_grok_armar_alarma_noche` |
| Armar fuera, opcional | `script.tesla_grok_armar_alarma_fuera` |
| Foto, opcional | `script.tesla_grok_camaras_telegram` |

Expón también `sensor.tesla_grok_seguridad`, `sensor.tesla_grok_homelab`, `sensor.tesla_grok_presencia`, `sensor.tesla_grok_modos` y `sensor.tesla_grok_ultima_operacion`. No necesitas exponer los sensores individuales del inventario.

Mantén sin exponer los helpers, `script.tesla_grok_motor`, automatizaciones, temporizadores y adaptadores `script.local_*`. Tampoco expongas alarmas, cerraduras, garajes, cámaras o interruptores críticos como controles directos para este proyecto. Conserva otras exposiciones deliberadas de tu instalación, revisando su alcance.

La cuenta no administradora y la lista de exposición cumplen funciones distintas. La exposición no es una nueva lista de permisos de usuario para toda la API de HA; revisa [los límites](../SECURITY.md).

## Comprobación en la web

Primero pide una revisión de seguridad y después su sensor. El nombre MCP generado suele ser `script__tesla_grok_revision_seguridad`; el cliente puede añadir otro prefijo. Pide a Grok que descubra sus herramientas, sin inventar un nombre prefijado.

Si has añadido un script y no aparece, comprueba su exposición y que cargó sin errores. Reconecta el conector y abre una conversación nueva si sigue mostrando un catálogo anterior. No cambies al endpoint administrativo para solventarlo. Un script con estado `off` está en reposo; ese estado no significa que esté deshabilitado.

En el código de HA 2026.11.2, los scripts se publican como herramientas y no aparecen en la lista de entidades del contexto vivo. Que una consulta al dominio `script` no los liste no demuestra que falte exposición. [Implementación del contexto](https://github.com/home-assistant/core/blob/2026.11.2/homeassistant/components/homeassistant/llm.py), [herramientas de scripts](https://github.com/home-assistant/core/blob/2026.11.2/homeassistant/components/script/llm.py).

No des por ejecutada una acción solo porque Grok diga que llamó a una herramienta. Consulta el resumen, su fecha y las trazas. El selector de una cámara ayuda al modelo; la lista permitida se comprueba otra vez dentro del script.

## Pasar al coche

Con el vehículo estacionado, comprueba versión, procesador, conexión y sesión de Grok según [los requisitos de Tesla](https://www.tesla.com/support/grok). Usa la misma cuenta en la que configuraste el conector y verifica si el cliente del coche permite usarlo.

Empieza con «Revisa la seguridad de casa». Si la web funciona pero el coche no descubre las herramientas, anota versión de software, región y tipo de cuenta para consultar soporte. No habilites administración ni publiques tokens como solución. La disponibilidad general de Connectors no acredita que todo servidor MCP personalizado funcione en cada cliente.

Una integración Tesla/Fleet en HA sería una dependencia distinta, útil para datos del coche pero innecesaria para esta arquitectura de órdenes. Nunca se usa la ubicación de un único coche como prueba de vivienda vacía.
