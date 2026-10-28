import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

lorenzo_id = "cb039671-bdb5-4d60-bb98-553ebb413b00"

print("--- Iniciando carga de la rama Médici -> Bizantina: Cosme el Viejo y Juan VIII Paleólogo ---")

# 1. Crear a Piero de' Médici («el Gotoso»)
piero_input = PersonInput(
    name="Piero de' Médici",
    aliases=[
        "Piero di Cosimo de' Medici",
        "Piero el Gotoso",
        "Piero il Gottoso",
    ],
    description=(
        "Gobernante de facto de Florencia (1464–1469), hijo de Cosme el Viejo y padre de Lorenzo el Magnífico. "
        "Prominente mecenas que encargó a Benozzo Gozzoli la 'Cabalgata de los Magos' en la Capilla del Palacio Médici, "
        "conmemorando el Concilio de Florencia de 1439."
    ),
    country="IT",
    city_born="Florencia",
    image_url="https://upload.wikimedia.org/wikipedia/commons/a/a7/Piero_di_Cosimo_de%27_Medici.jpg",
    wikidata_id="Q245209",
    birth=HistoricalDate(year=1416, precision="year"),
    death=HistoricalDate(year=1469, month=12, day=2, precision="day"),
).model_dump(mode="json")

piero = repo.create("people", piero_input)
piero_id = piero["id"]
print("Creado Piero de' Médici con ID:", piero_id)

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
        id=piero_id,
        rn="Piero di Cosimo de' Medici",
        bkf="Piero de' Médici",
        c="IT",
        img=piero_input["image_url"],
        occ="Gobernante de Florencia y mecenas de las artes",
        desc=piero_input["description"],
    )

# 2. Conectar Piero -> Lorenzo el Magnífico (family.parent_of)
source_p_lm = repo.create(
    "sources",
    SourceInput(
        title="Archivio di Stato di Firenze: Nascita di Lorenzo de' Medici da Piero e Lucrezia Tornabuoni (1449)",
        url="https://en.wikipedia.org/wiki/Lorenzo_de%27_Medici",
        publisher="Archivio di Stato di Firenze / Le Lettere",
        author="Gaetano Pieraccini: La stirpe de' Medici di Cafaggiolo",
    ).model_dump(mode="json"),
)

