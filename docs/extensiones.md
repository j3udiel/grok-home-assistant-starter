# Adaptadores opcionales

El núcleo nunca instala integraciones ni solicita credenciales. Los adaptadores son scripts privados revisados por el propietario. El mapa acepta solo `script.*`, bloquea referencias recursivas al proyecto y no recibe entidades o servicios arbitrarios desde la conversación.

## Fotos por Telegram

Necesitas una cámara capaz de `camera.snapshot` y una entidad `notify` del chat correcto de la integración Telegram bot. Comprueba ese destino con una prueba manual autorizada: que haya un bot no implica que el chat elegido sea el correcto.

La receta [adapters.yaml](../examples/adapters.yaml) fija una cámara, una entidad de chat y un único archivo `/media/tesla_grok_demo.jpg`. Sustituye los IDs ficticios y, si procede, el nombre de archivo por otro **literal y exclusivo**. No añadas parámetros de URL, ruta, chat o comandos a la herramienta pública.

1. Instala Telegram bot desde HA si lo necesitas. Introduce sus credenciales solo en la configuración privada de la integración.
2. Asegúrate de que el directorio existe y que `camera.snapshot` y Telegram pueden usarlo. Si tu instalación lo exige, fusiona `/media` con `homeassistant.allowlist_external_dirs`; no dupliques el bloque. Evita `/config/www`: sus ficheros pueden servirse como recursos estáticos.
3. Copia la receta adaptada a un package privado y valida HA. No expongas `script.local_photo`, `shell_command.local_photo_cleanup` ni el notify o la cámara.
4. Mapea `cameras: {entrada: script.local_photo}` en tu archivo local y regenera el núcleo. Expón solo `script.tesla_grok_camaras_telegram` y el resumen de última operación.
5. Autoriza fotos mediante el helper local. Pide una única foto y comprueba el chat. Esta prueba transmite una imagen real: decide cuándo y a quién puedes enviarla antes de ejecutarla.

La receta elimina el archivo anterior antes de capturar y comprueba que la limpieza terminó; así no reenvía una imagen vieja como si fuera nueva. Después comprueba la respuesta de Telegram y vuelve a limpiar. El watchdog detiene un envío de más de tres minutos; una limpieza periódica retira residuos cuando el adaptador está parado. Una caída de HA puede dejar un archivo temporal; no lo incluyas en un backup público.

El contrato de respuesta es un diccionario `{"accepted": true}` solo cuando el destino ha aceptado el mensaje. Un script que únicamente devuelve éxito de ejecución no basta. Verifica el esquema de respuesta de tu versión antes de modificar la receta. [Telegram bot y destinatarios](https://www.home-assistant.io/integrations/telegram_bot/), [camera.snapshot](https://www.home-assistant.io/integrations/camera/).

Para más cámaras, crea adaptadores privados independientes con archivos exclusivos y añade palabras al mapa. Ajusta el watchdog y la limpieza para cada adaptador. No reutilices el mismo archivo para envíos concurrentes. Este starter envía una cámara por solicitud; no incluye una orden «todas».

Grok informa del envío; no ve ni analiza la imagen. «Revisa la seguridad y envíame una foto de la entrada» son dos operaciones independientes y deben confirmarse por sus respectivos resultados.

## Climatización

La receta incluye un ejemplo de consigna fija para un equipo **ya en modo calefacción** y otro de preset `away` si el equipo lo admite. No cambia de `off` a `heat`, no adivina si un enchufe alimenta calefacción o refrigeración y no restaura configuraciones anteriores.

Antes de habilitarlo, comprueba equipo, unidades, consigna, modos y temperaturas recientes. La receta de llegada presupone que HA y el termostato trabajan en °C; ajústala si utilizas otra unidad. Conserva los permisos y validaciones internos. Haz una prueba con efectos físicos solo cuando el propietario la autorice.

Las consignas de ejemplo **persisten**: el temporizador de luz del núcleo no las revierte. Para preparación climática con duración máxima, implementa un adaptador específico que guarde modo/consigna, compruebe que sigue siendo propietario del cambio y restaure solo entonces. Mientras no esté revisado, deja `arrival_script: null` y `permitir_clima` apagado.

Si prefieres el control directo de temperatura desde Grok, puedes exponer deliberadamente un termostato real a Assist. Eso amplía el control y evita los guardas del package para ese dispositivo; decide si encaja con tu caso. Nunca expongas el enchufe de un calefactor como si fuera una luz. [Acciones climate](https://www.home-assistant.io/integrations/climate/).

## Armado

El núcleo solo llama a `alarm_control_panel.alarm_arm_night` y `alarm_arm_away`. No hay servicio de desarmado, PIN por voz, bypass ni armado forzado.

Configura una lista completa de contactos relevantes. La receta exige que todos estén OFF también de noche; si tu modo noche permite alguna apertura, revisa esa política explícitamente en tu fork. Verifica zonas y retardos en Alarmo u otra integración existente. No se instala Alarmo automáticamente.

La orden informa «solicitado», no «armado»: añade la alarma a las reglas del informe de seguridad y consulta su estado después. No expongas directamente la entidad de alarma para obtener ese dato. [Acciones de alarma](https://www.home-assistant.io/integrations/alarm_control_panel/).

## Interruptores que realmente son luces

Si un `switch` alimenta una lámpara ordinaria, usa el helper de Home Assistant para cambiar el tipo de dispositivo y representarlo como luz. Verifica que el nuevo `light.*` controla exactamente la carga esperada y úsalo en el mapa. Evita exponer simultáneamente controles duplicados que confundan a Grok. [Switch as X](https://www.home-assistant.io/integrations/switch_as_x/).

No conviertas enchufes de servidores, calefactores, bombas, cámaras o equipos críticos para que encajen en la lista de luces.
