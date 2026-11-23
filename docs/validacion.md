# Validación de la versión inicial

Fecha de revisión: 23 de noviembre de 2026.

## Alcance

La validación usa entidades ficticias y contenedores aislados, sin acceso a una instalación doméstica. No se ha desplegado este starter genérico en una casa ni se ha probado su conexión real de extremo a extremo con Grok/Tesla. El código debe adaptarse y validarse en cada instalación antes de autorizar efectos físicos.

| Comprobación | Resultado |
|---|---|
| Tests offline de políticas y compilador | 40 pruebas; presencia, disponibilidad, caducidad, listas cerradas, reserva de luces, alarmas y cámara simulada. |
| Configuración HA: paquete sin dependencias | Validada con Core 2026.11.2. |
| Configuración HA: ramas opcionales y adaptadores ficticios | Validada con Core 2026.11.2. |
| Motor real de scripts y templates | Informe estructurado, bloqueos de inicio y encendido/apagado de una luz simulada con reserva. |
| Credenciales y privacidad | Revisión de archivos y escaneo local de secretos; contenido sintético, sin historial importado. |
| OAuth, exposición y catálogo MCP de otra casa | Pendiente de cada instalación. |
| Dispositivos físicos, entrega Telegram y cliente Tesla | No ejecutados por esta validación. |

La comprobación de HA valida esquemas y plantillas; no garantiza que existan los dispositivos ficticios ni que tu integración soporte sus servicios. Las pruebas del motor sustituyen los servicios de luz por funciones en memoria. Los adaptadores se validan como configuración; no se transmiten imágenes ni se modifica climatización.

## Reproducir

Desde un venv con las dependencias instaladas:

```bash
python -m unittest discover -s tests -v
python tools/prepare_validation.py
```

Si dispones de Docker, descarga la imagen oficial y usa los archivos sintéticos anteriores:

```bash
docker pull ghcr.io/home-assistant/home-assistant:2026.11.2
docker run --rm --network none --entrypoint python \
  -v "$PWD/output/validation/baseline:/config" \
  ghcr.io/home-assistant/home-assistant:2026.11.2 \
  -m homeassistant --script check_config --config /config
docker run --rm --network none --entrypoint python \
  -v "$PWD/output/validation/configured:/config" \
  ghcr.io/home-assistant/home-assistant:2026.11.2 \
  -m homeassistant --script check_config --config /config
docker run --rm --network none --entrypoint python \
  -v "$PWD:/work:ro" \
  ghcr.io/home-assistant/home-assistant:2026.11.2 /work/tools/ha_smoke.py
```

No montes `/config` de producción, sockets Docker, credenciales ni dispositivos en esas pruebas. La imagen usada inicialmente tuvo digest `sha256:493a07e8f6530fc640223f4a0a5248f20a61ca2f718bb1d31efbf08a2c5ea28f`.

Para escanear secretos con Gitleaks local, sin enviar archivos a un servicio externo:

```bash
gitleaks dir . --redact=100
gitleaks git . --log-opts=--all --redact=100
```

Un escaneo sin hallazgos no demuestra que no exista información sensible. Revisa además nombres, dominios, direcciones, chats, inventarios, capturas y metadatos. No publiques el resultado completo de un escaneo que haya encontrado un secreto.
