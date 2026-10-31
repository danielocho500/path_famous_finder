import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import (
    FactInput,
    HistoricalDate,
    LocationInput,
    Period,
    PersonInput,
    SourceInput,
    WorkInput,
)
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

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


print("================================================================================")
print("  CONEXIÓN EXPLICABLE: ENRIQUE PEÑA NIETO -> EMILIA CLARKE")
print("================================================================================")

# ==============================================================================
# 1. PERSONAS (Verificadas antes de crear para evitar duplicados)
# ==============================================================================
print("\n--- 1. Verificando / Creando Personas ---")

# 1.1 Enrique Peña Nieto
epn_id = get_or_create_person(
    PersonInput(
        name="Enrique Peña Nieto",
        aliases=["EPN", "Peña Nieto"],
        description=(
            "Abogado y político mexicano. Presidente de los Estados Unidos Mexicanos de 2012 a 2018 y "
            "anteriormente gobernador del Estado de México (2005–2011)."
        ),
        country="MX",
        city_born="Atlacomulco",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/Enrique_Pe%C3%B1a_Nieto_2015.jpg/800px-Enrique_Pe%C3%B1a_Nieto_2015.jpg",
        wikidata_id="Q296741",
        birth=HistoricalDate(year=1966, month=7, day=20, precision="day"),
    ),
    {
        "real_name": "Enrique Peña Nieto",
        "best_known_for": "Enrique Peña Nieto",
        "principal_occupation": "Presidente de México (2012–2018)",
    },
)

# 1.2 Leonardo DiCaprio
dicaprio_id = get_or_create_person(
    PersonInput(
        name="Leonardo DiCaprio",
        aliases=["Leo DiCaprio", "Leonardo Wilhelm DiCaprio"],
        description=(
            "Aclamado actor y productor de cine estadounidense, ganador del Premio Óscar, BAFTA y tres Globos de Oro. "
            "Reconocido activista ecológico global y Mensajero de la Paz de la ONU para el Cambio Climático."
        ),
        country="US",
        city_born="Los Ángeles",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/Leonardo_DiCaprio_profile_2016.jpg/800px-Leonardo_DiCaprio_profile_2016.jpg",
        wikidata_id="Q38111",
        birth=HistoricalDate(year=1974, month=11, day=11, precision="day"),
    ),
    {
        "real_name": "Leonardo Wilhelm DiCaprio",
        "best_known_for": "Leonardo DiCaprio",
        "principal_occupation": "Actor, productor cinematográfico y activista ambiental",
    },
)

# 1.3 Carlos Slim Helú (Involucrado directo en el acuerdo de Los Pinos)
slim_id = get_or_create_person(
    PersonInput(
        name="Carlos Slim",
        aliases=["Carlos Slim Helú"],
        description=(
            "Ingeniero y magnate empresarial mexicano, presidente honorario de Grupo Carso y presidente de la Fundación Carlos Slim. "
            "Reconocido filántropo en proyectos de conservación ambiental, educación y salud."
        ),
        country="MX",
        city_born="Ciudad de México",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Carlos_Slim_2011.jpg/800px-Carlos_Slim_2011.jpg",
        wikidata_id="Q170419",
        birth=HistoricalDate(year=1940, month=1, day=28, precision="day"),
    ),
    {
        "real_name": "Carlos Slim Helú",
        "best_known_for": "Carlos Slim",
        "principal_occupation": "Empresario y filántropo, presidente de Fundación Carlos Slim",
    },
)

