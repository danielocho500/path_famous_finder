import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import (
    EventInput,
    EventParticipantInput,
    FactInput,
    HistoricalDate,
    LocationInput,
    Period,
    PersonInput,
    SourceInput,
    WorkInput,
)
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_event, validate_fact

repo = GraphRepository(driver)


def find_existing_person(tx, wikidata_id, name):
    """Verifica si una persona ya existe en Neo4j por wikidata_id o nombre."""
    if wikidata_id:
        res = tx.run(
            "MATCH (p:Person {wikidata_id: $qid}) RETURN p.id AS id, coalesce(p.search_name, p.real_name, p.name) AS name, p.wikidata_id AS wikidata_id",
            qid=wikidata_id,
        ).single()
        if res:
            return {"id": res["id"], "name": res["name"], "wikidata_id": res["wikidata_id"]}

    res = tx.run(
        """
        MATCH (p:Person)
        WHERE toLower(coalesce(p.search_name, '')) = toLower($name)
           OR toLower(coalesce(p.real_name, '')) = toLower($name)
           OR toLower(coalesce(p.best_known_for, '')) = toLower($name)
        RETURN p.id AS id, coalesce(p.search_name, p.real_name) AS name, p.wikidata_id AS wikidata_id
        LIMIT 1
        """,
        name=name,
    ).single()
    if res:
        return {"id": res["id"], "name": res["name"], "wikidata_id": res["wikidata_id"]}

    return None


def get_or_create_person(person_input: PersonInput, extra_props: dict):
    """Verifica antes de crear; si ya existe, devuelve el nodo existente."""
    with driver.session() as session:
        existing = session.execute_read(
            find_existing_person,
            person_input.wikidata_id,
            person_input.name,
        )

    if existing:
        print(f"[EXISTE PERSONA] '{existing['name']}' (ID: {existing['id']}, Wikidata: {existing['wikidata_id']})")
        return existing["id"]

    print(f"[NUEVA PERSONA] Creando: '{person_input.name}' (Wikidata: {person_input.wikidata_id})...")
    created = repo.create("people", person_input.model_dump(mode="json"))
    person_id = created["id"]

    with driver.session() as session:
        session.run(
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
            id=person_id,
            rn=extra_props.get("real_name", person_input.name),
            bkf=extra_props.get("best_known_for", person_input.name),
            c=person_input.country,
            img=person_input.image_url,
            occ=extra_props.get("principal_occupation", ""),
            desc=person_input.description,
        )
    print(f"[CREADA PERSONA] ID: {person_id}")
    return person_id


def get_or_create_work(work_input: WorkInput):
    """Verifica si la obra ya existe antes de crearla."""
    with driver.session() as session:
        res = session.run(
            """
            MATCH (w:Work)
            WHERE toLower(coalesce(w.search_name, '')) = toLower($name)
            RETURN w.id AS id, w.search_name AS name
            LIMIT 1
            """,
            name=work_input.name,
        ).single()
        if res:
            print(f"[EXISTE OBRA] '{res['name']}' (ID: {res['id']})")
            return res["id"]

    print(f"[NUEVA OBRA] Creando: '{work_input.name}'...")
    created = repo.create("works", work_input.model_dump(mode="json"))
    print(f"[CREADA OBRA] ID: {created['id']}")
    return created["id"]


def get_or_create_source(source_input: SourceInput):
    """Verifica si la fuente ya existe por URL o título."""
    with driver.session() as session:
        res = session.run(
            """
            MATCH (s:Source)
            WHERE (s.url IS NOT NULL AND s.url = $url)
               OR toLower(coalesce(s.search_name, '')) = toLower($title)
            RETURN s.id AS id, s.search_name AS title
            LIMIT 1
            """,
            url=source_input.url,
            title=source_input.title,
        ).single()
        if res:
            print(f"[EXISTE FUENTE] '{res['title']}' (ID: {res['id']})")
            return res["id"]

    print(f"[NUEVA FUENTE] Creando: '{source_input.title}'...")
    created = repo.create("sources", source_input.model_dump(mode="json"))
    print(f"[CREADA FUENTE] ID: {created['id']}")
    return created["id"]


