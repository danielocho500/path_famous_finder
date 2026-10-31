import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

george_vi_id = "06b08c76-df2d-49e8-951f-1fa7b85e804d"

# 1. Crear al Rey Jorge V
george_v_input = PersonInput(
    name="Jorge V del Reino Unido",
    aliases=[
        "George V",
        "George Frederick Ernest Albert",
        "Rey Jorge V",
    ],
    description=(
        "Rey del Reino Unido y los dominios británicos de ultramar, y emperador de la India, desde 1910 hasta su muerte en 1936. "
        "Lideró a la nación durante la Primera Guerra Mundial y renombró la dinastía real como Casa de Windsor en 1917."
    ),
    country="GB",
    city_born="Londres",
    image_url="https://upload.wikimedia.org/wikipedia/commons/c/c9/King_George_1923_LCCN2014715558_%28cropped%29.jpg",
    wikidata_id="Q269412",
    birth=HistoricalDate(year=1865, month=6, day=3, precision="day"),
    death=HistoricalDate(year=1936, month=1, day=20, precision="day"),
).model_dump(mode="json")

george_v = repo.create("people", george_v_input)
george_v_id = george_v["id"]
print("Creado Rey Jorge V con ID:", george_v_id)

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
        id=george_v_id,
        rn="George Frederick Ernest Albert",
        bkf="Jorge V del Reino Unido",
        c="GB",
        img=george_v_input["image_url"],
        occ="Monarca del Reino Unido y emperador de la India",
        desc=george_v_input["description"],
    )

# 2. Crear Fuente
source_input = SourceInput(
    title="King George V: His Life and Reign - Official Royal Biography",
    url="https://en.wikipedia.org/wiki/George_V",
    publisher="The Royal Household / Constable & Co",
    author="Harold Nicolson / Royal Archives",
).model_dump(mode="json")

source = repo.create("sources", source_input)
source_id = source["id"]
print("Fuente creada:", source_id, source["title"])

# 3. Crear Hecho de parentesco (family.parent_of)
fact_input = FactInput(
    type_id="family.parent_of",
    subject_id=george_v_id,
    object_id=george_vi_id,
    source_id=source_id,
    source_locator="Capítulo sobre el matrimonio con María de Teck y el nacimiento de su segundo hijo Alberto (Jorge VI)",
    note="El rey Jorge V es el padre biológico del rey Jorge VI del Reino Unido",
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
print("\n--- Conexiones de Jorge V ---")
print(json.dumps(connection_preview(repo, george_v_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Jorge VI ---")
print(json.dumps(connection_preview(repo, george_vi_id), indent=2, ensure_ascii=False))
