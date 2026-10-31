import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

gandhi_id = "e00314dc-b6bc-48da-a602-52f72e0386e2"

# 1. Crear a Rabindranath Tagore
tagore_input = PersonInput(
    name="Rabindranath Tagore",
    aliases=[
        "Rabindranath Thakur",
        "Gurudev",
        "Kabiguru",
    ],
    description=(
        "Poeta, filósofo, dramaturgo, compositor y pintor bengalí. Primer laureado no europeo "
        "en recibir el Premio Nobel de Literatura (1913). Figura cumbre del Renacimiento bengalí "
        "y compositor de los himnos nacionales de la India y Bangladés."
    ),
    country="IN",
    city_born="Calcuta",
    image_url="https://upload.wikimedia.org/wikipedia/commons/6/62/1926_Rabindrath_Tagore.jpg",
    wikidata_id="Q7241",
    birth=HistoricalDate(year=1861, month=5, day=7, precision="day"),
    death=HistoricalDate(year=1941, month=8, day=7, precision="day"),
).model_dump(mode="json")

tagore = repo.create("people", tagore_input)
tagore_id = tagore["id"]
print("Creado Rabindranath Tagore con ID:", tagore_id)

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
        id=tagore_id,
        rn="Rabindranath Thakur",
        bkf="Rabindranath Tagore",
        c="IN",
        img=tagore_input["image_url"],
        occ="Poeta, filósofo y compositor (Premio Nobel de Literatura)",
        desc=tagore_input["description"],
    )

# 2. Crear Fuente (Source)
source_input = SourceInput(
    title="The Mahatma and the Poet: Letters and Debates between Gandhi and Tagore (1915–1941)",
    url="https://en.wikipedia.org/wiki/Rabindranath_Tagore",
    publisher="Visva-Bharati / National Book Trust",
    author="Sabyasachi Bhattacharya / Visva-Bharati Archives",
).model_dump(mode="json")

source = repo.create("sources", source_input)
source_id = source["id"]
print("Fuente creada:", source_id, source["title"])

# 3. Crear Hecho de encuentro (personal.met)
fact_input = FactInput(
    type_id="personal.met",
    subject_id=tagore_id,
    object_id=gandhi_id,
    source_id=source_id,
    source_locator="Encuentro inaugural en el ashram de Santiniketan, 6 de marzo de 1915",
    note=(
        "Rabindranath Tagore y Mahatma Gandhi se conocieron en persona en Santiniketan el 6 de marzo de 1915, "
        "consolidando una profunda amistad y debate intelectual donde Tagore confirió el epíteto 'Mahatma' "
        "y Gandhi se refería a él como 'Gurudev'."
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
print("\n--- Conexiones de Tagore ---")
print(json.dumps(connection_preview(repo, tagore_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Gandhi ---")
print(json.dumps(connection_preview(repo, gandhi_id), indent=2, ensure_ascii=False))