# 1.4 Samuel L. Jackson
jackson_id = get_or_create_person(
    PersonInput(
        name="Samuel L. Jackson",
        aliases=["Samuel Leroy Jackson"],
        description=(
            "Prolífico actor y productor de cine estadounidense, galardonado con el Óscar honorífico en 2022. "
            "Uno de los actores más taquilleros en la historia del cine mundial, célebre por sus papeles en cine dramático y en el Universo Cinematográfico de Marvel."
        ),
        country="US",
        city_born="Washington",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Samuel_L._Jackson_2019_by_Glenn_Francis.jpg/800px-Samuel_L._Jackson_2019_by_Glenn_Francis.jpg",
        wikidata_id="Q172678",
        birth=HistoricalDate(year=1948, month=12, day=21, precision="day"),
    ),
    {
        "real_name": "Samuel Leroy Jackson",
        "best_known_for": "Samuel L. Jackson",
        "principal_occupation": "Actor y productor cinematográfico",
    },
)

# 1.5 Quentin Tarantino (Director de Django Unchained)
tarantino_id = get_or_create_person(
    PersonInput(
        name="Quentin Tarantino",
        aliases=["Quentin Jerome Tarantino"],
        description=(
            "Director de cine, guionista y productor estadounidense, ganador de dos Premios Óscar al mejor guion original y de la Palma de Oro en Cannes. "
            "Director de 'Django Unchained', 'Pulp Fiction' e 'Inglourious Basterds'."
        ),
        country="US",
        city_born="Knoxville",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Quentin_Tarantino_by_Gage_Skidmore.jpg/800px-Quentin_Tarantino_by_Gage_Skidmore.jpg",
        wikidata_id="Q3772",
        birth=HistoricalDate(year=1963, month=3, day=27, precision="day"),
    ),
    {
        "real_name": "Quentin Jerome Tarantino",
        "best_known_for": "Quentin Tarantino",
        "principal_occupation": "Director de cine y guionista",
    },
)

# 1.6 Emilia Clarke
clarke_id = get_or_create_person(
    PersonInput(
        name="Emilia Clarke",
        aliases=["Emilia Isobel Euphemia Rose Clarke"],
        description=(
            "Aclamada actriz británica de cine, televisión y teatro. Mundialmente reconocida por su papel protagónico de Daenerys Targaryen en 'Game of Thrones' "
            "y de G'iah en 'Secret Invasion'. Nombrada Miembro de la Orden del Imperio Británico (MBE) en 2024."
        ),
        country="GB",
        city_born="Londres",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d5/Emilia_Clarke_by_Gage_Skidmore_2.jpg/800px-Emilia_Clarke_by_Gage_Skidmore_2.jpg",
        wikidata_id="Q235196",
        birth=HistoricalDate(year=1986, month=10, day=23, precision="day"),
    ),
    {
        "real_name": "Emilia Isobel Euphemia Rose Clarke",
        "best_known_for": "Emilia Clarke",
        "principal_occupation": "Actriz de cine, televisión y teatro",
    },
)

# 1.7 Olivia Colman (Coprotagonista en Secret Invasion)
colman_id = get_or_create_person(
    PersonInput(
        name="Olivia Colman",
        aliases=["Sarah Caroline Colman", "Sarah Caroline Sinclair"],
        description=(
            "Distinguida actriz británica ganadora del Premio Óscar a la mejor actriz ('The Favourite'), cuatro premios BAFTA y tres Globos de Oro. "
            "Coprotagonista estelar junto a Samuel L. Jackson y Emilia Clarke en 'Secret Invasion'."
        ),
        country="GB",
        city_born="Norwich",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Olivia_Colman_2018.jpg/800px-Olivia_Colman_2018.jpg",
        wikidata_id="Q7088045",
        birth=HistoricalDate(year=1974, month=1, day=30, precision="day"),
    ),
    {
        "real_name": "Sarah Caroline Sinclair",
        "best_known_for": "Olivia Colman",
        "principal_occupation": "Actriz de cine y televisión",
    },
)

# ==============================================================================
# 2. OBRAS (Contextos de producciones compartidas)
# ==============================================================================
print("\n--- 2. Verificando / Creando Obras ---")

