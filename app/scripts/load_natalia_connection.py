import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import (
    EventInput,
    EventParticipantInput,
    HistoricalDate,
    Period,
    SourceInput,
)
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_event, validate_fact

repo = GraphRepository(driver)

natalia_id = "2bc02dc7-68e9-4160-92a6-e0f32a35af8b"
ruzzi_id = "07317f2d-69e5-41c3-8a89-9e493a0c549a"

# 1. Ajustar etiquetas y propiedades para consistencia en Natalia Lafourcade
with driver.session() as s:
    s.run(
        """
        MATCH (p:Person {id: $id})
        SET p:Famous,
            p.real_name = $rn,
            p.best_known_for = $bkf,
            p.country = $c,
            p.principal_occupation = $occ,
            p.profile_sumary_description = $desc
        """,
        id=natalia_id,
        rn="María Natalia Lafourcade Silva",
        bkf="Natalia Lafourcade",
        c="MX",
        occ="Cantautora y productora",
        desc="Cantautora, productora, actriz y compositora mexicana. Ganadora de múltiples premios Grammy y Latin Grammy.",
    )
print("Propiedades de Natalia Lafourcade actualizadas.")

# 2. Crear Fuente (Source)
source_data = SourceInput(
    title="Natalia Lafourcade presenta Hasta la Raíz en el Auditorio Nacional",
    url="https://www.eluniversal.com.mx/espectaculos/musica/natalia-lafourcade-auditorio-nacional-hasta-la-raiz",
    publisher="El Universal / OCESA",
    author="Redacción Espectáculos",
).model_dump(mode="json")

source = repo.create("sources", source_data)
source_id = source["id"]
print("Fuente creada:", source_id, source["title"])

# 3. Crear Evento y Participantes (Facts)
event_model = EventInput(
    name="Concierto Natalia Lafourcade - Gira Hasta la Raíz en el Auditorio Nacional",
    kind="arts.performance",
    place="Auditorio Nacional, Ciudad de México",
    period=Period(
        start=HistoricalDate(year=2015, month=11, day=4, precision="day"),
        end=HistoricalDate(year=2015, month=11, day=4, precision="day"),
    ),
    source_id=source_id,
    source_locator="Crónica oficial del concierto y créditos de ensamble en vivo",
    participants=[
        EventParticipantInput(
            type_id="arts.performed_together",
            subject_id=natalia_id,
            object_id="_pending_",
            source_id=source_id,
            source_locator="Crónica oficial del concierto",
            role="performer",
            status="draft",
            note="Natalia Lafourcade encabezó la presentación en vivo de Hasta la Raíz",
        ),
        EventParticipantInput(
            type_id="arts.performed_together",
            subject_id=ruzzi_id,
            object_id="_pending_",
            source_id=source_id,
            source_locator="Créditos de ensamble en vivo y reseña del concierto",
            role="performer",
            status="draft",
            note="Marian Ruzzi formó parte del ensamble tocando teclados, guitarra y coros",
        ),
    ],
)

event_validated = validate_event(repo, event_model)
facts_validated = [
    validate_fact(repo, p, pending_context=event_validated)
    for p in event_model.participants
]

event_created = repo.create_event_with_facts(event_validated, facts_validated)
print("Evento creado:", event_created["id"], event_created["name"])

# 4. Verificar los Facts para que sean válidos en las rutas del grafo
for f in event_created["participants"]:
    fact_id = f["id"]
    current = repo.get("facts", fact_id)
    data = {
        k: v
        for k, v in current.items()
        if k not in ("id", "revision", "created_at", "updated_at")
    }
    data["status"] = "verified"
    repo.update(
        "facts",
        fact_id,
        current["revision"],
        validate_fact(repo, data),
        "verify",
    )
    print("Fact verificado:", fact_id, data["note"])

# 5. Comprobar conexiones mutuas
connections_natalia = connection_preview(repo, natalia_id)
print("\n--- Conexiones de Natalia Lafourcade ---")
print(json.dumps(connections_natalia, indent=2, ensure_ascii=False))

connections_ruzzi = connection_preview(repo, ruzzi_id)
print("\n--- Conexiones de Marian Ruzzi ---")
print(json.dumps(connections_ruzzi, indent=2, ensure_ascii=False))
