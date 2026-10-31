import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

placido_id = "0f447424-1419-474b-b2b1-955f6680c8eb"

# 1. Crear a la Reina Isabel II
isabel_input = PersonInput(
    name="Isabel II del Reino Unido",
    aliases=[
        "Elizabeth II",
        "Elizabeth Alexandra Mary Windsor",
        "Reina Isabel II",
    ],
    description=(
        "Reina del Reino Unido y soberana de los otros reinos de la Mancomunidad de Naciones (1952-2022). "
        "Su reinado de 70 años y 214 días es el más extenso documentado de cualquier monarca británico."
    ),
    country="GB",
    city_born="Londres",
    image_url="https://upload.wikimedia.org/wikipedia/commons/1/11/Queen_Elizabeth_II_official_portrait_for_1959_tour_%28retouched%29_%28cropped%29_%283-to-4_aspect_ratio%29.jpg",
    wikidata_id="Q9682",
    birth=HistoricalDate(year=1926, month=4, day=21, precision="day"),
    death=HistoricalDate(year=2022, month=9, day=8, precision="day"),
).model_dump(mode="json")

isabel = repo.create("people", isabel_input)
isabel_id = isabel["id"]
print("Creada Reina Isabel II con ID:", isabel_id)

# Ajustar propiedades adicionales de compatibilidad
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
        id=isabel_id,
        rn="Elizabeth Alexandra Mary Windsor",
        bkf="Isabel II del Reino Unido",
        c="GB",
        img=isabel_input["image_url"],
        occ="Monarca del Reino Unido",
        desc=isabel_input["description"],
    )

# 2. Crear Fuente (Source)
source_input = SourceInput(
    title="Honors and Royal Galas of Plácido Domingo - Order of the British Empire",
    url="https://en.wikipedia.org/wiki/Pl%C3%A1cido_Domingo",
    publisher="Royal Opera House / Official Records",
    author="Biographical & Honours Archive",
).model_dump(mode="json")

source = repo.create("sources", source_input)
source_id = source["id"]
print("Fuente creada:", source_id, source["title"])

# 3. Crear Hecho directo de encuentro (personal.met)
fact_input = FactInput(
    type_id="personal.met",
    subject_id=placido_id,
    object_id=isabel_id,
    source_id=source_id,
    source_locator="Sección 'Honours' y actuaciones de gala ante la monarca en la Royal Opera House de Londres",
    note=(
        "Plácido Domingo y la Reina Isabel II coincidieron en persona en recepciones de la Royal Opera House "
        "y en la concesión de su condecoración como Caballero Comendador de la Orden del Imperio Británico (KBE)"
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

# 5. Comprobar conexiones mutuas
print("\n--- Conexiones de Plácido Domingo ---")
print(json.dumps(connection_preview(repo, placido_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de la Reina Isabel II ---")
print(json.dumps(connection_preview(repo, isabel_id), indent=2, ensure_ascii=False))
