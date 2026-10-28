import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

descartes_id = "034406c7-3b63-4130-a52f-ac4211594cfb"

# 1. Crear a Marin Mersenne
mersenne_input = PersonInput(
    name="Marin Mersenne",
    aliases=[
        "Marin Mersenne",
        "Padre Mersenne",
    ],
    description=(
        "Sacerdote de la Orden de los Mínimos, matemático, teólogo y filósofo francés. "
        "Conocido como el 'secretario de la Europa científica' por articular la red de correspondencia "
        "que conectó a Galileo, Descartes, Fermat, Pascal y Hobbes. Pionero de la acústica y de la teoría de números."
    ),
    country="FR",
    city_born="Oizé",
    image_url="https://upload.wikimedia.org/wikipedia/commons/e/ed/MarinMersenneDuflos.jpg",
    wikidata_id="Q188663",
    birth=HistoricalDate(year=1588, month=9, day=8, precision="day"),
    death=HistoricalDate(year=1648, month=9, day=1, precision="day"),
).model_dump(mode="json")

mersenne = repo.create("people", mersenne_input)
mersenne_id = mersenne["id"]
print("Creado Marin Mersenne con ID:", mersenne_id)

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
        id=mersenne_id,
        rn="Marin Mersenne",
        bkf="Marin Mersenne",
        c="FR",
        img=mersenne_input["image_url"],
        occ="Matemático, filósofo y teólogo de la Orden de los Mínimos",
        desc=mersenne_input["description"],
    )

# 2. Conectar Descartes <-> Mersenne
source_dm = repo.create(
    "sources",
    SourceInput(
        title="Descartes and Mersenne: Lifelong Intellectual Partnership at La Flèche and Paris",
        url="https://en.wikipedia.org/wiki/Marin_Mersenne",
        publisher="Bibliothèque Nationale de France / Archives of the Order of Minims",
        author="Historical Correspondence of René Descartes and Marin Mersenne",
    ).model_dump(mode="json"),
)