def get_or_create_verified_fact(fact_input: FactInput):
    """Verifica si el hecho exacto ya existe (mismo sujeto, objeto, tipo y rol); si no, lo crea y verifica."""
    with driver.session() as session:
        res = session.run(
            """
            MATCH (p:Person {id: $sub})-[:SUBJECT_OF]->(f:Fact)-[:OBJECT]->(o {id: $obj})
            WHERE f.type_id = $type_id
              AND coalesce(f.role, '') = coalesce($role, '')
            RETURN f.id AS id, f.status AS status
            LIMIT 1
            """,
            sub=fact_input.subject_id,
            obj=fact_input.object_id,
            type_id=fact_input.type_id,
            role=fact_input.role,
        ).single()

    if res:
        print(f"[EXISTE HECHO] ID {res['id']} ({fact_input.type_id}, Status: {res['status']})")
        return res["id"]

    print(f"[NUEVO HECHO] Creando: {fact_input.type_id} ({fact_input.subject_id} -> {fact_input.object_id})...")
    validated = validate_fact(repo, fact_input)
    created = repo.create("facts", validated)
    fact_id = created["id"]

    current = repo.get("facts", fact_id)
    data = {k: v for k, v in current.items() if k not in ("id", "revision", "created_at", "updated_at")}
    data["status"] = "verified"
    repo.update("facts", fact_id, current["revision"], validate_fact(repo, data), "verify")
    print(f"[HECHO VERIFICADO] ID {fact_id} creado y verificado.")
    return fact_id


def get_or_create_event_with_facts(event_input: EventInput):
    """Verifica si el evento ya existe antes de crearlo junto con sus participantes."""
    with driver.session() as session:
        res = session.run(
            """
            MATCH (e:Event)
            WHERE toLower(coalesce(e.search_name, '')) = toLower($name)
            RETURN e.id AS id, e.search_name AS name
            LIMIT 1
            """,
            name=event_input.name,
        ).single()
        if res:
            print(f"[EXISTE EVENTO] '{res['name']}' (ID: {res['id']})")
            return res["id"]

    print(f"[NUEVO EVENTO] Creando: '{event_input.name}'...")
    event_validated = validate_event(repo, event_input)
    facts_validated = [
        validate_fact(repo, p, pending_context=event_validated)
        for p in event_input.participants
    ]
    created = repo.create_event_with_facts(event_validated, facts_validated)
    event_id = created["id"]
    for f in created["participants"]:
        fact_id = f["id"]
        current = repo.get("facts", fact_id)
        data = {k: v for k, v in current.items() if k not in ("id", "revision", "created_at", "updated_at")}
        data["status"] = "verified"
        repo.update("facts", fact_id, current["revision"], validate_fact(repo, data), "verify")
    print(f"[EVENTO CREADO Y PARTICIPANTES VERIFICADOS] ID: {event_id}")
    return event_id


print("================================================================================")
print("  CONEXIÓN EXPLICABLE: SILVANA ESTRADA -> LOUIS PASTEUR")
print("================================================================================")

# ==============================================================================
# 1. PERSONAS (Verificadas antes de crear para evitar duplicados)
# ==============================================================================
print("\n--- 1. Verificando / Creando Personas ---")

# 1.1 Silvana Estrada
silvana_id = get_or_create_person(
    PersonInput(
        name="Silvana Estrada",
        aliases=["Silvana Estrada Romero"],
        description=(
            "Cantautora y música multiinstrumentista mexicana, aclamada por su interpretación con el cuatro venezolano "
            "y ganadora del Latin Grammy a Mejor Nuevo Artista (2022). Colaboradora cercana de Natalia Lafourcade."
        ),
        country="MX",
        city_born="Coatepec",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Silvana_Estrada_2022.jpg/800px-Silvana_Estrada_2022.jpg",
        wikidata_id="Q62066618",
        birth=HistoricalDate(year=1997, month=4, day=15, precision="day"),
    ),
    {
        "real_name": "Silvana Estrada Romero",
        "best_known_for": "Silvana Estrada",
        "principal_occupation": "Cantautora, multinstrumentista y compositora",
    },
)

