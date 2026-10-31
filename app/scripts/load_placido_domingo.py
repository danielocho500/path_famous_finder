import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import (
    EventInput,
    EventParticipantInput,
    HistoricalDate,
    Period,
    PersonInput,
    SourceInput,
)
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_event, validate_fact

repo = GraphRepository(driver)

natalia_id = "2bc02dc7-68e9-4160-92a6-e0f32a35af8b"

# 1. Actualizar imagen de Natalia Lafourcade con la URL verificada
natalia_image = "https://upload.wikimedia.org/wikipedia/commons/b/b2/Natalia_Lafourcade_-_Premios_Goya_2023.jpg"
with driver.session() as s:
    rec = s.run("MATCH (p:Person {id: $id}) RETURN p.data as data", id=natalia_id).single()
    if rec and rec["data"]:
        data_json = json.loads(rec["data"])
        data_json["image_url"] = natalia_image
        s.run(
            "MATCH (p:Person {id: $id}) SET p.image_url = $img, p.data = $data",
            id=natalia_id,
            img=natalia_image,
            data=json.dumps(data_json, ensure_ascii=False),
        )
print("Imagen de Natalia Lafourcade actualizada a versión verificada.")

# 2. Crear a Plácido Domingo
placido_input = PersonInput(
    name="Plácido Domingo",
    aliases=["José Plácido Domingo Embil", "Plácido Domingo Embil"],
    description=(
        "Cantante de ópera (tenor y barítono), director de orquesta y gestor cultural español. "
        "Miembro histórico de Los Tres Tenores y una de las figuras líricas más galardonadas e influyentes "
        "de la música internacional."
    ),
    country="ES",
    city_born="Madrid",
    image_url="https://upload.wikimedia.org/wikipedia/commons/0/09/Concierto_de_Pl%C3%A1cido_Domingo_%28cropped%29.jpg",
    wikidata_id="Q180896",
    birth=HistoricalDate(year=1941, month=1, day=21, precision="day"),
).model_dump(mode="json")

placido = repo.create("people", placido_input)
placido_id = placido["id"]
print("Creado Plácido Domingo con ID:", placido_id)

# Ajustar etiquetas y props de compatibilidad
with driver.session() as s:
    s.run(
        """
        MATCH (p:Person {id: $id})
        SET p:Famous,
            p.real_name = $rn,
            p.best_known_for = $bkf,
            p.country = $c,
            p.image_url = $img,
            p.principal_occupation = $occ,
            p.profile_sumary_description = $desc
        """,
        id=placido_id,
        rn="José Plácido Domingo Embil",
        bkf="Plácido Domingo",
        c="ES",
        img=placido_input["image_url"],
        occ="Cantante de ópera y director de orquesta",
        desc=placido_input["description"],
    )

# 3. Crear Fuente de evidencia histórica
source_input = SourceInput(
    title="Plácido en el alma: un Bernabéu entregado al tenor y sus invitados",
    url="https://elpais.com/cultura/2016/06/29/actualidad/1467228801_633659.html",
    publisher="El País",
    author="Jesús Ruiz Mantilla",
).model_dump(mode="json")

source = repo.create("sources", source_input)
source_id = source["id"]
print("Fuente creada:", source_id, source["title"])

# 4. Crear Evento y Participantes
event_model = EventInput(
    name="Concierto Plácido en el Alma en el Estadio Santiago Bernabéu",
    kind="arts.performance",
    place="Estadio Santiago Bernabéu, Madrid, España",
    period=Period(
        start=HistoricalDate(year=2016, month=6, day=29, precision="day"),
        end=HistoricalDate(year=2016, month=6, day=29, precision="day"),
    ),
    source_id=source_id,
    source_locator="Crónica oficial del concierto y reseña de actuaciones en El País",
    participants=[
        EventParticipantInput(
            type_id="arts.performed_together",
            subject_id=natalia_id,
            object_id="_pending_",
            source_id=source_id,
            source_locator="Crónica oficial del concierto en El País",
            role="performer",
            status="draft",
            note="Natalia Lafourcade actuó como artista invitada en el concierto homenaje a Plácido Domingo en el Santiago Bernabéu",
        ),
        EventParticipantInput(
            type_id="arts.performed_together",
            subject_id=placido_id,
            object_id="_pending_",
            source_id=source_id,
            source_locator="Crónica oficial del concierto y programa",
            role="performer",
            status="draft",
            note="Plácido Domingo encabezó el macroconcierto benéfico Plácido en el Alma ante más de 60.000 espectadores",
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

# 5. Verificar ambos hechos
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

# 6. Comprobar conexiones mutuas
print("\n--- Conexiones de Plácido Domingo ---")
print(json.dumps(connection_preview(repo, placido_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Natalia Lafourcade ---")
print(json.dumps(connection_preview(repo, natalia_id), indent=2, ensure_ascii=False))
