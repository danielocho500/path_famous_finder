import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

jefferson_id = "f1e96b6b-a29d-44c6-ac10-6cb1e2298adc"

# 1. Crear a Luis XVI de Francia
louis_input = PersonInput(
    name="Luis XVI de Francia",
    aliases=[
        "Louis XVI",
        "Louis-Auguste de France",
        "Rey Luis XVI",
    ],
    description=(
        "Rey de Francia y de Navarra (1774–1792). Su apoyo financiero y militar a los colonos norteamericanos "
        "fue decisivo para la victoria en la Guerra de Independencia de los Estados Unidos. Último monarca absoluto "
        "del Antiguo Régimen antes de la Revolución francesa."
    ),
    country="FR",
    city_born="Versalles",
    image_url="https://upload.wikimedia.org/wikipedia/commons/c/ce/Antoine-Fran%C3%A7ois_Callet_-_Louis_XVI%2C_roi_de_France_et_de_Navarre_%281754-1793%29%2C_rev%C3%AAtu_du_grand_costume_royal_en_1779_-_Google_Art_Project.jpg",
    wikidata_id="Q7732",
    birth=HistoricalDate(year=1754, month=8, day=23, precision="day"),
    death=HistoricalDate(year=1793, month=1, day=21, precision="day"),
).model_dump(mode="json")

louis = repo.create("people", louis_input)
louis_id = louis["id"]
print("Creado Luis XVI con ID:", louis_id)

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
        id=louis_id,
        rn="Louis-Auguste de France",
        bkf="Luis XVI de Francia",
        c="FR",
        img=louis_input["image_url"],
        occ="Rey de Francia y de Navarra",
        desc=louis_input["description"],
    )

# 2. Crear Fuente (Source)
source_input = SourceInput(
    title="Thomas Jefferson in France: Diplomatic Mission to the Court of Louis XVI (1784–1789)",
    url="https://en.wikipedia.org/wiki/Louis_XVI",
    publisher="U.S. Department of State / Office of the Historian / Library of Congress",
    author="Jefferson Diplomatic Papers / French Foreign Ministry Archives",
).model_dump(mode="json")

source = repo.create("sources", source_input)
source_id = source["id"]
print("Fuente creada:", source_id, source["title"])

# 3. Crear Hecho de encuentro diplomático (personal.met)
fact_input = FactInput(
    type_id="personal.met",
    subject_id=jefferson_id,
    object_id=louis_id,
    source_id=source_id,
    source_locator="Audiencia formal en Versalles y presentación de credenciales diplomáticas, 17 de mayo de 1785",
    note=(
        "Thomas Jefferson fue recibido en audiencia oficial en el Palacio de Versalles por el rey Luis XVI de Francia "
        "en mayo de 1785 como ministro plenipotenciario de los Estados Unidos, manteniendo relaciones diplomáticas directas "
        "en la corte francesa hasta 1789."
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
print("\n--- Conexiones de Jefferson ---")
print(json.dumps(connection_preview(repo, jefferson_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Luis XVI ---")
print(json.dumps(connection_preview(repo, louis_id), indent=2, ensure_ascii=False))