# 1.2 Natalia Lafourcade (Ya en BD)
natalia_id = get_or_create_person(
    PersonInput(
        name="Natalia Lafourcade",
        aliases=["María Natalia Lafourcade Silva"],
        description="Cantautora, productora, actriz y compositora mexicana. Ganadora de múltiples premios Grammy y Latin Grammy.",
        country="MX",
        city_born="Coatepec",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/5/52/Natalia_Lafourcade_2017.jpg/800px-Natalia_Lafourcade_2017.jpg",
        wikidata_id="Q192273",
        birth=HistoricalDate(year=1984, month=2, day=26, precision="day"),
    ),
    {
        "real_name": "María Natalia Lafourcade Silva",
        "best_known_for": "Natalia Lafourcade",
        "principal_occupation": "Cantautora y productora",
    },
)

# 1.3 Jorge V del Reino Unido (Ya en BD)
george_v_id = get_or_create_person(
    PersonInput(
        name="Jorge V del Reino Unido",
        aliases=["George V", "George Frederick Ernest Albert"],
        description="Rey del Reino Unido y los dominios de la Mancomunidad Británica de Naciones, y emperador de la India de 1910 a 1936.",
        country="GB",
        city_born="Londres",
        image_url="https://upload.wikimedia.org/wikipedia/commons/5/50/King_George_V_1911.jpg",
        wikidata_id="Q269412",
        birth=HistoricalDate(year=1865, month=6, day=3, precision="day"),
        death=HistoricalDate(year=1936, month=1, day=20, precision="day"),
    ),
    {
        "real_name": "George Frederick Ernest Albert",
        "best_known_for": "Jorge V del Reino Unido",
        "principal_occupation": "Monarca del Reino Unido y emperador de la India",
    },
)

# 1.4 Eduardo VII del Reino Unido (Padre de Jorge V, anfitrión de Pasteur en 1881)
edward_vii_id = get_or_create_person(
    PersonInput(
        name="Eduardo VII del Reino Unido",
        aliases=["Edward VII", "Albert Edward", "Príncipe de Gales"],
        description=(
            "Rey del Reino Unido de Gran Bretaña e Irlanda y emperador de la India de 1901 a 1910. "
            "Como Príncipe de Gales inauguró y presidió el 7.º Congreso Médico Internacional en Londres el 2 de agosto de 1881, "
            "donde dio la bienvenida oficial y condecoró el genio científico de Louis Pasteur."
        ),
        country="GB",
        city_born="Londres",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/e/e2/King_Edward_VII_%281841-1910%29.jpg/800px-King_Edward_VII_%281841-1910%29.jpg",
        wikidata_id="Q20875",
        birth=HistoricalDate(year=1841, month=11, day=9, precision="day"),
        death=HistoricalDate(year=1910, month=5, day=6, precision="day"),
    ),
    {
        "real_name": "Albert Edward",
        "best_known_for": "Eduardo VII del Reino Unido",
        "principal_occupation": "Monarca del Reino Unido y emperador de la India",
    },
)

# 1.5 Joseph Lister (Figura clave y discípulo de Pasteur, cirujano de la corte británica)
lister_id = get_or_create_person(
    PersonInput(
        name="Joseph Lister",
        aliases=["Lord Lister", "Baron Lister"],
        description=(
            "Cirujano y científico británico pionero de la cirugía antiséptica moderna. Basó sus descubrimientos "
            "directamente en la teoría germinal de Louis Pasteur, a quien rindió el célebre homenaje de la Sorbona en 1892. "
            "Fue cirujano personal de la Reina Victoria y del Rey Eduardo VII."
        ),
        country="GB",
        city_born="Upton",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/b/b8/Joseph_Lister_c1867.jpg/800px-Joseph_Lister_c1867.jpg",
        wikidata_id="Q155767",
        birth=HistoricalDate(year=1827, month=4, day=5, precision="day"),
        death=HistoricalDate(year=1912, month=2, day=10, precision="day"),
    ),
    {
        "real_name": "Joseph Lister",
        "best_known_for": "Joseph Lister",
        "principal_occupation": "Cirujano británico y padre de la cirugía antiséptica",
    },
)