django_work_id = get_or_create_work(
    WorkInput(
        name="Django Unchained",
        kind="film",
        period=Period(
            start=HistoricalDate(year=2012, precision="year"),
            end=HistoricalDate(year=2012, precision="year"),
        ),
        description="Película de wéstern dramático escrita y dirigida por Quentin Tarantino, coprotagonizada por Leonardo DiCaprio y Samuel L. Jackson.",
    )
)

secret_invasion_work_id = get_or_create_work(
    WorkInput(
        name="Secret Invasion",
        kind="film",
        period=Period(
            start=HistoricalDate(year=2023, precision="year"),
            end=HistoricalDate(year=2023, precision="year"),
        ),
        description="Producción de acción y suspenso del Universo Cinematográfico de Marvel protagonizada por Samuel L. Jackson, Emilia Clarke y Olivia Colman.",
    )
)

# ==============================================================================
# 3. FUENTES DOCUMENTALES (Con ubicaciones precisas)
# ==============================================================================
print("\n--- 3. Verificando / Creando Fuentes Documentales ---")

source_vaquita = get_or_create_source(
    SourceInput(
        title="Firma del Memorando de Entendimiento para la Protección de los Ecosistemas Marinos en el Alto Golfo de California",
        url="https://www.gob.mx/presidencia/prensa/gobierno-de-la-republica-fundacion-leonardo-dicaprio-y-fundacion-carlos-slim-unen-esfuerzos-en-favor-del-alto-golfo-de-california",
        publisher="Presidencia de la República (México) / Comunicación Social",
        author="Gobierno de la República",
        location=LocationInput(
            name="Residencia Oficial de Los Pinos",
            city="Ciudad de México",
            country="MX",
            lat=19.4158,
            lng=-99.1928,
        ),
    )
)

source_django = get_or_create_source(
    SourceInput(
        title="Django Unchained Official Production Notes and Academy Awards Credits",
        url="https://www.oscars.org/oscars/ceremonies/2013",
        publisher="The Weinstein Company / Columbia Pictures / AMPAS",
        author="Academy of Motion Picture Arts and Sciences",
        location=LocationInput(
            name="Dolby Theatre / Second Line Stages",
            city="Los Ángeles",
            country="US",
            lat=34.1016,
            lng=-118.3401,
        ),
    )
)

source_secret_invasion = get_or_create_source(
    SourceInput(
        title="Marvel Studios: Secret Invasion Official Press Kit and Cast Credits",
        url="https://www.marvel.com/tv-shows/secret-invasion/1",
        publisher="Marvel Studios / Walt Disney Studios",
        author="Marvel Communications",
        location=LocationInput(
            name="Pinewood Studios",
            city="Londres",
            country="GB",
            lat=51.5492,
            lng=-0.5372,
        ),
    )
)

source_queen_epn = get_or_create_source(
    SourceInput(
        title="State Visit of the President of the United Mexican States to the United Kingdom",
        url="https://www.royal.uk/state-visit-mexico-2015",
        publisher="The Royal Family / Buckingham Palace Court Circular",
        author="Royal Communications",
        location=LocationInput(
            name="Buckingham Palace",
            city="Londres",
            country="GB",
            lat=51.5014,
            lng=-0.1419,
        ),
    )
)

# ==============================================================================
# 4. HECHOS (Fechas por año para producciones, fecha completa para cumbres/banquetes)
# ==============================================================================
print("\n--- 4. Conectando Hechos con Fechas y Lugares ---")

# 4.1 CUMBRE AMBIENTAL: Enrique Peña Nieto <-> Leonardo DiCaprio (Fecha completa: 7 de junio de 2017)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=epn_id,
        object_id=dicaprio_id,
        period=Period(
            start=HistoricalDate(year=2017, month=6, day=7, precision="day"),
            end=HistoricalDate(year=2017, month=6, day=7, precision="day"),
        ),
        source_id=source_vaquita,
        source_locator="Boletín oficial de Presidencia, 7 de junio de 2017; Firma del Memorando de Entendimiento en el Salón Adolfo López Mateos de Los Pinos.",
        note=(
            "El presidente Enrique Peña Nieto y el actor y ambientalista Leonardo DiCaprio se reunieron el 7 de junio de 2017 "
            "en la Residencia Oficial de Los Pinos para firmar un histórico acuerdo trilateral con el fin de salvar a la vaquita marina "
            "y prohibir de forma permanente las redes de enmalle en el Alto Golfo de California."
        ),
        status="draft",
        location=LocationInput(
            name="Residencia Oficial de Los Pinos",
            city="Ciudad de México",
            country="MX",
            lat=19.4158,
            lng=-99.1928,
        ),
    )
)

