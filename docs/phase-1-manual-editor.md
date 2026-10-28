# Fase 1: editor web para poblar el grafo

> Implementado en `app/modules/graph` y `app/web`. Este documento conserva el diseño y los criterios de aceptación. El panel se sirve como HTML/CSS/JavaScript estático desde FastAPI; no requiere Jinja2. La migración de `Famous` se ejecuta con `python scripts/migrate_famous.py [--apply]` dentro del contenedor. No se ejecutó contra una base real en este entorno porque no hay una instancia de Neo4j disponible.

## Resultado buscado

Una persona del equipo con acceso a la red privada puede abrir un panel web, buscar o crear personas, registrar una fuente, añadir una relación documentada y corregirla después. Todo queda persistido en Neo4j mediante la API de FastAPI. El panel muestra los hechos cargados y las conexiones directas resultantes con su explicación y fuentes.

Esta fase es de **carga, consulta, edición y archivo de datos**. La búsqueda de rutas de varios saltos queda para la fase siguiente.

## Decisión de producto: tipos visibles y hechos guardados

El formulario mostrará **supertipo → subtipo**. El supertipo ayuda a navegar; el subtipo determina qué campos se piden y cómo se guarda el hecho. La lista se entrega desde `GET /api/v1/connection-types`, de modo que el cliente y la API usan el mismo catálogo.

«Mismo equipo» no es un evento: se deriva de dos hechos `MEMBER_OF` sobre el mismo equipo con periodos que se solapan con certeza. «Se enfrentaron» se deriva de dos participaciones en un **partido concreto** y en bandos opuestos. Las colaboraciones en obras requieren periodos de contribución compatibles; contribuciones documentadas en siglos distintos no se conectan. El usuario verá estos resultados como conexiones; Neo4j conservará los hechos que las justifican.

Las dos opciones deportivas de partido comparten la misma participación canónica. Al leer dos participantes del mismo partido, sus bandos determinan si se muestran como rivales o compañeros; no hay que duplicar el hecho por cada posible par.

| Supertipo | Subtipos iniciales visibles | Forma canónica y regla |
| --- | --- | --- |
| Deportivo | Mismo equipo; se enfrentaron; jugaron en el mismo partido y bando | Membresías de equipo con intervalo; o participantes de un partido con `side` y fecha. |
| Artístico | Colaboraron en una obra; actuaron en la misma producción; se presentaron juntos | Aportes a una `Work` o participantes de un evento concreto, con rol y periodo. La persona representada en una obra posterior no cuenta como colaboradora. |
| Político | Firmaron el mismo tratado; participaron en la misma reunión; integraron el mismo gobierno | Participación con rol `signatory`/`attendee`, o membresías simultáneas a una organización. |
| Familiar | Padre/madre de; hermanos; cónyuges | Hecho directo entre personas con fuente. Una inferencia por progenitor compartido se añadirá solo con una regla que distinga hermanos y medios hermanos. |
| Personal y profesional | Se reunieron; mentor de; colaboraron en un proyecto | Hecho directo respaldado o participación en el mismo proyecto/evento, según subtipo. |

Cada entrada del catálogo tendrá `id`, `supertype`, `label`, `shape` (`direct`, `membership`, `event`, `work`), roles admitidos, campos obligatorios, regla de derivación y plantilla de explicación. Añadir **instancias** de cualquiera de estos tipos será posible en el panel. Añadir un subtipo nuevo que requiera otra regla de derivación implica cambiar y probar esa regla; no basta con añadir una etiqueta.

Las reglas también indican qué combinaciones de roles cuentan. Dos jugadores en bandos opuestos pueden «enfrentarse»; un espectador del partido no se convierte en su rival. Dos asistentes confirmados a una reunión pueden «coincidir en la reunión», pero el sistema no afirmará que hablaron entre sí. Los eventos masivos no crearán automáticamente miles de pares.

## Datos que guardamos

