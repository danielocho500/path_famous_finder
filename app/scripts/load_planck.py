import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

einstein_id = "1c977060-8781-4ce9-86d8-4f6bcaeefb01"

# 1. Crear a Max Planck
planck_input = PersonInput(
    name="Max Planck",
    aliases=[
        "Max Karl Ernst Ludwig Planck",
        "Max Planck",
    ],
    description=(
        "Físico teórico alemán, considerado el fundador de la teoría cuántica y una de las figuras más "
        "relevantes de la física moderna. Descubrió los cuantos de energía (constante de Planck) y fue "
        "galardonado con el Premio Nobel de Física en 1918."
    ),
    country="DE",
    city_born="Kiel",
    image_url="https://upload.wikimedia.org/wikipedia/commons/f/fc/Bundesarchiv_Bild_183-R0116-504%2C_Max_Planck.jpg",
    wikidata_id="Q9021",
    birth=HistoricalDate(year=1858, month=4, day=23, precision="day"),
    death=HistoricalDate(year=1947, month=10, day=4, precision="day"),
).model_dump(mode="json")

planck = repo.create("people", planck_input)
planck_id = planck["id"]
print("Creado Max Planck con ID:", planck_id)

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
        id=planck_id,
        rn="Max Karl Ernst Ludwig Planck",
        bkf="Max Planck",
        c="DE",
        img=planck_input["image_url"],
        occ="Físico teórico y pionero cuántico (Premio Nobel de Física)",
        desc=planck_input["description"],
    )

# 2. Crear Fuente (Source)
source_input = SourceInput(
    title="Max Planck and Albert Einstein: The Birth of Quantum Physics and Relativity",
    url="https://en.wikipedia.org/wiki/Max_Planck",
    publisher="Prussian Academy of Sciences / Nobel Foundation",
    author="Nobel Historical Archives",
).model_dump(mode="json")

source = repo.create("sources", source_input)
source_id = source["id"]
print("Fuente creada:", source_id, source["title"])

# 3. Crear Hecho de mentoría (professional.mentor_of)
fact_input = FactInput(
    type_id="professional.mentor_of",
    subject_id=planck_id,
    object_id=einstein_id,
    source_id=source_id,
    source_locator="Publicación de los artículos de la relatividad especial en 1905 y nombramiento en Berlín en 1913",
    note=(
        "Max Planck fue el mentor institucional y descubridor académico de Albert Einstein, publicando sus artículos de "
        "la relatividad especial en Annalen der Physik y reclutándolo formalmente para la Academia Prusiana de las Ciencias en 1913."
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
print("\n--- Conexiones de Max Planck ---")
print(json.dumps(connection_preview(repo, planck_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Albert Einstein ---")
print(json.dumps(connection_preview(repo, einstein_id), indent=2, ensure_ascii=False))