# 4.2 CUMBRE AMBIENTAL: Enrique Peña Nieto <-> Carlos Slim (Fecha completa: 7 de junio de 2017)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=epn_id,
        object_id=slim_id,
        period=Period(
            start=HistoricalDate(year=2017, month=6, day=7, precision="day"),
            end=HistoricalDate(year=2017, month=6, day=7, precision="day"),
        ),
        source_id=source_vaquita,
        source_locator="Boletín oficial de Presidencia, 7 de junio de 2017; Salón Adolfo López Mateos de Los Pinos.",
        note=(
            "El presidente Enrique Peña Nieto y Carlos Slim Helú, presidente de la Fundación Carlos Slim, se reunieron en Los Pinos el 7 de junio de 2017 "
            "para coordinar el financiamiento y la reconversión de artes de pesca en el hábitat de la vaquita marina."
        ),
        status="draft",
        location=LocationInput(
            name="Residencia Oficial de Los Pinos",
            city="Ciudad de México",
            country="MX",
            lat=19.4158,
            lng=-99.1928,
        ),
    )
)

# 4.3 CUMBRE AMBIENTAL: Leonardo DiCaprio <-> Carlos Slim (Fecha completa: 7 de junio de 2017)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=dicaprio_id,
        object_id=slim_id,
        period=Period(
            start=HistoricalDate(year=2017, month=6, day=7, precision="day"),
            end=HistoricalDate(year=2017, month=6, day=7, precision="day"),
        ),
        source_id=source_vaquita,
        source_locator="Boletín oficial de Presidencia, 7 de junio de 2017; Alianza Fundación Leonardo DiCaprio y Fundación Carlos Slim.",
        note=(
            "Leonardo DiCaprio y Carlos Slim colaboraron directamente en la cumbre de Los Pinos del 7 de junio de 2017 "
            "para comprometer fondos conjuntos en favor de la biodiversidad marina y el desarrollo comunitario sustentable en el Golfo de California."
        ),
        status="draft",
        location=LocationInput(
            name="Residencia Oficial de Los Pinos",
            city="Ciudad de México",
            country="MX",
            lat=19.4158,
            lng=-99.1928,
        ),
    )
)

# 4.4 CINE: Leonardo DiCaprio en Django Unchained (2012)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=dicaprio_id,
        object_id=django_work_id,
        role="actor",
        period=Period(
            start=HistoricalDate(year=2012, precision="year"),
            end=HistoricalDate(year=2012, precision="year"),
        ),
        source_id=source_django,
        source_locator="Créditos oficiales de 'Django Unchained', papel de Calvin J. Candie.",
        note="Leonardo DiCaprio interpretó al hacendado antagonista Calvin J. Candie en 'Django Unchained' (2012), dirigida por Quentin Tarantino.",
        status="draft",
        location=LocationInput(
            name="Evergreen Plantation y Second Line Stages",
            city="Nueva Orleans",
            country="US",
            lat=29.9511,
            lng=-90.0715,
        ),
    )
)