- `Person`: UUID propio, nombre, alias, datos biográficos opcionales, fechas históricas con precisión y `wikidata_id` opcional. El nombre se usa para buscar, nunca como clave única.
- `Source`: UUID, título, URL **o** cita bibliográfica/archivo, autor/editor y fecha de consulta. Se puede reutilizar en varios hechos.
- `Fact`: UUID, subtipo/predicado, sujeto, objeto, rol, intervalo, estado, `primary_source_id` y `source_locator` **obligatorios**. Enlaza a la misma fuente con `SUPPORTED_BY`. Cada participación de una persona en un evento o equipo es su propio hecho y necesita su propia evidencia.
- `Event`: UUID, supertipo, subtipo, título, fecha/periodo, lugar opcional y fuente de sus datos básicos. Puede tener cualquier número de participantes; cada participación es un `Fact`.
- `Organization` y `Work`: UUID, nombre/título, tipo y fechas cuando apliquen. Las personas se unen a ellos mediante hechos de membresía o contribución.

El formulario pide el localizador de la fuente: página, sección, minuto de video, identificador de afirmación o enlace con ancla. Pegar la portada de una biografía sin indicar dónde afirma la conexión no permite marcar el hecho como verificado. Una conexión derivada expone los IDs de **todos** sus hechos y fuentes.

Fechas admitidas: día exacto, mes, año o intervalo; AEC/EC y marca de aproximación. El actual `PostFamous.date_born: date` sirve para algunas personas modernas, pero no como modelo general para personajes antiguos.

## Cliente web sencillo