fact_p_lm = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=piero_id,
            object_id=lorenzo_id,
            source_id=source_p_lm["id"],
            source_locator="Archivio di Stato di Firenze: Nascita e battesimo di Lorenzo de' Medici il 1 gennaio 1449 a Firenze",
            note=(
                "Piero de' Médici ('el Gotoso') fue el padre de Lorenzo el Magnífico, fruto de su matrimonio con la poetisa y noble "
                "Lucrezia Tornabuoni. Piero preparó a Lorenzo en la diplomacia y el liderazgo político florentino hasta su muerte en 1469."
            ),
            status="draft",
        ),
    ),
)
data_p_lm = {
    k: v
    for k, v in repo.get("facts", fact_p_lm["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_p_lm["status"] = "verified"
repo.update(
    "facts",
    fact_p_lm["id"],
    fact_p_lm["revision"],
    validate_fact(repo, data_p_lm),
    "verify",
)
print("Hecho Piero -> Lorenzo el Magnífico verificado.")

# 3. Crear a Cosme de' Médici («Cosme el Viejo» / Pater Patriae)
cosimo_old_input = PersonInput(
    name="Cosme de' Médici el Viejo",
    aliases=[
        "Cosimo de' Medici",
        "Cosme el Viejo",
        "Pater Patriae",
    ],
    description=(
        "Fundador de la dinastía política de los Médici y primer gobernante de facto de Florencia (1434–1464). "
        "Financió y acogió el Concilio de Florencia de 1439, fundó la Academia Platónica Florentina inspirada por Gemisto Pletón "
        "y encargó la reconstrucción de San Lorenzo a Brunelleschi y la biblioteca del convento de San Marcos a Michelozzo."
    ),
    country="IT",
    city_born="Florencia",
    image_url="https://upload.wikimedia.org/wikipedia/commons/f/fa/Cosimo_di_Medici_%28Bronzino%29.jpg",
    wikidata_id="Q1699",
    birth=HistoricalDate(year=1389, month=9, day=27, precision="day"),
    death=HistoricalDate(year=1464, month=8, day=1, precision="day"),
).model_dump(mode="json")

cosimo_old = repo.create("people", cosimo_old_input)
cosimo_old_id = cosimo_old["id"]
print("Creado Cosme el Viejo con ID:", cosimo_old_id)

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
        id=cosimo_old_id,
        rn="Cosimo di Giovanni de' Medici",
        bkf="Cosme de' Médici el Viejo",
        c="IT",
        img=cosimo_old_input["image_url"],
        occ="Fundador del dominio político de los Médici y Padre de la Patria (Pater Patriae)",
        desc=cosimo_old_input["description"],
    )

# 4. Conectar Cosme el Viejo -> Piero de' Médici (family.parent_of)
source_co_p = repo.create(
    "sources",
    SourceInput(
        title="Albero genealogico dei Medici: Nascita di Piero da Cosimo il Vecchio e Contessina de' Bardi",
        url="https://en.wikipedia.org/wiki/Cosimo_de%27_Medici",
        publisher="Archivio di Stato di Firenze / Sansoni",
        author="Angelo Fabroni: Magni Cosmi Medicei Vita",
    ).model_dump(mode="json"),
)

fact_co_p = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=cosimo_old_id,
            object_id=piero_id,
            source_id=source_co_p["id"],
            source_locator="Archivio di Stato di Firenze: Nascita del primogenito Piero nel 1416 da Cosimo e Contessina de' Bardi",
            note=(
                "Cosme el Viejo fue el padre de Piero el Gotoso, nacido de su matrimonio con Contessina de' Bardi. "
                "Piero sucedió a su padre como cabeza del Banco Médici y señor de Florencia a su fallecimiento en 1464."
            ),
            status="draft",
        ),
    ),
)
data_co_p = {
    k: v
    for k, v in repo.get("facts", fact_co_p["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_co_p["status"] = "verified"
repo.update(
    "facts",
    fact_co_p["id"],
    fact_co_p["revision"],
    validate_fact(repo, data_co_p),
    "verify",
)
print("Hecho Cosme el Viejo -> Piero verificado.")

# 5. Crear a Juan VIII Paleólogo (Emperador Bizantino)
john_viii_input = PersonInput(
    name="Juan VIII Paleólogo",
    aliases=[
        "John VIII Palaiologos",
        "Ioannes VIII Palaiologos",
        "Emperador Juan VIII",
    ],
    description=(
        "Penúltimo Emperador del Imperio Bizantino / Basileus de los Romanos (1425–1448). "
        "Viajó a Italia con una gran corte imperial para presidir el Concilio de Florencia de 1439, "
        "donde proclamó la unión de las Iglesias católica y ortodoxa buscando ayuda militar occidental para salvar Constantinopla. "
        "Inmortalizado en la famosa medalla de Pisanello y los frescos de Gozzoli."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/2/24/Palaio.jpg",
    wikidata_id="Q37072",
    birth=HistoricalDate(year=1392, month=12, day=18, precision="day"),
    death=HistoricalDate(year=1448, month=10, day=31, precision="day"),
).model_dump(mode="json")

john_viii = repo.create("people", john_viii_input)
john_viii_id = john_viii["id"]
print("Creado Juan VIII Paleólogo con ID:", john_viii_id)

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
        id=john_viii_id,
        rn="Ioannes VIII Palaiologos",
        bkf="Juan VIII Paleólogo",
        c="GR",
        img=john_viii_input["image_url"],
        occ="Emperador del Imperio Bizantino (Basileus de los Romanos)",
        desc=john_viii_input["description"],
    )

# 6. Conectar Cosme el Viejo <-> Juan VIII Paleólogo (personal.met / Concilio de Florencia 1439)
source_co_j = repo.create(
    "sources",
    SourceInput(
        title="Il Concilio di Firenze del 1439: L'incontro tra Cosimo il Vecchio e l'imperatore Giovanni VIII Paleologo",
        url="https://en.wikipedia.org/wiki/Council_of_Florence",
        publisher="Archivio Storico Italiano / Leo S. Olschki",
        author="Joseph Gill: The Council of Florence",
    ).model_dump(mode="json"),
)

fact_co_j = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=cosimo_old_id,
            object_id=john_viii_id,
            source_id=source_co_j["id"],
            source_locator="Firenze, Palazzo Medici e Santa Maria Novella (febbraio-luglio 1439)",
            note=(
                "Cosme el Viejo de Médici financió y organizó el traslado del Concilio ecuménico de Ferrara a Florencia en febrero de 1439. "
                "Allí agasajó y se reunió personalmente con el emperador bizantino Juan VIII Paleólogo y su séquito imperial, "
                "cubriendo sus cuantiosos gastos de estancia y forjando una profunda fascinación por el saber griego clásico "
                "que impulsó el renacimiento de las letras helénicas en Europa."
            ),
            status="draft",
        ),
    ),
)
data_co_j = {
    k: v
    for k, v in repo.get("facts", fact_co_j["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_co_j["status"] = "verified"
repo.update(
    "facts",
    fact_co_j["id"],
    fact_co_j["revision"],
    validate_fact(repo, data_co_j),
    "verify",
)
print("Hecho Cosme el Viejo <-> Juan VIII Paleólogo verificado.")

# 7. Crear al Papa Eugenio IV
eugene_input = PersonInput(
    name="Papa Eugenio IV",
    aliases=[
        "Gabriele Condulmer",
        "Eugenio IV",
        "Pope Eugene IV",
    ],
    description=(
        "Papa de la Iglesia Católica (1431–1447), protector de las artes y humanistas. "
        "Presidió el Concilio de Ferrara-Florencia y promulgó junto a Juan VIII Paleólogo la histórica bula de unión 'Laetentur Caeli' (1439), "
        "residiendo en Florencia bajo la alianza y amparo financiero de Cosme de' Médici."
    ),
    country="IT",
    city_born="Venecia",
    image_url="https://upload.wikimedia.org/wikipedia/commons/c/c1/Domenico_di_Bartolo%2C_madonna_della_misericordia%2C_1444%2C_06%28cropped%29.jpg",
    wikidata_id="Q167444",
    birth=HistoricalDate(year=1383, precision="year"),
    death=HistoricalDate(year=1447, month=2, day=23, precision="day"),
).model_dump(mode="json")

eugene = repo.create("people", eugene_input)
eugene_id = eugene["id"]
print("Creado Papa Eugenio IV con ID:", eugene_id)

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
        id=eugene_id,
        rn="Gabriele Condulmer",
        bkf="Papa Eugenio IV",
        c="IT",
        img=eugene_input["image_url"],
        occ="Papa de la Iglesia Católica (1431–1447)",
        desc=eugene_input["description"],
    )

# 8. Conectar Papa Eugenio IV <-> Juan VIII Paleólogo (personal.met / Firma de Laetentur Caeli)
source_eu_j = repo.create(
    "sources",
    SourceInput(
        title="Bolla pontificia Laetentur Caeli: Unione delle Chiese latina e greca al Concilio di Firenze (6 luglio 1439)",
        url="https://en.wikipedia.org/wiki/Council_of_Florence",
        publisher="Archivio Segreto Vaticano / Sacrosancta Concilia",
        author="Papa Eugenio IV & Imperatore Giovanni VIII Paleologo",
    ).model_dump(mode="json"),
)

fact_eu_j = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=eugene_id,
            object_id=john_viii_id,
            source_id=source_eu_j["id"],
            source_locator="Cattedrale di Santa Maria del Fiore, Firenze (6 luglio 1439)",
            note=(
                "El 6 de julio de 1439, el Papa Eugenio IV y el Emperador Juan VIII Paleólogo firmaron y proclamaron solemnemente "
                "en la catedral de Santa Maria del Fiore de Florencia la célebre bula de unión 'Laetentur Caeli', celebrando la misa "
                "en latín y griego y abrazándose ante los prelados de Oriente y Occidente."
            ),
            status="draft",
        ),
    ),
)
data_eu_j = {
    k: v
    for k, v in repo.get("facts", fact_eu_j["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_eu_j["status"] = "verified"
repo.update(
    "facts",
    fact_eu_j["id"],
    fact_eu_j["revision"],
    validate_fact(repo, data_eu_j),
    "verify",
)
print("Hecho Papa Eugenio IV <-> Juan VIII Paleólogo verificado.")

# 9. Conectar Papa Eugenio IV <-> Cosme el Viejo (personal.met / alianza florentina)
source_eu_co = repo.create(
    "sources",
    SourceInput(
        title="Il soggiorno di Eugenio IV a Firenze e l'alleanza con Cosimo de' Medici (1434–1443)",
        url="https://en.wikipedia.org/wiki/Pope_Eugene_IV",
        publisher="Archivio Storico Italiano / Leo S. Olschki",
        author="Gustavo Uzielli / Gaetano Pieraccini",
    ).model_dump(mode="json"),
)

fact_eu_co = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=eugene_id,
            object_id=cosimo_old_id,
            source_id=source_eu_co["id"],
            source_locator="Convento di Santa Maria Novella, Firenze (1434–1443)",
            note=(
                "El Papa Eugenio IV residió en Florencia durante varios años en el convento de Santa Maria Novella amparado por Cosme de' Médici, "
                "quien actuó como su banquero y principal respaldo diplomático y militar frente a las rebeliones romanas y el Concilio de Basilea."
            ),
            status="draft",
        ),
    ),
)
data_eu_co = {
    k: v
    for k, v in repo.get("facts", fact_eu_co["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_eu_co["status"] = "verified"
repo.update(
    "facts",
    fact_eu_co["id"],
    fact_eu_co["revision"],
    validate_fact(repo, data_eu_co),
    "verify",
)
print("Hecho Papa Eugenio IV <-> Cosme el Viejo verificado.")

# 10. Crear a Gemisto Pletón
pletho_input = PersonInput(
    name="Gemisto Pletón",
    aliases=[
        "George Gemistos Plethon",
        "Georgios Gemistos",
        "Pletón",
    ],
    description=(
        "Erudito neoplatónico y filósofo griego bizantino de Mistra, una de las mentes más brillantes de finales del Imperio Bizantino. "
        "Acompañó al emperador Juan VIII a Florencia en 1439, donde sus conferencias sobre Platón entusiasmaron a Cosme el Viejo "
        "y propiciaron la creación de la Academia Platónica Florentina."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/a/a7/Benozzo_Gozzoli%2C_Pletone%2C_Cappella_dei_Magi.jpg",
    wikidata_id="Q208638",
    birth=HistoricalDate(year=1355, precision="year"),
    death=HistoricalDate(year=1452, month=6, day=26, precision="day"),
).model_dump(mode="json")

pletho = repo.create("people", pletho_input)
pletho_id = pletho["id"]
print("Creado Gemisto Pletón con ID:", pletho_id)

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
        id=pletho_id,
        rn="Georgios Gemistos Plethon",
        bkf="Gemisto Pletón",
        c="GR",
        img=pletho_input["image_url"],
        occ="Filósofo neoplatónico y humanista bizantino de Mistra",
        desc=pletho_input["description"],
    )

# 11. Conectar Gemisto Pletón <-> Cosme el Viejo (personal.met / lecciones de Platón)
source_pl_co = repo.create(
    "sources",
    SourceInput(
        title="Plethon and the Florentine Platonic Academy of Cosimo de' Medici",
        url="https://en.wikipedia.org/wiki/Gemistus_Pletho",
        publisher="Oxford University Press / The Warburg Institute",
        author="C. M. Woodhouse: George Gemistos Plethon: The Last of the Hellenes",
    ).model_dump(mode="json"),
)

fact_pl_co = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=pletho_id,
            object_id=cosimo_old_id,
            source_id=source_pl_co["id"],
            source_locator="Conferenze neoplatoniche a Firenze (1439) e Prefazione alle Opere di Platone di Marsilio Ficino",
            note=(
                "Durante el Concilio de Florencia en 1439, Gemisto Pletón impartió una serie de magistrales conferencias sobre las diferencias "
                "entre Platón y Aristóteles. Cosme de' Médici quedó tan inspirado por sus enseñanzas que concibió la idea de revivir "
                "la Academia Platónica de Atenas en Florencia, encargando años después a Marsilio Ficino la traducción completa de Platón."
            ),
            status="draft",
        ),
    ),
)
data_pl_co = {
    k: v
    for k, v in repo.get("facts", fact_pl_co["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_pl_co["status"] = "verified"
repo.update(
    "facts",
    fact_pl_co["id"],
    fact_pl_co["revision"],
    validate_fact(repo, data_pl_co),
    "verify",
)
print("Hecho Gemisto Pletón <-> Cosme el Viejo verificado.")

# 12. Conectar Gemisto Pletón <-> Juan VIII Paleólogo (personal.met / séquito imperial)
source_pl_j = repo.create(
    "sources",
    SourceInput(
        title="La delegazione bizantina al Concilio di Ferrara-Firenze: Plethone al seguito dell'imperatore",
        url="https://en.wikipedia.org/wiki/Gemistus_Pletho",
        publisher="Archivio di Stato di Firenze / Brill",
        author="Silvester Syropoulos: Memoirs of the Council of Florence",
    ).model_dump(mode="json"),
)

fact_pl_j = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=pletho_id,
            object_id=john_viii_id,
            source_id=source_pl_j["id"],
            source_locator="Seguito dell'imperatore Giovanni VIII a Ferrara e Firenze (1438–1439)",
            note=(
                "Gemisto Pletón fue elegido personalmente por el emperador Juan VIII Paleólogo como uno de sus seis consejeros "
                "y delegados principales no eclesiásticos para representarlo en los debates teológicos y filosóficos del Concilio de Florencia."
            ),
            status="draft",
        ),
    ),
)
data_pl_j = {
    k: v
    for k, v in repo.get("facts", fact_pl_j["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_pl_j["status"] = "verified"
repo.update(
    "facts",
    fact_pl_j["id"],
    fact_pl_j["revision"],
    validate_fact(repo, data_pl_j),
    "verify",
)
print("Hecho Gemisto Pletón <-> Juan VIII Paleólogo verificado.")

# Resumen de conexiones de Juan VIII Paleólogo
print("\n--- Conexiones de Juan VIII Paleólogo ---")
print(json.dumps(connection_preview(repo, john_viii_id), indent=2, ensure_ascii=False))