# 4.5 CINE: Samuel L. Jackson en Django Unchained (2012)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=jackson_id,
        object_id=django_work_id,
        role="actor",
        period=Period(
            start=HistoricalDate(year=2012, precision="year"),
            end=HistoricalDate(year=2012, precision="year"),
        ),
        source_id=source_django,
        source_locator="Créditos oficiales de 'Django Unchained', papel de Stephen.",
        note="Samuel L. Jackson interpretó al leal mayordomo Stephen en 'Django Unchained' (2012), compartiendo múltiples escenas clave con Leonardo DiCaprio.",
        status="draft",
        location=LocationInput(
            name="Evergreen Plantation y Second Line Stages",
            city="Nueva Orleans",
            country="US",
            lat=29.9511,
            lng=-90.0715,
        ),
    )
)

# 4.6 CINE: Quentin Tarantino director de Django Unchained (2012)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=tarantino_id,
        object_id=django_work_id,
        role="director",
        period=Period(
            start=HistoricalDate(year=2012, precision="year"),
            end=HistoricalDate(year=2012, precision="year"),
        ),
        source_id=source_django,
        source_locator="Créditos oficiales de 'Django Unchained', dirección y guion original.",
        note="Quentin Tarantino escribió y dirigió el largometraje 'Django Unchained' (2012), reuniendo en el reparto a Leonardo DiCaprio y Samuel L. Jackson.",
        status="draft",
        location=LocationInput(
            name="Second Line Stages",
            city="Nueva Orleans",
            country="US",
            lat=29.9511,
            lng=-90.0715,
        ),
    )
)

# 4.7 PRODUCCIÓN: Samuel L. Jackson en Secret Invasion (2023)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=jackson_id,
        object_id=secret_invasion_work_id,
        role="actor",
        period=Period(
            start=HistoricalDate(year=2023, precision="year"),
            end=HistoricalDate(year=2023, precision="year"),
        ),
        source_id=source_secret_invasion,
        source_locator="Créditos de 'Secret Invasion' (Marvel Studios, 2023), papel protagónico de Nick Fury.",
        note="Samuel L. Jackson protagonizó 'Secret Invasion' como el veterano director de espionaje Nick Fury.",
        status="draft",
        location=LocationInput(
            name="Pinewood Studios",
            city="Londres",
            country="GB",
            lat=51.5492,
            lng=-0.5372,
        ),
    )
)

# 4.8 PRODUCCIÓN: Emilia Clarke en Secret Invasion (2023)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=clarke_id,
        object_id=secret_invasion_work_id,
        role="actor",
        period=Period(
            start=HistoricalDate(year=2023, precision="year"),
            end=HistoricalDate(year=2023, precision="year"),
        ),
        source_id=source_secret_invasion,
        source_locator="Créditos de 'Secret Invasion' (Marvel Studios, 2023), papel protagónico estelar de G'iah.",
        note="Emilia Clarke coprotagonizó 'Secret Invasion' interpretando a G'iah, compartiendo roles principales y escenas cruciales con Samuel L. Jackson.",
        status="draft",
        location=LocationInput(
            name="Pinewood Studios",
            city="Londres",
            country="GB",
            lat=51.5492,
            lng=-0.5372,
        ),
    )
)

# 4.9 PRODUCCIÓN: Olivia Colman en Secret Invasion (2023)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=colman_id,
        object_id=secret_invasion_work_id,
        role="actor",
        period=Period(
            start=HistoricalDate(year=2023, precision="year"),
            end=HistoricalDate(year=2023, precision="year"),
        ),
        source_id=source_secret_invasion,
        source_locator="Créditos de 'Secret Invasion' (Marvel Studios, 2023), papel de la agente Sonya Falsworth.",
        note="Olivia Colman coprotagonizó 'Secret Invasion' como la astuta agente británica Sonya Falsworth junto a Samuel L. Jackson y Emilia Clarke.",
        status="draft",
        location=LocationInput(
            name="Pinewood Studios",
            city="Londres",
            country="GB",
            lat=51.5492,
            lng=-0.5372,
        ),
    )
)