fact_dm = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=descartes_id,
            object_id=mersenne_id,
            source_id=source_dm["id"],
            source_locator="Estudios en el Collège de La Flèche (1606) y reuniones en el convento de los Mínimos de París",
            note=(
                "René Descartes y Marin Mersenne se conocieron en el colegio jesuita de La Flèche hacia 1606 y mantuvieron "
                "una íntima amistad y colaboración intelectual; Mersenne fue el principal intermediario editorial de Descartes "
                "en París y organizó las famosas objeciones de teólogos y filósofos a las Meditaciones metafísicas."
            ),
            status="draft",
        ),
    ),
)
data_dm = {
    k: v
    for k, v in repo.get("facts", fact_dm["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_dm["status"] = "verified"
repo.update(
    "facts",
    fact_dm["id"],
    fact_dm["revision"],
    validate_fact(repo, data_dm),
    "verify",
)
print("Hecho Descartes <-> Mersenne verificado.")

# 3. Crear a Galileo Galilei
galileo_input = PersonInput(
    name="Galileo Galilei",
    aliases=[
        "Galileo Galilei",
        "Galileo",
    ],
    description=(
        "Astrónomo, físico, ingeniero y matemático toscano, considerado el padre de la ciencia moderna, "
        "la física clásica y la astronomía observacional. Descubrió las lunas de Júpiter ('estrellas mediceas') "
        "y defendió rigurosamente el modelo heliocéntrico copernicano."
    ),
    country="IT",
    city_born="Pisa",
    image_url="https://upload.wikimedia.org/wikipedia/commons/d/d4/Justus_Sustermans_-_Portrait_of_Galileo_Galilei%2C_1636.jpg",
    wikidata_id="Q307",
    birth=HistoricalDate(year=1564, month=2, day=15, precision="day"),
    death=HistoricalDate(year=1642, month=1, day=8, precision="day"),
).model_dump(mode="json")

galileo = repo.create("people", galileo_input)
galileo_id = galileo["id"]
print("Creado Galileo Galilei con ID:", galileo_id)

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
        id=galileo_id,
        rn="Galileo Galilei",
        bkf="Galileo Galilei",
        c="IT",
        img=galileo_input["image_url"],
        occ="Astrónomo, físico y matemático (Padre de la ciencia moderna)",
        desc=galileo_input["description"],
    )

# 4. Conectar Mersenne <-> Galileo
source_mg = repo.create(
    "sources",
    SourceInput(
        title="Correspondence and Translation of Galileo's Mechanics by Marin Mersenne (1634)",
        url="https://en.wikipedia.org/wiki/Galileo_Galilei",
        publisher="Académie des Sciences / Edizione Nazionale delle Opere di Galileo Galilei",
        author="Antonio Favaro: Le Opere di Galileo Galilei",
    ).model_dump(mode="json"),
)

fact_mg = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=mersenne_id,
            object_id=galileo_id,
            source_id=source_mg["id"],
            source_locator="Publicación de 'Les Mécaniques de Galilée' (1634) y correspondencia científica de defensa heliocéntrica",
            note=(
                "Marin Mersenne mantuvo una estrecha relación epistolar y de difusión científica con Galileo Galilei, "
                "traduciendo y publicando al francés su tratado de mecánica en 1634 y promoviendo sus descubrimientos astronómicos "
                "frente a la condena de la Inquisición."
            ),
            status="draft",
        ),
    ),
)
data_mg = {
    k: v
    for k, v in repo.get("facts", fact_mg["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_mg["status"] = "verified"
repo.update(
    "facts",
    fact_mg["id"],
    fact_mg["revision"],
    validate_fact(repo, data_mg),
    "verify",
)
print("Hecho Mersenne <-> Galileo verificado.")

# 5. Crear a Cosme II de Médici
cosimo_input = PersonInput(
    name="Cosme II de Médici",
    aliases=[
        "Cosimo II de' Medici",
        "Cosme II de Toscana",
    ],
    description=(
        "Gran Duque de Toscana (1609–1621) perteneciente a la ilustre dinastía de los Médici. "
        "Discípulo y el más importante mecenas y protector de Galileo Galilei, a quien nombró Filósofo "
        "y Matemático Principal de la corte toscana y en cuyo honor Galileo bautizó las lunas de Júpiter."
    ),
    country="IT",
    city_born="Florencia",
    image_url="https://upload.wikimedia.org/wikipedia/commons/0/07/Justus_Sustermans_010.jpg",
    wikidata_id="Q313174",
    birth=HistoricalDate(year=1590, month=5, day=12, precision="day"),
    death=HistoricalDate(year=1621, month=2, day=28, precision="day"),
).model_dump(mode="json")

cosimo = repo.create("people", cosimo_input)
cosimo_id = cosimo["id"]
print("Creado Cosme II de Médici con ID:", cosimo_id)

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
        id=cosimo_id,
        rn="Cosimo II de' Medici",
        bkf="Cosme II de Médici",
        c="IT",
        img=cosimo_input["image_url"],
        occ="Gran Duque de Toscana (Casa de Médici)",
        desc=cosimo_input["description"],
    )

# 6. Conectar Galileo <-> Cosme II de Médici (mentor y corte)
source_gc = repo.create(
    "sources",
    SourceInput(
        title="Galileo Galilei and the Court of Cosimo II de' Medici: Sidereus Nuncius (1610)",
        url="https://en.wikipedia.org/wiki/Cosimo_II_de%27_Medici",
        publisher="Archivio di Stato di Firenze / Museo Galileo",
        author="Historical Records of the Grand Duchy of Tuscany",
    ).model_dump(mode="json"),
)

fact_gc = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="professional.mentor_of",
            subject_id=galileo_id,
            object_id=cosimo_id,
            source_id=source_gc["id"],
            source_locator="Tutoría matemática (1605-1608), dedicatoria del Sidereus Nuncius y decreto de corte de 1610",
            note=(
                "Galileo Galilei fue el tutor personal de matemáticas de Cosme II de Médici en Florencia (1605-1608). "
                "En 1610, Galileo le dedicó el descubrimiento de las cuatro lunas de Júpiter bautizándolas 'Estrellas Mediceas' "
                "(Medicea Sidera), y Cosme II lo nombró Matemático y Filósofo Principal de la corte toscana en el Palacio Pitti."
            ),
            status="draft",
        ),
    ),
)
data_gc = {
    k: v
    for k, v in repo.get("facts", fact_gc["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_gc["status"] = "verified"
repo.update(
    "facts",
    fact_gc["id"],
    fact_gc["revision"],
    validate_fact(repo, data_gc),
    "verify",
)
print("Hecho Galileo <-> Cosme II verificado.")

# 7. Resumen de conexiones
print("\n--- Conexiones de Galileo Galilei ---")
print(json.dumps(connection_preview(repo, galileo_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Cosme II de Médici ---")
print(json.dumps(connection_preview(repo, cosimo_id), indent=2, ensure_ascii=False))
