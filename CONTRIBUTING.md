# Contribuir

Usa un fork y pruebas con entidades ficticias. No adjuntes paquetes generados, `.storage`, fotos o logs de tu casa. No reduzcas los bloqueos de `unknown`/`unavailable` para conseguir que una prueba pase.

Antes de proponer un cambio:

1. Ejecuta `python -m unittest discover -s tests -v` en tu venv.
2. Si cambias el generador, regenera `examples/tesla_grok.yaml` exclusivamente con `config.example.yaml`, nunca con un mapa personal. El generador evita sobrescrituras; genera a un archivo temporal y compara antes de reemplazar el ejemplo.
3. Valida las ramas nuevas con la versión de Home Assistant indicada, en una configuración aislada.
4. Describe qué servicios puede ejecutar el cambio y qué pasa si falta un sensor, cambia la presencia o se interrumpe HA.
5. Escanea secretos y revisa manualmente nombres, hosts, IPs, chats y metadatos antes de hacer push.

No ejecutes tests con acceso a dispositivos reales. Los tests que requieren Home Assistant usan `--network none` y servicios simulados.
