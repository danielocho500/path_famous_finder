import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

ninon_id = "7dc56c04-8a9c-4a63-851c-533cee08b55e"

# 1. Crear a Cristina de Suecia
christina_input = PersonInput(
    name="Cristina de Suecia",
    aliases=[
        "Kristina",
        "Reina Cristina de Suecia",
        "Christina of Sweden",
    ],
    description=(
        "Reina de Suecia (1632–1654), recordada como una de las soberanas más cultas e ilustradas del siglo XVII. "
        "Apasionada por la filosofía, las ciencias y las artes, abdicó voluntariamente a la corona para residir en Roma. "
        "Mecenas de los mayores intelectuales de Europa y protectora de la libertad de pensamiento."
    ),
    country="SE",
    city_born="Estocolmo",
    image_url="https://upload.wikimedia.org/wikipedia/commons/2/2e/Swedish_queen_Drottning_Kristina_portrait_by_S%C3%A9bastien_Bourdon_stor.jpg",
    wikidata_id="Q52937",
    birth=HistoricalDate(year=1626, month=12, day=18, precision="day"),
    death=HistoricalDate(year=1689, month=4, day=19, precision="day"),
).model_dump(mode="json")

christina = repo.create("people", christina_input)
christina_id = christina["id"]
print("Creada Reina Cristina de Suecia con ID:", christina_id)

# Ajustar compatibilidad
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
        id=christina_id,
        rn="Kristina Augusta de Suecia",
        bkf="Cristina de Suecia",
        c="SE",
        img=christina_input["image_url"],
        occ="Reina de Suecia y mecenas cultural",
        desc=christina_input["description"],
    )

# 2. Conectar Cristina de Suecia con Ninon de Lenclos
source_cn = repo.create(
    "sources",
    SourceInput(
        title="Queen Christina of Sweden and Ninon de Lenclos: The 1656 Paris Meeting",
        url="https://en.wikipedia.org/wiki/Christina,_Queen_of_Sweden",
        publisher="Royal Swedish Academy of Letters / National Historical Archives",
        author="Historical Accounts of Christina's French Embassy / Madame de Motteville Memoirs",
    ).model_dump(mode="json"),
)
print("Fuente Cristina-Ninon creada:", source_cn["id"])

fact_cn = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=christina_id,
            object_id=ninon_id,
            source_id=source_cn["id"],
            source_locator="Audiencia privada en Picpus/París, septiembre de 1656",
            note=(
                "En septiembre de 1656, durante su viaje oficial por Francia tras abdicar al trono, la reina Cristina de Suecia "
                "solicitó una audiencia privada con Ninon de Lenclos en las afueras de París, pasando horas debatiendo "
                "a solas sobre filosofía, independencia moral y pensamiento libre."
            ),
            status="draft",
        ),
    ),
)
data_cn = {
    k: v
    for k, v in repo.get("facts", fact_cn["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_cn["status"] = "verified"
repo.update(
    "facts",
    fact_cn["id"],
    fact_cn["revision"],
    validate_fact(repo, data_cn),
    "verify",
)
print("Hecho Cristina <-> Ninon verificado.")

# 3. Crear a René Descartes
descartes_input = PersonInput(
    name="René Descartes",
    aliases=[
        "René Descartes",
        "Renatus Cartesius",
    ],
    description=(
        "Filósofo, matemático y físico francés, considerado el padre de la filosofía moderna y del racionalismo occidental "
        "('Cogito, ergo sum'). Creador de la geometría analítica y figura cumbre de la Revolución científica. "
        "Fue llamado a Estocolmo en 1649 como tutor filosófico de la reina Cristina de Suecia."
    ),
    country="FR",
    city_born="Descartes",
    image_url="https://upload.wikimedia.org/wikipedia/commons/7/73/Frans_Hals_-_Portret_van_Ren%C3%A9_Descartes.jpg",
    wikidata_id="Q9191",
    birth=HistoricalDate(year=1596, month=3, day=31, precision="day"),
    death=HistoricalDate(year=1650, month=2, day=11, precision="day"),
).model_dump(mode="json")

descartes = repo.create("people", descartes_input)
descartes_id = descartes["id"]
print("Creado René Descartes con ID:", descartes_id)

# Ajustar compatibilidad
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
        id=descartes_id,
        rn="René Descartes",
        bkf="René Descartes",
        c="FR",
        img=descartes_input["image_url"],
        occ="Filósofo y matemático (Padre de la filosofía moderna)",
        desc=descartes_input["description"],
    )

# 4. Conectar Descartes con Cristina de Suecia (mentor / tutor)
source_dc = repo.create(
    "sources",
    SourceInput(
        title="Descartes in Stockholm: Tutoring Queen Christina of Sweden (1649–1650)",
        url="https://en.wikipedia.org/wiki/Ren%C3%A9_Descartes",
        publisher="Bibliothèque Nationale de France / Swedish Royal Archives",
        author="Adrien Baillet: La Vie de Monsieur Des-Cartes (1691)",
    ).model_dump(mode="json"),
)
print("Fuente Descartes-Cristina creada:", source_dc["id"])

fact_dc = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="professional.mentor_of",
            subject_id=descartes_id,
            object_id=christina_id,
            source_id=source_dc["id"],
            source_locator="Tutoría filosófica en el Palacio Real de Tre Kronor (Estocolmo), octubre 1649 a febrero 1650",
            note=(
                "René Descartes viajó a Estocolmo en 1649 invitado formalmente por la reina Cristina de Suecia para desempeñarse "
                "como su tutor de filosofía y asesor intelectual en la corte real, impartiendo lecciones matutinas hasta su muerte en 1650."
            ),
            status="draft",
        ),
    ),
)
data_dc = {
    k: v
    for k, v in repo.get("facts", fact_dc["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_dc["status"] = "verified"
repo.update(
    "facts",
    fact_dc["id"],
    fact_dc["revision"],
    validate_fact(repo, data_dc),
    "verify",
)
print("Hecho Descartes <-> Cristina verificado.")

# 5. Comprobar conexiones
print("\n--- Conexiones de Cristina de Suecia ---")
print(json.dumps(connection_preview(repo, christina_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de René Descartes ---")
print(json.dumps(connection_preview(repo, descartes_id), indent=2, ensure_ascii=False))
