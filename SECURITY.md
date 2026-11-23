# Seguridad y privacidad

## Qué limita este proyecto

Grok recibe scripts con operaciones cerradas y resúmenes. Las entidades y destinos se eligen localmente, no mediante texto libre de voz. Las acciones físicas requieren permisos internos; la ausencia exige fuentes conocidas, recientes y cobertura revisada. Un dato ausente o `unavailable` bloquea las acciones de ausencia.

El motor serializa llegada, salida, vacaciones y armado. Las fotos tienen una lista cerrada, ejecución única y límite de frecuencia. No hay desarmado, apertura de cerraduras, control de garajes, apagado de servidores ni ejecución shell arbitraria. El adaptador de fotos de ejemplo usa solo una limpieza con ruta fija.

Los eventos solo transportan informes; no son credenciales ni autorizaciones. Las instrucciones de voz, descripciones de herramientas y selectores no sustituyen las comprobaciones dentro de HA.

## Qué no garantiza

- Una identidad OAuth comprometida, un administrador o una integración maliciosa pueden tener acceso más amplio que estas herramientas. Una cuenta no administradora no equivale a un aislamiento por entidad para toda la API. Protege la sesión de Grok y revoca autorizaciones que no uses.
- Assist puede compartir exposición entre clientes. Revisa todos los controles ya expuestos: exponer directamente un termostato permite usar sus acciones sin pasar por los permisos de este package.
- La presencia es una inferencia. Los sensores pueden fallar o publicar datos antiguos con apariencia reciente. No sirve para autorizar acciones de alto riesgo.
- El temporizador requiere que HA esté operativo. La propiedad de una luz se infiere de su estado y fecha de actualización; no es una reserva exclusiva impuesta al dispositivo. Se cede ante cambios, y una orden idéntica puede no dejar huella. Usa una lámpara dedicada y revisa después de fallos.
- Los adaptadores privados son parte del código de confianza. Deben mantener destinos fijos, comprobar disponibilidad, evitar reintentos ciegos y documentar efectos. Una respuesta positiva de Telegram no demuestra que una persona haya leído la foto.
- Las fotos se transmiten a Telegram. No se exponen a Grok para análisis visual. Las capturas temporales pueden persistir si se interrumpe un envío; revisa limpieza y backups.
- Las trazas, estados e historiales pueden contener información doméstica. No los publiques sin revisar. Este repositorio no es una auditoría de la red, de TLS ni de las integraciones instaladas por cada usuario.

## Datos que no debes subir

Credenciales, `.storage`, `secrets.yaml`, URLs de tu casa, direcciones IP, coordenadas, IDs de chats, nombres de familiares, inventarios de presencia, capturas, logs, backups y paquetes generados con entidades reales. `local/` y `output/` están ignorados por defecto; Git ignore no elimina archivos ya comprometidos.

Para compartir un caso, usa entidades ficticias y un ejemplo mínimo. Si se filtra un secreto, revócalo o rótalo primero; borrarlo del último commit no lo elimina del historial, forks o copias.

El contenido de este repositorio es genérico. Publicarlo desde una cuenta personal de GitHub sigue vinculándolo al perfil y a los metadatos públicos de autoría; no proporciona anonimato de identidad del propietario.

## Parar el proyecto

Desactiva el helper maestro en HA y los permisos físicos. Usa el script local de desactivación de vacaciones y comprueba trabajos en curso. El conciliador puede completar la limpieza de una luz propia. Una llamada ya aceptada por un servicio externo no se puede deshacer revocando el permiso después.

Si necesitas una parada inmediata, cancela desde HA los scripts del proyecto y los adaptadores privados, y revisa manualmente luces/clima. Desactivar Grok no sustituye a los controles locales de seguridad.
