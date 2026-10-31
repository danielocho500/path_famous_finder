import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

george_v_id = "cbb5fef4-11b4-46fc-92d6-0827b5558575"

# 1. Crear a Mahatma Gandhi
gandhi_input = PersonInput(
    name="Mahatma Gandhi",
    aliases=[
        "Mohandas Karamchand Gandhi",
        "Bapu",
        "Gandhiji",
    ],
    description=(
        "Abogado, pensador y líder espiritual y político del nacionalismo indio. "
        "Condujo a la India hacia su independencia del dominio británico liderando campañas masivas "
        "de desobediencia civil y resistencia pacífica (satyagraha)."
    ),
    country="IN",
    city_born="Porbandar",
    image_url="https://upload.wikimedia.org/wikipedia/commons/7/7a/Mahatma-Gandhi%2C_studio%2C_1931.jpg",
    wikidata_id="Q1001",
    birth=HistoricalDate(year=1869, month=10, day=2, precision="day"),
    death=HistoricalDate(year=1948, month=1, day=30, precision="day"),
).model_dump(mode="json")

gandhi = repo.create("people", gandhi_input)
gandhi_id = gandhi["id"]
print("Creado Mahatma Gandhi con ID:", gandhi_id)

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
        id=gandhi_id,
        rn="Mohandas Karamchand Gandhi",
        bkf="Mahatma Gandhi",
        c="IN",
        img=gandhi_input["image_url"],
        occ="Líder pacifista, abogado y filósofo político",
        desc=gandhi_input["description"],
    )

# 2. Crear Fuente (Source)
source_input = SourceInput(
    title="Second Round Table Conference and Royal Reception at Buckingham Palace (1931)",
    url="https://en.wikipedia.org/wiki/Round_Table_Conferences_(India)",
    publisher="British National Archives / Official Conference Records",
    author="Round Table Conference Proceedings",
).model_dump(mode="json")

source = repo.create("sources", source_input)
source_id = source["id"]
print("Fuente creada:", source_id, source["title"])

# 3. Crear Hecho de encuentro (personal.met)
fact_input = FactInput(
    type_id="personal.met",
    subject_id=gandhi_id,
    object_id=george_v_id,
    source_id=source_id,
    source_locator="Recepción real para delegados en el Palacio de Buckingham, 5 de noviembre de 1931",
    note=(
        "Mahatma Gandhi y el rey Jorge V se reunieron en persona y conversaron durante la recepción oficial "
        "en el Palacio de Buckingham en el marco de la Segunda Conferencia de la Mesa Redonda."
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
print("\n--- Conexiones de Gandhi ---")
print(json.dumps(connection_preview(repo, gandhi_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Jorge V ---")
print(json.dumps(connection_preview(repo, george_v_id), indent=2, ensure_ascii=False))