# 1.6 Louis Pasteur
pasteur_id = get_or_create_person(
    PersonInput(
        name="Louis Pasteur",
        aliases=["Pasteur"],
        description=(
            "Químico, físico y bacteriólogo francés, uno de los científicos más influyentes de la historia de la humanidad. "
            "Pionero de la microbiología médica, creador del proceso de pasteurización y de las vacunas contra la rabia y el carbunco."
        ),
        country="FR",
        city_born="Dole",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Louis_Pasteur%2C_photo_Pierre_Lamy_Petit_cir_1880.jpg/800px-Louis_Pasteur%2C_photo_Pierre_Lamy_Petit_cir_1880.jpg",
        wikidata_id="Q529",
        birth=HistoricalDate(year=1822, month=12, day=27, precision="day"),
        death=HistoricalDate(year=1895, month=9, day=28, precision="day"),
    ),
    {
        "real_name": "Louis Pasteur",
        "best_known_for": "Louis Pasteur",
        "principal_occupation": "Científico, bacteriólogo y químico francés",
    },
)

# ==============================================================================
# 2. FUENTES DOCUMENTADAS CON GEOLOCALIZACIÓN
# ==============================================================================
print("\n--- 2. Verificando / Creando Fuentes Históricas ---")

# Fuente 1: Colaboración Silvana Estrada y Natalia Lafourcade (Un Canto por México)
src_silvana_natalia = get_or_create_source(
    SourceInput(
        title="Sony Music & Rolling Stone - Natalia Lafourcade y Silvana Estrada en Un Canto por México Vol. 2 (2021)",
        url="https://www.sonymusic.com.mx/natalia-lafourcade-presenta-un-canto-por-mexico-vol-2/",
        citation="Créditos oficiales del álbum 'Un Canto por México, Vol. 2' (Sony Music México, 2021): Silvana Estrada y Natalia Lafourcade en 'La Llorona'.",
        author="Sony Music México",
        publisher="Sony Music Entertainment México",
        location=LocationInput(
            name="Estudios Sony Music México",
            city="Ciudad de México",
            country="MX",
            lat=19.4326,
            lng=-99.1332,
        ),
    )
)

# Fuente 2: Concierto en el Auditorio Nacional (7 de noviembre de 2023)
src_auditorio_concierto = get_or_create_source(
    SourceInput(
        title="Rolling Stone & OCESA - Natalia Lafourcade invita a Silvana Estrada al Auditorio Nacional (2023)",
        url="https://es.rollingstone.com/natalia-lafourcade-concierto-auditorio-nacional-silvana-estrada/",
        citation="Rolling Stone México: 'Natalia Lafourcade triunfa en el Auditorio Nacional con Silvana Estrada como invitada especial', Ciudad de México, 7 de noviembre de 2023.",
        author="Redacción Rolling Stone",
        publisher="Rolling Stone México / OCESA",
        location=LocationInput(
            name="Auditorio Nacional",
            city="Ciudad de México",
            country="MX",
            lat=19.4246,
            lng=-99.1918,
        ),
    )
)

# Fuente 3: Linaje Real Británico (Eduardo VII y Jorge V)
src_royal_lineage = get_or_create_source(
    SourceInput(
        title="The Royal Archives - Lineage and Birth of King George V, Son of King Edward VII (1865)",
        url="https://www.royal.uk/george-v",
        citation="Official Records of the British Monarchy: Birth of Prince George Frederick Ernest Albert (King George V) to Albert Edward, Prince of Wales (King Edward VII), Marlborough House, London, June 3, 1865.",
        author="The Royal Collection Trust",
        publisher="The Royal Household",
        location=LocationInput(
            name="Marlborough House",
            city="Londres",
            country="GB",
            lat=51.5049,
            lng=-0.1368,
        ),
    )
)

# Fuente 4: Congreso Médico Internacional de Londres 1881 (Eduardo VII y Louis Pasteur)
src_congress_1881 = get_or_create_source(
    SourceInput(
        title="Transactions of the International Medical Congress London 1881 - Opening Address and Reception of Louis Pasteur",
        url="https://archive.org/details/transactionsofint01inte",
        citation="Transactions of the International Medical Congress, Seventh Session, Vol. 1, pp. 1-15: Inaugural session led by H.R.H. The Prince of Wales (King Edward VII) receiving Professor Louis Pasteur, St James's Hall, London, August 2, 1881.",
        author="Sir William MacCormac & International Medical Congress Committee",
        publisher="J.W. Kolckmann, London",
        location=LocationInput(
            name="St James's Hall",
            city="Londres",
            country="GB",
            lat=51.5096,
            lng=-0.1367,
        ),
    )
)

