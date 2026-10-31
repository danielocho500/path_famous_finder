import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

humboldt_id = "f6a81343-0f41-4314-9376-56d3e6631b77"

# 1. Crear a Thomas Jefferson
jefferson_input = PersonInput(
    name="Thomas Jefferson",
    aliases=[
        "Thomas Jefferson",
    ],
    description=(
        "Político, filósofo de la Ilustración, arquitecto y Padre Fundador de los Estados Unidos. "
        "Autor principal de la Declaración de Independencia (1776) y tercer presidente de los Estados Unidos (1801–1809). "
        "Fundador de la Universidad de Virginia."
    ),
    country="US",
    city_born="Shadwell",
    image_url="https://upload.wikimedia.org/wikipedia/commons/0/07/Official_Presidential_portrait_of_Thomas_Jefferson_%28by_Rembrandt_Peale%2C_1800%29.jpg",
    wikidata_id="Q11812",
    birth=HistoricalDate(year=1743, month=4, day=13, precision="day"),
    death=HistoricalDate(year=1826, month=7, day=4, precision="day"),
).model_dump(mode="json")

jefferson = repo.create("people", jefferson_input)
jefferson_id = jefferson["id"]
print("Creado Thomas Jefferson con ID:", jefferson_id)

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
        id=jefferson_id,
        rn="Thomas Jefferson",
        bkf="Thomas Jefferson",
        c="US",
        img=jefferson_input["image_url"],
        occ="Tercer presidente de los Estados Unidos y filósofo",
        desc=jefferson_input["description"],
    )

# 2. Crear Fuente (Source)
source_input = SourceInput(
    title="Alexander von Humboldt and Thomas Jefferson: A Meeting of Minds in the White House (1804)",
    url="https://en.wikipedia.org/wiki/Thomas_Jefferson",
    publisher="Library of Congress / National Archives",
    author="Monticello Historical Studies / Library of Congress",
).model_dump(mode="json")

source = repo.create("sources", source_input)
source_id = source["id"]
print("Fuente creada:", source_id, source["title"])

# 3. Crear Hecho de encuentro (personal.met)
fact_input = FactInput(
    type_id="personal.met",
    subject_id=humboldt_id,
    object_id=jefferson_id,
    source_id=source_id,
    source_locator="Reuniones en la Casa Blanca (Washington D.C.), 1 a 13 de junio de 1804",
    note=(
        "Alexander von Humboldt y el presidente Thomas Jefferson se reunieron personalmente en la Casa Blanca "
        "en junio de 1804 tras la expedición americana de Humboldt, intercambiando mapas, estadísticas e ideas "
        "sobre ciencia, la Ilustración y la geografía del continente."
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
print("\n--- Conexiones de Humboldt ---")
print(json.dumps(connection_preview(repo, humboldt_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Jefferson ---")
print(json.dumps(connection_preview(repo, jefferson_id), indent=2, ensure_ascii=False))
