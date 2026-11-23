# Frases y pruebas

## Sin efectos físicos

Con los permisos físicos OFF, prueba primero en la web y después con el Tesla estacionado:

| Frase | Qué debes comprobar |
|---|---|
| «Grok, revisa la seguridad de casa y dime qué información falta» | Se ejecuta `revision_seguridad`; aparece fecha nueva, severidad y cobertura ausente. |
| «Dime cómo está el homelab, priorizando las incidencias» | Se ejecuta `estado_homelab`; no inventa servidores o contenedores. |
| «¿Ese informe es nuevo o está caducado?» | Tras cinco minutos sin revisión, indica CADUCADO. |
| «Prepara mi llegada a casa» | Sin permisos no enciende luces ni llama al adaptador climático. |
| «Activa salir de casa» | Con visitas ON o alguien presente, bloquea la ausencia. |
| «Activa vacaciones» | Con presencia desconocida o visitas ON, bloquea. |
| «Desactiva vacaciones» | Funciona incluso con el proyecto deshabilitado; no restaura escenas generales. |
| «Envíame la foto de una cámara no configurada» | Bloquea el argumento aunque el cliente ignore el selector. |

No cambies estados reales de personas, trackers, puertas o alarmas para probar un fallo. Los tests del repositorio utilizan objetos y servicios simulados.

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Si una llamada queda en «En curso», revisa la traza. No repitas órdenes físicas hasta averiguar si el dispositivo aceptó la anterior. Los helpers de modo expresan una solicitud local, no una garantía de que cada dispositivo respondió.

## Pruebas con efectos, cuando tú las autorices

Habilita solo el permiso que vas a comprobar desde HA. Haz pruebas pequeñas, supervisadas y reversibles; no uses una petición de voz como la única autorización de un dispositivo peligroso.

- Luz: una lámpara verificada, en oscuridad confirmada y con presencia válida. Comprueba encendido, plazo y respeto a un cambio manual posterior.
- Salida: solo con la vivienda realmente vacía y la lista de luces revisada. Nunca «simules» que la familia está fuera en producción.
- Vacaciones: prueba la lámpara dedicada, el veto por presencia y la desactivación local. Comprueba que ninguna otra rutina usa esa lámpara.
- Cámara: «Envíame por Telegram una foto de la entrada». Comprueba el chat y el resumen; no confundas aceptación de Telegram con lectura humana.
- Combinada: «Revisa la seguridad y envíame una foto de la entrada». Requiere ambos scripts expuestos; una operación puede funcionar y la otra fallar.
- Clima: solo después de revisar el adaptador, las unidades y la persistencia de la consigna.
- Alarma: prueba el armado real únicamente con el propietario presente y el sistema preparado. No hagas esta prueba durante una validación automática.

## Diagnóstico rápido

| Síntoma | Comprobación |
|---|---|
| Herramienta no disponible | Script cargado, exposición correcta, cuenta correcta y catálogo del conector actualizado. |
| Script OFF | Normalmente está en reposo. Mira el helper de permiso y la última operación. |
| Presencia Desconocida | Lista completa, `source`, tracker reciente, testigos recientes y permiso de cobertura. |
| Permisos se apagan tras reiniciar | Política deliberada de reautorización. |
| Homelab sin cobertura | Faltan reglas o integraciones; no es prueba de que todo funcione. |
| Armado solicitado, sin confirmación | Lee el estado real mediante revisión de seguridad y la traza de la integración. |
| Foto no confirmada | Revisa adaptador, destino fijo, respuesta Telegram, watchdog y archivo temporal. |
| Luz queda encendida | Puede haberse cedido propiedad ante otro cambio o haber fallado HA; no se apaga a ciegas. |
| Web funciona; coche no | Verifica versión, sesión, disponibilidad del conector y soporte del cliente Tesla. |