# Fuente 5: Jubileo de Louis Pasteur en la Sorbona con Joseph Lister (1892)
src_sorbonne_jubilee = get_or_create_source(
    SourceInput(
        title="Académie des Sciences & Sorbonne Archives - Jubilé de M. Louis Pasteur (1892)",
        url="https://gallica.bnf.fr/ark:/12148/bpt6k202868s",
        citation="Compte-rendu solennel du Jubilé de M. Louis Pasteur célébré à la Sorbonne le 27 décembre 1892: Étreinte historique entre Louis Pasteur et Lord Joseph Lister.",
        author="Académie des Sciences de Paris",
        publisher="Gauthier-Villars, Imprimeur-Libraire",
        location=LocationInput(
            name="Gran Anfiteatro de la Sorbona",
            city="París",
            country="FR",
            lat=48.8485,
            lng=2.3433,
        ),
    )
)

# ==============================================================================
# 3. OBRAS MUSICALES Y EVENTO EN VIVO
# ==============================================================================
print("\n--- 3. Creando Obras y Eventos Artísticos ---")

# 3.1 Obra: "Un Canto por México, Vol. 2" (2021)
work_canto_mexico_id = get_or_create_work(
    WorkInput(
        name="Un Canto por México, Vol. 2",
        kind="music",
        period=Period(
            start=HistoricalDate(year=2021, precision="year"),
            end=HistoricalDate(year=2021, precision="year"),
        ),
        description=(
            "Álbum de estudio de Natalia Lafourcade lanzado en 2021 en beneficio del Centro de Documentación del Son Jarocho, "
            "que cuenta con la destacada colaboración vocal y musical de Silvana Estrada en el tema 'La Llorona'."
        ),
    )
)

# 3.2 Evento: Concierto en el Auditorio Nacional (7 de noviembre de 2023)
event_auditorio_id = get_or_create_event_with_facts(
    EventInput(
        name="Concierto Natalia Lafourcade - Gira De Todas las Flores en el Auditorio Nacional",
        kind="arts.performance",
        place="Auditorio Nacional, Ciudad de México",
        period=Period(
            start=HistoricalDate(year=2023, month=11, day=7, precision="day"),
            end=HistoricalDate(year=2023, month=11, day=7, precision="day"),
        ),
        source_id=src_auditorio_concierto,
        source_locator="Concierto sold out en el Auditorio Nacional, 7 de noviembre de 2023.",
        location=LocationInput(
            name="Auditorio Nacional",
            city="Ciudad de México",
            country="MX",
            lat=19.4246,
            lng=-99.1918,
        ),
        participants=[
            EventParticipantInput(
                type_id="arts.performed_together",
                subject_id=natalia_id,
                source_id=src_auditorio_concierto,
                source_locator="Presentación estelar de Natalia Lafourcade en el Auditorio Nacional.",
                role="performer",
                status="draft",
                note="Natalia Lafourcade encabezó su concierto en el Auditorio Nacional e invitó a Silvana Estrada.",
            ),
            EventParticipantInput(
                type_id="arts.performed_together",
                subject_id=silvana_id,
                source_id=src_auditorio_concierto,
                source_locator="Aparición especial de Silvana Estrada en el Auditorio Nacional.",
                role="performer",
                status="draft",
                note="Silvana Estrada subió al escenario como invitada especial para cantar 'La Llorona' y 'La Corriente' a dueto.",
            ),
        ],
    )
)

# ==============================================================================
# 4. HECHOS VERIFICADOS (ENLACES HISTÓRICOS Y GENEALÓGICOS)
# ==============================================================================
print("\n--- 4. Creando / Verificando Hechos Relacionales ---")

# A) SILVANA ESTRADA Y NATALIA LAFOURCADE: COLABORACIÓN EN DISCO (arts.collaborated_on_work)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=silvana_id,
        object_id=work_canto_mexico_id,
        role="performer",
        period=Period(
            start=HistoricalDate(year=2021, precision="year"),
            end=HistoricalDate(year=2021, precision="year"),
        ),
        source_id=src_silvana_natalia,
        source_locator="Créditos del álbum 'Un Canto por México, Vol. 2', Sony Music México, mayo de 2021.",
        note="Silvana Estrada grabó la voz y arreglos de cuatro venezolano en la versión de 'La Llorona' junto a Natalia Lafourcade.",
        status="draft",
        location=LocationInput(
            name="Estudios Sony Music México",
            city="Ciudad de México",
            country="MX",
            lat=19.4326,
            lng=-99.1332,
        ),
    )
)

