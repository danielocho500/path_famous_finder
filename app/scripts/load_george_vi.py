import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

isabel_id = "07b365cc-70b1-4622-9375-1f6671eb730e"

# 1. Crear al Rey Jorge VI
george_input = PersonInput(
    name="Jorge VI del Reino Unido",
    aliases=[
        "George VI",
        "Albert Frederick Arthur George",
        "Rey Jorge VI",
    ],
    description=(
        "Rey del Reino Unido y los dominios de la Mancomunidad Británica de Naciones desde 1936 hasta su muerte en 1952. "
        "Último emperador de la India y primer jefe de la Mancomunidad."
    ),
    country="GB",
    city_born="Sandringham",
    image_url="https://upload.wikimedia.org/wikipedia/commons/e/e0/King_George_VI_LOC_matpc.14736_A_%28cropped%29.jpg",
    wikidata_id="Q280856",
    birth=HistoricalDate(year=1895, month=12, day=14, precision="day"),
    death=HistoricalDate(year=1952, month=2, day=6, precision="day"),
).model_dump(mode="json")

george = repo.create("people", george_input)
george_id = george["id"]
print("Creado Rey Jorge VI con ID:", george_id)

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
        id=george_id,
        rn="Albert Frederick Arthur George",
        bkf="Jorge VI del Reino Unido",
        c="GB",
        img=george_input["image_url"],
        occ="Monarca del Reino Unido",
        desc=george_input["description"],
    )

# 2. Crear Fuente
source_input = SourceInput(
    title="George VI: The Official Biography and Royal Lineage",
    url="https://en.wikipedia.org/wiki/George_VI",
    publisher="The Royal Household / Official Biographies",
    author="John Wheeler-Bennett / Royal Archives",
).model_dump(mode="json")

source = repo.create("sources", source_input)
source_id = source["id"]
print("Fuente creada:", source_id, source["title"])

# 3. Crear Hecho de parentesco (family.parent_of)
fact_input = FactInput(
    type_id="family.parent_of",
    subject_id=george_id,
    object_id=isabel_id,
    source_id=source_id,
    source_locator="Capítulo biográfico sobre la familia real británica y nacimiento de la princesa Isabel",
    note="El rey Jorge VI es el padre biológico de la reina Isabel II del Reino Unido",
    status="draft",
)

fact_created = repo.create("facts", validate_fact(repo, fact_input))
fact_id = fact_created["id"]
print("Fact de parentesco creado:", fact_id)

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
print("\n--- Conexiones de Jorge VI ---")
print(json.dumps(connection_preview(repo, george_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Isabel II ---")
print(json.dumps(connection_preview(repo, isabel_id), indent=2, ensure_ascii=False))
