import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

planck_id = "8ca83a4e-c00c-474f-a9f9-f68d7a57a7a1"

# 1. Crear a Hermann von Helmholtz
helmholtz_input = PersonInput(
    name="Hermann von Helmholtz",
    aliases=[
        "Hermann Ludwig Ferdinand von Helmholtz",
        "Hermann Helmholtz",
    ],
    description=(
        "Físico, médico y polímata prusiano. Formuló matemáticamente el principio de conservación de la energía, "
        "inventó el oftalmoscopio e hizo contribuciones monumentales a la electrodinámica, la acústica "
        "y la fisiología de los sentidos."
    ),
    country="DE",
    city_born="Potsdam",
    image_url="https://upload.wikimedia.org/wikipedia/commons/c/c7/Hermann_von_Helmholtz.jpg",
    wikidata_id="Q60024",
    birth=HistoricalDate(year=1821, month=8, day=31, precision="day"),
    death=HistoricalDate(year=1894, month=9, day=8, precision="day"),
).model_dump(mode="json")

helmholtz = repo.create("people", helmholtz_input)
helmholtz_id = helmholtz["id"]
print("Creado Hermann von Helmholtz con ID:", helmholtz_id)

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
        id=helmholtz_id,
        rn="Hermann Ludwig Ferdinand von Helmholtz",
        bkf="Hermann von Helmholtz",
        c="DE",
        img=helmholtz_input["image_url"],
        occ="Físico, fisiólogo y profesor universitario",
        desc=helmholtz_input["description"],
    )

# 2. Crear Fuente (Source)
source_input = SourceInput(
    title="Max Planck: The Making of a Theoretical Physicist (1858–1900)",
    url="https://en.wikipedia.org/wiki/Hermann_von_Helmholtz",
    publisher="University of Berlin Archives / Academic Press",
    author="J.L. Heilbron / Historical Archives",
).model_dump(mode="json")

source = repo.create("sources", source_input)
source_id = source["id"]
print("Fuente creada:", source_id, source["title"])

# 3. Crear Hecho de mentoría (professional.mentor_of)
fact_input = FactInput(
    type_id="professional.mentor_of",
    subject_id=helmholtz_id,
    object_id=planck_id,
    source_id=source_id,
    source_locator="Cátedra de física en la Universidad de Berlín (1877-1878) y dirección de estudios de Planck",
    note=(
        "Hermann von Helmholtz fue el profesor y mentor académico formativo de Max Planck en la Universidad de Berlín, "
        "inspirando su dedicación a la termodinámica teórica y apoyando su posterior carrera académica."
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
print("\n--- Conexiones de Helmholtz ---")
print(json.dumps(connection_preview(repo, helmholtz_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Planck ---")
print(json.dumps(connection_preview(repo, planck_id), indent=2, ensure_ascii=False))