get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=natalia_id,
        object_id=work_canto_mexico_id,
        role="creator",
        period=Period(
            start=HistoricalDate(year=2021, precision="year"),
            end=HistoricalDate(year=2021, precision="year"),
        ),
        source_id=src_silvana_natalia,
        source_locator="Créditos de producción de 'Un Canto por México, Vol. 2', 2021.",
        note="Natalia Lafourcade ideó, produjo y encabezó el proyecto discográfico 'Un Canto por México, Vol. 2'.",
        status="draft",
        location=LocationInput(
            name="Estudios Sony Music México",
            city="Ciudad de México",
            country="MX",
            lat=19.4326,
            lng=-99.1332,
        ),
    )
)

# B) SILVANA ESTRADA <-> NATALIA LAFOURCADE: ENCUENTRO EN ESCENARIO (personal.met, 7 de noviembre de 2023)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=silvana_id,
        object_id=natalia_id,
        period=Period(
            start=HistoricalDate(year=2023, month=11, day=7, precision="day"),
            end=HistoricalDate(year=2023, month=11, day=7, precision="day"),
        ),
        source_id=src_auditorio_concierto,
        source_locator="Escenario del Auditorio Nacional, Ciudad de México, 7 de noviembre de 2023.",
        note=(
            "Silvana Estrada y Natalia Lafourcade compartieron el escenario del Auditorio Nacional en un emotivo reencuentro en vivo, "
            "interpretando a dúo 'La Llorona' y 'La Corriente' ante 10,000 espectadores."
        ),
        status="draft",
        location=LocationInput(
            name="Auditorio Nacional",
            city="Ciudad de México",
            country="MX",
            lat=19.4246,
            lng=-99.1918,
        ),
    )
)

# C) EDUARDO VII <-> JORGE V: RELACIÓN PADRE-HIJO (family.parent_of, 3 de junio de 1865)
get_or_create_verified_fact(
    FactInput(
        type_id="family.parent_of",
        subject_id=edward_vii_id,
        object_id=george_v_id,
        period=Period(
            start=HistoricalDate(year=1865, month=6, day=3, precision="day"),
            end=HistoricalDate(year=1910, month=5, day=6, precision="day"),
        ),
        source_id=src_royal_lineage,
        source_locator="Acta de nacimiento del príncipe George Frederick Ernest Albert, Marlborough House, Londres, 3 de junio de 1865.",
        note="El rey Eduardo VII (entonces Príncipe de Gales) es el padre biológico del rey Jorge V del Reino Unido.",
        status="draft",
        location=LocationInput(
            name="Marlborough House",
            city="Londres",
            country="GB",
            lat=51.5049,
            lng=-0.1368,
        ),
    )
)

# D) EDUARDO VII <-> LOUIS PASTEUR: ENCUENTRO OFICIAL EN EL CONGRESO MÉDICO DE LONDRES (personal.met, 2 de agosto de 1881)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=edward_vii_id,
        object_id=pasteur_id,
        period=Period(
            start=HistoricalDate(year=1881, month=8, day=2, precision="day"),
            end=HistoricalDate(year=1881, month=8, day=2, precision="day"),
        ),
        source_id=src_congress_1881,
        source_locator="Transactions of the International Medical Congress, London 1881, Sesión de Apertura, 2 de agosto de 1881.",
        note=(
            "El Príncipe de Gales (futuro Rey Eduardo VII) inauguró el 7.º Congreso Médico Internacional en St James's Hall en Londres "
            "el 2 de agosto de 1881, recibiendo en audiencia y con los máximos honores al célebre sabio francés Louis Pasteur, "
            "quien presentó sus revolucionarios descubrimientos sobre la vacunación y la teoría germinal de las enfermedades."
        ),
        status="draft",
        location=LocationInput(
            name="St James's Hall",
            city="Londres",
            country="GB",
            lat=51.5096,
            lng=-0.1367,
        ),
    )
)

