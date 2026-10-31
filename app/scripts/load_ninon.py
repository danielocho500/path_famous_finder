import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

voltaire_id = "840028da-76cd-4d7a-a9d8-b1a9fa88939d"

# 1. Crear a Ninon de Lenclos
ninon_input = PersonInput(
    name="Ninon de Lenclos",
    aliases=[
        "Anne de Lenclos",
        "Ninon de l'Enclos",
    ],
    description=(
        "Escritora, filósofa epicúrea y mecenas francesa del siglo XVII. Dirigió uno de los salones literarios "
        "más célebres e influyentes de París, frecuentado por Molière, La Fontaine, Racine y el joven Voltaire, "
        "a quien impulsó en su vocación literaria legándole fondos en su testamento."
    ),
    country="FR",
    city_born="París",
    image_url="https://upload.wikimedia.org/wikipedia/commons/8/83/Ch%C3%A2teau_de_Bussy-Rabutin_-_Anne%2C_dite_Ninon_de_Lenclos_%28bgw19_0345%29.jpg",
    wikidata_id="Q237045",
    birth=HistoricalDate(year=1620, month=11, day=10, precision="day"),
    death=HistoricalDate(year=1705, month=10, day=17, precision="day"),
).model_dump(mode="json")

ninon = repo.create("people", ninon_input)
ninon_id = ninon["id"]
print("Creada Ninon de Lenclos con ID:", ninon_id)

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
        id=ninon_id,
        rn="Anne de Lenclos",
        bkf="Ninon de Lenclos",
        c="FR",
        img=ninon_input["image_url"],
        occ="Filósofa, escritora y mecenas de salón literario",
        desc=ninon_input["description"],
    )

# 2. Crear Fuente (Source)
source_input = SourceInput(
    title="Ninon de Lenclos and the Young Voltaire: The Legacy of 1704–1705",
    url="https://en.wikipedia.org/wiki/Ninon_de_l%27Enclos",
    publisher="Bibliothèque nationale de France / Voltaire Foundation (University of Oxford)",
    author="Voltaire Biographical Archives & Testament Records",
).model_dump(mode="json")

source = repo.create("sources", source_input)
source_id = source["id"]
print("Fuente creada:", source_id, source["title"])

# 3. Crear Hecho de encuentro (personal.met)
fact_input = FactInput(
    type_id="personal.met",
    subject_id=ninon_id,
    object_id=voltaire_id,
    source_id=source_id,
    source_locator="Encuentro en el salón de París (1704) y cláusula testamentaria de Ninon de Lenclos de 1705",
    note=(
        "Ninon de Lenclos conoció en persona en su salón de París al joven François-Marie Arouet (Voltaire, de 10 años), "
        "presentado por su padrino el abad de Châteauneuf en 1704. Fascinada por su brillantez precoz, le legó 2.000 libras "
        "en su testamento para que pudiera comprar libros, marcando el inicio de su carrera literaria."
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
print("\n--- Conexiones de Ninon de Lenclos ---")
print(json.dumps(connection_preview(repo, ninon_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Voltaire ---")
print(json.dumps(connection_preview(repo, voltaire_id), indent=2, ensure_ascii=False))
