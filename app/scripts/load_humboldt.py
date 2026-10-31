import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

helmholtz_id = "5283d925-44fb-417a-b67b-4f76f45bec04"

# 1. Crear a Alexander von Humboldt
humboldt_input = PersonInput(
    name="Alexander von Humboldt",
    aliases=[
        "Friedrich Wilhelm Heinrich Alexander von Humboldt",
        "Barón de Humboldt",
    ],
    description=(
        "Polímata, geógrafo, naturalista y explorador prusiano. Considerado el padre de la geografía "
        "moderna universal y pionero de la biogeografía, la climatología y el pensamiento ecológico. "
        "Célebre por su monumental expedición científica por América (1799–1804)."
    ),
    country="DE",
    city_born="Berlín",
    image_url="https://upload.wikimedia.org/wikipedia/commons/3/36/Stieler%2C_Joseph_Karl_-_Alexander_von_Humboldt_-_1843.jpg",
    wikidata_id="Q43880",
    birth=HistoricalDate(year=1769, month=9, day=14, precision="day"),
    death=HistoricalDate(year=1859, month=5, day=6, precision="day"),
).model_dump(mode="json")

humboldt = repo.create("people", humboldt_input)
humboldt_id = humboldt["id"]
print("Creado Alexander von Humboldt con ID:", humboldt_id)

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
        id=humboldt_id,
        rn="Friedrich Wilhelm Heinrich Alexander von Humboldt",
        bkf="Alexander von Humboldt",
        c="DE",
        img=humboldt_input["image_url"],
        occ="Naturalista, geógrafo y explorador",
        desc=humboldt_input["description"],
    )

# 2. Crear Fuente (Source)
source_input = SourceInput(
    title="Alexander von Humboldt and the Prussian Academy: Patronage of Young Helmholtz",
    url="https://en.wikipedia.org/wiki/Alexander_von_Humboldt",
    publisher="Royal Prussian Academy of Sciences / Humboldt Heritage",
    author="Historical Archive of Prussian Sciences",
).model_dump(mode="json")

source = repo.create("sources", source_input)
source_id = source["id"]
print("Fuente creada:", source_id, source["title"])

# 3. Crear Hecho de mentoría/mecenazgo (professional.mentor_of)
fact_input = FactInput(
    type_id="professional.mentor_of",
    subject_id=humboldt_id,
    object_id=helmholtz_id,
    source_id=source_id,
    source_locator="Mecenazgo científico en Berlín tras el tratado de conservación de energía (1847-1849)",
    note=(
        "Alexander von Humboldt apadrinó y fue mentor del joven Hermann von Helmholtz en Berlín, quedando impresionado "
        "por su tratado sobre la conservación de la fuerza (1847), gestionando su liberación del servicio militar "
        "y asegurando su primera cátedra universitaria de fisiología en Königsberg."
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

print("\n--- Conexiones de Helmholtz ---")
print(json.dumps(connection_preview(repo, helmholtz_id), indent=2, ensure_ascii=False))