# 4.10 ANCLAJE REAL: Enrique Peña Nieto <-> Isabel II del Reino Unido (Fecha completa: 3 de marzo de 2015)
queen_existing = None
with driver.session() as session:
    queen_existing = session.execute_read(
        find_existing_person,
        "Q9682",
        "Isabel II del Reino Unido",
    )

if queen_existing:
    print(f"\n[ANCLAJE AL GRAFO GLOBAL] Vinculando Enrique Peña Nieto con Isabel II ({queen_existing['id']})...")
    get_or_create_verified_fact(
        FactInput(
            type_id="personal.met",
            subject_id=epn_id,
            object_id=queen_existing["id"],
            period=Period(
                start=HistoricalDate(year=2015, month=3, day=3, precision="day"),
                end=HistoricalDate(year=2015, month=3, day=3, precision="day"),
            ),
            source_id=source_queen_epn,
            source_locator="Court Circular de Buckingham Palace, 3 de marzo de 2015; Ceremonia oficial de bienvenida en Horse Guards Parade y Banquete de Estado.",
            note=(
                "La reina Isabel II y el duque de Edimburgo recibieron en Visita de Estado al presidente de México Enrique Peña Nieto "
                "el 3 de marzo de 2015, celebrando la ceremonia oficial de bienvenida con guardia de honor y el banquete de Estado en el Palacio de Buckingham."
            ),
            status="draft",
            location=LocationInput(
                name="Buckingham Palace",
                city="Londres",
                country="GB",
                lat=51.5014,
                lng=-0.1419,
            ),
        )
    )

# ==============================================================================
# 5. VERIFICACIÓN DEL CAMINO MÁS CORTO EN NEO4J
# ==============================================================================
print("\n================================================================================")
print("  CONSULTANDO CAMINO MÁS CORTO: ENRIQUE PEÑA NIETO -> EMILIA CLARKE")
print("================================================================================")

with driver.session() as session:
    res = session.run(
        """
        MATCH (start:Person {id: $start_id}), (target:Person {id: $target_id})
        MATCH p = shortestPath((start)-[:SUBJECT_OF|OBJECT*]-(target))
        RETURN [n IN nodes(p) | 
            CASE 
                WHEN 'Person' IN labels(n) THEN {
                    tipo: 'Person', 
                    id: n.id, 
                    nombre: coalesce(n.search_name, n.real_name, n.name), 
                    wikidata: n.wikidata_id
                }
                WHEN 'Work' IN labels(n) THEN {
                    tipo: 'Work', 
                    id: n.id, 
                    titulo: n.search_name
                }
                WHEN 'Fact' IN labels(n) THEN {
                    tipo: 'Fact', 
                    id: n.id, 
                    type_id: n.type_id, 
                    status: n.status, 
                    ubicacion: n.location_name,
                    ciudad: n.city,
                    pais: n.country
                }
                ELSE {tipo: labels(n)[0], id: n.id}
            END
        ] AS camino,
        length(p) AS longitud_relaciones
        """,
        start_id=epn_id,
        target_id=clarke_id,
    ).single()

    if res:
        print(f"Camino encontrado! Longitud de relaciones: {res['longitud_relaciones']}")
        for step in res["camino"]:
            print(" ", json.dumps(step, ensure_ascii=False))
    else:
        print("ERROR: No se encontró camino.")

print("\n--- Validando vistas de conexión derivadas (connection_preview) ---")
for person_name, pid in [("Enrique Peña Nieto", epn_id), ("Leonardo DiCaprio", dicaprio_id), ("Samuel L. Jackson", jackson_id), ("Emilia Clarke", clarke_id)]:
    print(f"\nConexiones directas derivadas de {person_name}:")
    conns = connection_preview(repo, pid)
    for c in conns:
        other = repo.get("people", c["person_id"])
        ctx_name = ""
        if c.get("context_id"):
            try:
                ctx_name = f" mediante {repo.get('works', c['context_id']).get('name')}"
            except Exception:
                pass
        print(f"  -> {c['type_id']} con {other.get('name')}{ctx_name} ({c['direction']})")
