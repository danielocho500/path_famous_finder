import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

tagore_id = "e13c9122-48fb-4673-a24e-af9cb2ad2b7d"

# 1. Crear a Albert Einstein
einstein_input = PersonInput(
    name="Albert Einstein",
    aliases=[
        "Albert Einstein",
    ],
    description=(
        "Físico teórico nacido en Alemania, considerado el científico más influyente del siglo XX. "
        "Desarrolló la teoría de la relatividad general y especial, y recibió el Premio Nobel de Física "
        "en 1921 por sus contribuciones a la física teórica y el efecto fotoeléctrico."
    ),
    country="DE",
    city_born="Ulm",
    image_url="https://upload.wikimedia.org/wikipedia/commons/2/28/Albert_Einstein_Head_cleaned.jpg",
    wikidata_id="Q937",
    birth=HistoricalDate(year=1879, month=3, day=14, precision="day"),
    death=HistoricalDate(year=1955, month=4, day=18, precision="day"),
).model_dump(mode="json")

einstein = repo.create("people", einstein_input)
einstein_id = einstein["id"]
print("Creado Albert Einstein con ID:", einstein_id)

# Ajustar propiedades de compatibilidad
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
        id=einstein_id,
        rn="Albert Einstein",
        bkf="Albert Einstein",
        c="DE",
        img=einstein_input["image_url"],
        occ="Físico teórico (Premio Nobel de Física)",
        desc=einstein_input["description"],
    )

# 2. Crear Fuente (Source)
source_input = SourceInput(
    title="The Nature of Reality: Albert Einstein and Rabindranath Tagore in Conversation (1930)",
    url="https://en.wikipedia.org/wiki/Albert_Einstein",
    publisher="The Modern Review / Einstein Archives Online",
    author="Albert Einstein & Rabindranath Tagore",
).model_dump(mode="json")

source = repo.create("sources", source_input)
source_id = source["id"]
print("Fuente creada:", source_id, source["title"])

# 3. Crear Hecho de encuentro (personal.met)
fact_input = FactInput(
    type_id="personal.met",
    subject_id=einstein_id,
    object_id=tagore_id,
    source_id=source_id,
    source_locator="Encuentro en la residencia de Einstein en Caputh (Berlín), 14 de julio de 1930",
    note=(
        "Albert Einstein y Rabindranath Tagore se reunieron en persona el 14 de julio de 1930 en Caputh, Alemania, "
        "manteniendo una conversación histórica sobre la ciencia, la verdad, la conciencia y la naturaleza de la realidad."
    ),
    status="draft",
)

fact_created = repo.create("facts", validate_fact(repo, fact_input))
fact_id = fact_created["id"]
print("Fact creado:", fact_id)

# 4. Verificar el hecho
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
print("Fact verificado exitosamente.")

# 5. Comprobar conexiones
print("\n--- Conexiones de Einstein ---")
print(json.dumps(connection_preview(repo, einstein_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Tagore ---")
print(json.dumps(connection_preview(repo, tagore_id), indent=2, ensure_ascii=False))