Una sola aplicación FastAPI sirve HTML y archivos CSS/JavaScript propios. Es suficiente para un editor con formularios dinámicos y evita mantener un segundo servidor y un proceso de compilación frontend. [FastAPI documenta archivos estáticos](https://fastapi.tiangolo.com/tutorial/static-files/) para este uso.

Pantallas de la primera entrega:

1. **Inicio:** borradores recientes, errores de validación y accesos a «Añadir persona», «Añadir fuente» y «Añadir conexión».
2. **Personas:** búsqueda/autocompletado, alerta de posibles duplicados, alta y edición, ficha con hechos y conexiones directas.
3. **Fuentes:** biblioteca de fuentes reutilizables, alta y edición con vista de los hechos que dependen de cada fuente.
4. **Asistente de conexión:** elegir supertipo/subtipo; seleccionar o crear personas y contexto (equipo, partido, reunión, obra); introducir roles y fechas; asociar una fuente **por cada hecho**; revisar una frase de vista previa antes de guardar.
5. **Editor de evento/contexto:** añadir, editar o retirar participantes de un mismo evento sin duplicarlo. Un partido muestra bandos; una firma de tratado muestra roles; una obra muestra créditos.
6. **Revisión:** lista de borradores y acción «Verificar». Un cambio en personas, fechas, roles o fuentes de un hecho verificado lo devuelve a revisión y actualiza las conexiones derivadas.

El panel y la API de esta fase **no tendrán login ni autenticación en la aplicación**, según la decisión del equipo. Ambos se desplegarán únicamente en una red privada. La configuración actual de `docker-compose.yml` publica `8004:8000` sin dirección de host, lo que enlaza el puerto a todas las interfaces; antes del despliegue se cambiará por la IP de la red privada o por `127.0.0.1` detrás de un acceso interno. [Docker documenta el comportamiento de los puertos publicados](https://docs.docker.com/reference/compose-file/services/#ports). La elección concreta depende de cómo acceda el equipo al servidor.

## API v1 propuesta

Todos los endpoints viven bajo el `PREFIX` ya existente, por ejemplo `/relation_finder/api/v1`. `GET` devuelve JSON para el panel y futuros clientes; `POST` y `PATCH` editan datos. Toda la API permanece dentro de la red privada.

```text
GET                 /connection-types
GET, POST           /people                 # GET admite ?q= para buscar
GET, PATCH          /people/{id}
GET, POST           /sources                # GET admite ?q= para buscar
GET, PATCH          /sources/{id}
GET, POST           /organizations
GET, PATCH          /organizations/{id}
GET, POST           /works
GET, PATCH          /works/{id}
GET, POST           /events
GET, PATCH          /events/{id}
GET, POST           /facts
GET, PATCH          /facts/{id}
POST                /facts/{id}/verify
POST                /facts/{id}/archive
GET                 /people/{id}/connections
```

El asistente usa estos endpoints para crear o reutilizar entidades y luego guardar hechos. `POST /events` aceptará opcionalmente `participants[]`, cada uno con rol, fuente y localizador, para guardar el evento y sus participaciones en una misma operación transaccional. Así una carga incompleta no aparenta una reunión verificada.

Respuestas relevantes: `422` por fechas, roles o fuente faltante; `404` si una entidad/fuente referida no existe; `409` por conflicto de edición o identidad externa duplicada. El API devuelve IDs propios, estado y versión. No se borra físicamente un hecho: se archiva para conservar el historial de por qué cambió una conexión.

## Neo4j y edición segura

1. Añadir restricciones únicas para `id` de `Person`, `Source`, `Fact`, `Event`, `Organization` y `Work`; `wikidata_id` de `Person` cuando exista. Usar migraciones idempotentes y comprobar duplicados antes de aplicar restricciones. [Neo4j documenta estas restricciones](https://neo4j.com/docs/cypher-manual/5/constraints/create-constraints/).
2. Guardar un hecho, su `primary_source_id`, el enlace `SUPPORTED_BY` y sus participantes en la misma transacción. Rechazar hechos sin fuente en la API y verificar la existencia de la fuente dentro de la transacción. Las [transacciones gestionadas del driver](https://neo4j.com/docs/python-manual/current/transactions/) sirven para ese límite atómico.
3. Versionar con `revision`, `created_at`, `updated_at` y un registro de cambios. `PATCH` requiere la revisión que el editor abrió; un `409` evita sobrescribir una edición ajena. Se puede añadir un nombre de editor escrito manualmente, pero sin login no se tratará como identidad verificada.
4. Para mostrar conexiones directas, derivarlas de los hechos al leer o mantener una vista reconstruible. Al editar o archivar un hecho, la conexión deja de mostrarse si perdió el respaldo necesario.
5. **Migrar** los nodos `Famous` existentes en una operación repetible: informe previo de duplicados, UUID nuevo y etiqueta `Person`, conservando los nodos y su imagen. El endpoint antiguo puede delegar temporalmente en el nuevo servicio.

Neo4j Community no obliga a que exista una propiedad mediante una restricción de existencia; la exigencia de fuente debe estar en validación de la API, transacciones y pruebas, incluso si se usa una edición de Neo4j que sí ofrezca esa restricción. [Neo4j distingue las restricciones disponibles por edición](https://neo4j.com/docs/cypher-manual/5/constraints/).

## Orden de entrega y criterios de aceptación

1. **Esquema y migración:** modelos, restricciones, migración de `Famous`, repositorios Neo4j y pruebas con una base de desarrollo. No se elimina información existente.
2. **API de edición:** CRUD de personas, fuentes, contextos y hechos; catálogo inicial de subtipos mantenido en código, estados y validación temporal.
3. **Panel:** búsqueda, asistentes por subtipo, edición, archivo, revisión y vista previa de conexiones directas. Se entrega desde el mismo contenedor FastAPI.
4. **Verificación completa:** pruebas del API y de consultas contra Neo4j, más recorridos manuales del panel.

La fase se acepta cuando se puedan reproducir estos casos en Neo4j:

- Dos membresías con fechas solapadas muestran «mismo equipo» con **dos fuentes**; sin solapamiento no aparece la conexión.
- Dos personas en bandos opuestos del mismo partido muestran «se enfrentaron»; compartir bando no genera ese subtipo.
- Dos creadores contemporáneos en una obra muestran colaboración; ser el tema de una obra posterior no genera conexión.
- Dos firmantes de una firma concreta se conectan mediante ese evento, con la fuente de cada participación.
- Un parentesco directo guarda dirección, fechas cuando existan y fuente. Dos personas homónimas siguen siendo entidades distintas.
- Un hecho sin fuente o con fuente inexistente se rechaza. Editar fechas, roles o fuentes actualiza la vista de conexiones y deja registro de la corrección.
- Los datos sobreviven al reinicio de la aplicación; panel y API solo son accesibles desde la red privada acordada.

## Alcance confirmado

- Panel desplegable para el equipo, sin autenticación de aplicación y fuera del acceso público.
- Migración conservadora de los `Famous` existentes a `Person`.
- Catálogo inicial amplio de supertipos/subtipos, ampliable en código. El panel crea y edita instancias, no definiciones de tipos.
- Fase 1 limitada al CRUD y a la revisión de conexiones directas; la búsqueda de caminos queda para la fase siguiente.

La única configuración de despliegue que queda por precisar al implementarla es si el equipo accede por LAN, VPN o un proxy interno; eso determina a qué IP privada se enlaza el puerto.