# E) JOSEPH LISTER <-> LOUIS PASTEUR: EL CÉLEBRE ABRAZO DE LA SORBONA (personal.met, 27 de diciembre de 1892)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=lister_id,
        object_id=pasteur_id,
        period=Period(
            start=HistoricalDate(year=1892, month=12, day=27, precision="day"),
            end=HistoricalDate(year=1892, month=12, day=27, precision="day"),
        ),
        source_id=src_sorbonne_jubilee,
        source_locator="Gran Anfiteatro de la Sorbona, Ceremonia del Jubileo de los 70 años de Louis Pasteur, 27 de diciembre de 1892.",
        note=(
            "Durante el solemne Jubileo por los 70 años de Louis Pasteur en la Sorbona de París el 27 de diciembre de 1892, "
            "Lord Joseph Lister avanzó por el escenario para entregar una medalla de oro en nombre de la ciencia médica británica, "
            "fundiéndose ambos sabios en un emotivo e histórico abrazo que conmovió al mundo científico."
        ),
        status="draft",
        location=LocationInput(
            name="Gran Anfiteatro de la Sorbona",
            city="París",
            country="FR",
            lat=48.8485,
            lng=2.3433,
        ),
    )
)

# F) EDUARDO VII <-> JOSEPH LISTER: CIRUJANO REAL Y ORDEN DEL MÉRITO (personal.met, 14 de junio de 1902)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=edward_vii_id,
        object_id=lister_id,
        period=Period(
            start=HistoricalDate(year=1902, month=6, day=14, precision="day"),
            end=HistoricalDate(year=1902, month=6, day=14, precision="day"),
        ),
        source_id=src_royal_lineage,
        source_locator="Concesión de la Orden del Mérito (Order of Merit), Palacio de Buckingham, 14 de junio de 1902.",
        note=(
            "El Rey Eduardo VII nombró a Lord Joseph Lister como su cirujano de honor (Serjeant-Surgeon in Ordinary) "
            "y le concedió personalmente la Orden del Mérito en el Palacio de Buckingham en reconocimiento a su revolución quirúrgica."
        ),
        status="draft",
        location=LocationInput(
            name="Palacio de Buckingham",
            city="Londres",
            country="GB",
            lat=51.5014,
            lng=-0.1419,
        ),
    )
)

# ==============================================================================
# 5. VERIFICACIÓN Y PREVIEWS DEL CAMINO COMPLETO
# ==============================================================================
print("\n--- 5. Verificando Conexiones Derivadas y Caminos Óptimos ---")

print("\n[Conexiones derivadas para Silvana Estrada]:")
preview_silvana = connection_preview(repo, silvana_id)
for conn in preview_silvana:
    target_person = repo.get("people", conn["person_id"])
    target_name = target_person.get("search_name") or target_person.get("name")
    print(f"  -> Conectada con: {target_name} vía {conn['type_id']}")

print("\n[Conexiones derivadas para Louis Pasteur]:")
preview_pasteur = connection_preview(repo, pasteur_id)
for conn in preview_pasteur:
    target_person = repo.get("people", conn["person_id"])
    target_name = target_person.get("search_name") or target_person.get("name")
    print(f"  -> Conectado con: {target_name} vía {conn['type_id']}")

with driver.session() as session:
    path_res = session.run(
        """
        MATCH path = shortestPath((start:Person {id: $s_id})-[*..20]-(target:Person {id: $p_id}))
        RETURN [node IN nodes(path) | coalesce(node.search_name, node.name, labels(node)[0])] AS names,
               [rel IN relationships(path) | type(rel)] AS rels,
               length(path) AS hops
        """,
        s_id=silvana_id,
        p_id=pasteur_id,
    ).single()

if path_res:
    print(f"\n[CAMINO MÁS CORTO ENCONTRADO EN NEO4J] ({path_res['hops']} saltos):")
    for idx, name in enumerate(path_res["names"]):
        if idx < len(path_res["rels"]):
            print(f"  ({name}) --[{path_res['rels'][idx]}]-->")
        else:
            print(f"  ({name})")

print("\n================================================================================")
print("  CONEXIÓN SILVANA ESTRADA -> LOUIS PASTEUR COMPLETADA EXITOSAMENTE")
print("================================================================================")
