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
print("  CARGA DE ONE DIRECTION Y RELACIONES CURIOSAS/DIVERTIDAS EN NEO4J")
print("================================================================================")

# ==============================================================================
# 1. MIEMBROS DE ONE DIRECTION Y FIGURAS NUEVAS/EXISTENTES
# ==============================================================================
print("\n--- 1. Verificando / Creando Personas ---")

# 1.1 Harry Styles
harry_id = get_or_create_person(
    PersonInput(
        name="Harry Styles",
        aliases=["Harry Edward Styles", "Hazza"],
        description=(
            "Cantante, compositor y actor británico. Miembro de One Direction y aclamado solista internacional "
            "ganador de 3 premios Grammy. Famoso por elogiar el cabello de la reina Isabel II en persona en 2012."
        ),
        country="GB",
        city_born="Redditch",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d9/Harry_Styles_November_2014.jpg/800px-Harry_Styles_November_2014.jpg",
        wikidata_id="Q362696",
        birth=HistoricalDate(year=1994, month=2, day=1, precision="day"),
    ),
    {
        "real_name": "Harry Edward Styles",
        "best_known_for": "Harry Styles",
        "principal_occupation": "Cantante, compositor y actor",
    },
)

# 1.2 Zayn Malik
zayn_id = get_or_create_person(
    PersonInput(
        name="Zayn Malik",
        aliases=["Zayn", "Zain Javadd Malik"],
        description=(
            "Cantante y compositor británico. Miembro de One Direction (2010–2015) y posteriormente exitoso solista pop/R&B. "
            "Representó el elemento 'Misterio' en el memorable videoclip dirigido por Danny DeVito."
        ),
        country="GB",
        city_born="Bradford",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/1/10/Zayn_Malik_in_2015.jpg/800px-Zayn_Malik_in_2015.jpg",
        wikidata_id="Q361233",
        birth=HistoricalDate(year=1993, month=1, day=12, precision="day"),
    ),
    {
        "real_name": "Zain Javadd Malik",
        "best_known_for": "Zayn Malik",
        "principal_occupation": "Cantante y compositor",
    },
)

# 1.3 Liam Payne
liam_id = get_or_create_person(
    PersonInput(
        name="Liam Payne",
        aliases=["Liam James Payne", "Payno"],
        description=(
            "Cantante, guitarrista y compositor británico. Miembro clave y coautor prolífico de One Direction. "
            "Famoso por relatar la anécdota de cuando Donald Trump expulsó a la banda de su hotel en Nueva York en 2012."
        ),
        country="GB",
        city_born="Wolverhampton",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/ad/Liam_Payne_2019.png/800px-Liam_Payne_2019.png",
        wikidata_id="Q262071",
        birth=HistoricalDate(year=1993, month=8, day=29, precision="day"),
        death=HistoricalDate(year=2024, month=10, day=16, precision="day"),
    ),
    {
        "real_name": "Liam James Payne",
        "best_known_for": "Liam Payne",
        "principal_occupation": "Cantante y compositor",
    },
)

# 1.4 Louis Tomlinson
louis_id = get_or_create_person(
    PersonInput(
        name="Louis Tomlinson",
        aliases=["Louis William Tomlinson", "Tommo"],
        description=(
            "Cantante, compositor y personalidad televisiva británico. Miembro de One Direction y el mayor acreditado "
            "en composición del grupo. Asignado el elemento 'Peligro' por Danny DeVito en 'Steal My Girl'."
        ),
        country="GB",
        city_born="Doncaster",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Louis_Tomlinson_2014.jpg/800px-Louis_Tomlinson_2014.jpg",
        wikidata_id="Q362497",
        birth=HistoricalDate(year=1991, month=12, day=24, precision="day"),
    ),
    {
        "real_name": "Louis William Tomlinson",
        "best_known_for": "Louis Tomlinson",
        "principal_occupation": "Cantante y compositor",
    },
)

# 1.5 Niall Horan
niall_id = get_or_create_person(
    PersonInput(
        name="Niall Horan",
        aliases=["Niall James Horan", "Nialler"],
        description=(
            "Cantante, compositor y guitarrista irlandés. Miembro de One Direction y ferviente apasionado del fútbol, "
            "quien visitó los vestuarios del Manchester United para convivir con Wayne Rooney en Chicago en 2015."
        ),
        country="IE",
        city_born="Mullingar",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/Niall_Horan_2019_by_Glenn_Francis.jpg/800px-Niall_Horan_2019_by_Glenn_Francis.jpg",
        wikidata_id="Q362686",
        birth=HistoricalDate(year=1993, month=9, day=13, precision="day"),
    ),
    {
        "real_name": "Niall James Horan",
        "best_known_for": "Niall Horan",
        "principal_occupation": "Cantautor y músico",
    },
)

# 1.6 Simon Cowell
cowell_id = get_or_create_person(
    PersonInput(
        name="Simon Cowell",
        aliases=["Simon Phillip Cowell"],
        description=(
            "Ejecutivo discográfico, productor y personalidad televisiva británica. Creador de The X Factor y Got Talent, "
            "quien concibió, formó y apadrinó como mentor a One Direction en Londres en julio de 2010."
        ),
        country="GB",
        city_born="Londres",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Simon_Cowell_at_Red_Carpet_America%27s_Got_Talent_Season_18_September_2023.jpg/800px-Simon_Cowell_at_Red_Carpet_America%27s_Got_Talent_Season_18_September_2023.jpg",
        wikidata_id="Q162629",
        birth=HistoricalDate(year=1959, month=10, day=7, precision="day"),
    ),
    {
        "real_name": "Simon Phillip Cowell",
        "best_known_for": "Simon Cowell",
        "principal_occupation": "Productor musical y jurado televisivo",
    },
)

# 1.7 Danny DeVito
devito_id = get_or_create_person(
    PersonInput(
        name="Danny DeVito",
        aliases=["Daniel Michael DeVito Jr."],
        description=(
            "Aclamado actor, comediante y director de cine estadounidense. Ganador del Globo de Oro y del Emmy. "
            "Sorprendió al mundo al coprotagonizar como excéntrico director el video surrealista 'Steal My Girl' de One Direction en 2014."
        ),
        country="US",
        city_born="Neptune Township",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Danny_DeVito_by_Gage_Skidmore.jpg/800px-Danny_DeVito_by_Gage_Skidmore.jpg",
        wikidata_id="Q26805",
        birth=HistoricalDate(year=1944, month=11, day=17, precision="day"),
    ),
    {
        "real_name": "Daniel Michael DeVito Jr.",
        "best_known_for": "Danny DeVito",
        "principal_occupation": "Actor, comediante y director de cine",
    },
)

# 1.8 Donald Trump
trump_id = get_or_create_person(
    PersonInput(
        name="Donald Trump",
        aliases=["Donald John Trump", "The Donald"],
        description=(
            "Magnate empresarial, figura de los medios de comunicación y presidente de los Estados Unidos. "
            "Protagonizó una cómica polémica en 2012 al ordenar el desalojo de One Direction de su hotel en Nueva York "
            "cuando los jóvenes músicos prefirieron seguir durmiendo antes que levantarse a saludar a la hija de un conocido."
        ),
        country="US",
        city_born="Nueva York",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/5/56/Donald_Trump_official_portrait_2017.jpg/800px-Donald_Trump_official_portrait_2017.jpg",
        wikidata_id="Q22686",
        birth=HistoricalDate(year=1946, month=6, day=14, precision="day"),
    ),
    {
        "real_name": "Donald John Trump",
        "best_known_for": "Donald Trump",
        "principal_occupation": "Empresario y presidente de los Estados Unidos",
    },
)

# 1.9 Isabel II del Reino Unido (Ya en BD)
elizabeth_id = get_or_create_person(
    PersonInput(
        name="Isabel II del Reino Unido",
        aliases=["Elizabeth II", "Elizabeth Alexandra Mary Windsor"],
        description="Reina del Reino Unido y de los otros reinos de la Mancomunidad de Naciones desde 1952 hasta 2022.",
        country="GB",
        city_born="Londres",
        image_url="https://upload.wikimedia.org/wikipedia/commons/b/b6/Queen_Elizabeth_II_in_March_2015.jpg",
        wikidata_id="Q9682",
        birth=HistoricalDate(year=1926, month=4, day=21, precision="day"),
        death=HistoricalDate(year=2022, month=9, day=8, precision="day"),
    ),
    {
        "real_name": "Elizabeth Alexandra Mary Windsor",
        "best_known_for": "Isabel II del Reino Unido",
        "principal_occupation": "Monarca del Reino Unido y de la Commonwealth",
    },
)

# 1.10 Plácido Domingo (Ya en BD)
placido_id = get_or_create_person(
    PersonInput(
        name="Plácido Domingo",
        aliases=["José Plácido Domingo Embil"],
        description="Cantante lírico, tenor y director de orquesta español.",
        country="ES",
        city_born="Madrid",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Placido_Domingo_2014.jpg/800px-Placido_Domingo_2014.jpg",
        wikidata_id="Q180896",
        birth=HistoricalDate(year=1941, month=1, day=21, precision="day"),
    ),
    {
        "real_name": "José Plácido Domingo Embil",
        "best_known_for": "Plácido Domingo",
        "principal_occupation": "Tenor y director de orquesta lírico",
    },
)

# 1.11 Wayne Rooney (Ya en BD)
rooney_id = get_or_create_person(
    PersonInput(
        name="Wayne Rooney",
        aliases=["Wayne Mark Rooney", "Wazza"],
        description="Exfutbolista y entrenador inglés. Máximo goleador histórico del Manchester United F.C.",
        country="GB",
        city_born="Liverpool",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Wayne_Rooney_2018.jpg/800px-Wayne_Rooney_2018.jpg",
        wikidata_id="Q26659",
        birth=HistoricalDate(year=1985, month=10, day=24, precision="day"),
    ),
    {
        "real_name": "Wayne Mark Rooney",
        "best_known_for": "Wayne Rooney",
        "principal_occupation": "Futbolista profesional y máximo goleador de Manchester United",
    },
)

# ==============================================================================
# 2. FUENTES DOCUMENTADAS CON GEOLOCALIZACIÓN
# ==============================================================================
print("\n--- 2. Verificando / Creando Fuentes Históricas ---")

# Fuente 1: 100th Royal Variety Performance 2012
src_royal_variety = get_or_create_source(
    SourceInput(
        title="Royal Variety Charity - 100th Royal Variety Performance Official Gala (2012)",
        url="https://www.royalvarietycharity.org/the-royal-variety-performance",
        citation="The Royal Variety Charity Official Archives: Centennial Royal Variety Performance, Royal Albert Hall, London, November 19, 2012.",
        author="Royal Variety Charity & BBC",
        publisher="Royal Variety Charity",
        location=LocationInput(
            name="Royal Albert Hall",
            city="Londres",
            country="GB",
            lat=51.5009,
            lng=-0.1774,
        ),
    )
)

# Fuente 2: Simon Cowell y The X Factor 2010
src_xfactor = get_or_create_source(
    SourceInput(
        title="ITV & Syco Entertainment - The X Factor UK Series 7 Formation of One Direction (2010)",
        url="https://www.itv.com/xfactor",
        citation="The X Factor UK Official Broadcast Archives: Bootcamp and Group Category formation by Simon Cowell, Wembley Arena & The O2, London, July 23, 2010.",
        author="Talkback Thames / Syco Music",
        publisher="ITV Studios",
        location=LocationInput(
            name="Wembley Arena",
            city="Londres",
            country="GB",
            lat=51.5582,
            lng=-0.2828,
        ),
    )
)

# Fuente 3: Steal My Girl con Danny DeVito
src_steal_my_girl = get_or_create_source(
    SourceInput(
        title="Los Angeles Times & Syco Music - One Direction 'Steal My Girl' Video Production with Danny DeVito (2014)",
        url="https://www.latimes.com/entertainment/music/la-et-ms-one-direction-steal-my-girl-danny-devito-video-20141024-story.html",
        citation="Los Angeles Times: 'One Direction and Danny DeVito shoot surreal Steal My Girl video in the California desert', Palmdale, September 2014.",
        author="Mikael Wood",
        publisher="Los Angeles Times & Columbia Records",
        location=LocationInput(
            name="Desierto de Palmdale",
            city="Palmdale",
            country="US",
            lat=34.5794,
            lng=-118.1165,
        ),
    )
)

# Fuente 4: Incidente de Donald Trump en Nueva York 2012
src_trump_incident = get_or_create_source(
    SourceInput(
        title="CBS News & Rollacoaster Magazine - Donald Trump Hotel Ejection Incident of One Direction (2012)",
        url="https://www.cbsnews.com/news/liam-payne-donald-trump-kicked-one-direction-out-of-hotel/",
        citation="CBS News & Rollacoaster Magazine Interview with Liam Payne: The 2012 Trump International Hotel ejection in New York City.",
        author="Andrea Park",
        publisher="CBS News",
        location=LocationInput(
            name="Trump International Hotel and Tower",
            city="Nueva York",
            country="US",
            lat=40.7692,
            lng=-73.9818,
        ),
    )
)

# Fuente 5: Niall Horan y Wayne Rooney en Chicago 2015
src_niall_rooney = get_or_create_source(
    SourceInput(
        title="Manchester Evening News - Niall Horan visits Manchester United dressing room and Wayne Rooney (2015)",
        url="https://www.manchestereveningnews.co.uk/news/showbiz-news/one-direction-star-niall-horan-9762693",
        citation="Manchester Evening News: 'One Direction superstar Niall Horan visits Wayne Rooney and Manchester United team at Soldier Field', July 29, 2015.",
        author="Katie Fitzpatrick",
        publisher="Manchester Evening News",
        location=LocationInput(
            name="Soldier Field",
            city="Chicago",
            country="US",
            lat=41.8623,
            lng=-87.6167,
        ),
    )
)

# ==============================================================================
# 3. OBRA COLECTIVA Y EVENTO ARTÍSTICO
# ==============================================================================
print("\n--- 3. Creando Obra y Evento Artístico ---")

# 3.1 Obra Musical: "Steal My Girl" (2014)
work_steal_my_girl_id = get_or_create_work(
    WorkInput(
        name="Steal My Girl",
        kind="music",
        period=Period(
            start=HistoricalDate(year=2014, precision="year"),
            end=HistoricalDate(year=2014, precision="year"),
        ),
        description=(
            "Exitoso sencillo de One Direction perteneciente al álbum Four (2014), cuyo icónico videoclip oficial en el desierto "
            "fue codirigido y protagonizado por Danny DeVito junto a los cinco integrantes de la agrupación."
        ),
    )
)

# 3.2 Evento Artístico: 100th Royal Variety Performance (19 de noviembre de 2012)
event_variety_id = get_or_create_event_with_facts(
    EventInput(
        name="100th Royal Variety Performance",
        kind="arts.performance",
        place="Royal Albert Hall, Londres",
        period=Period(
            start=HistoricalDate(year=2012, month=11, day=19, precision="day"),
            end=HistoricalDate(year=2012, month=11, day=19, precision="day"),
        ),
        source_id=src_royal_variety,
        source_locator="Gala centenaria televisada por la BBC desde el Royal Albert Hall en presencia de SM la Reina Isabel II.",
        location=LocationInput(
            name="Royal Albert Hall",
            city="Londres",
            country="GB",
            lat=51.5009,
            lng=-0.1774,
        ),
        participants=[
            EventParticipantInput(
                type_id="arts.performed_together",
                subject_id=harry_id,
                source_id=src_royal_variety,
                source_locator="Actuación en vivo de One Direction interpretando 'Little Things'.",
                role="performer",
                status="draft",
                note="Harry Styles se presentó en vivo con One Direction en la gala del centenario de la Royal Variety.",
            ),
            EventParticipantInput(
                type_id="arts.performed_together",
                subject_id=zayn_id,
                source_id=src_royal_variety,
                source_locator="Actuación en vivo de One Direction interpretando 'Little Things'.",
                role="performer",
                status="draft",
                note="Zayn Malik se presentó en vivo con One Direction en el Royal Albert Hall.",
            ),
            EventParticipantInput(
                type_id="arts.performed_together",
                subject_id=liam_id,
                source_id=src_royal_variety,
                source_locator="Actuación en vivo de One Direction interpretando 'Little Things'.",
                role="performer",
                status="draft",
                note="Liam Payne cantó en vivo con One Direction ante la Reina Isabel II.",
            ),
            EventParticipantInput(
                type_id="arts.performed_together",
                subject_id=louis_id,
                source_id=src_royal_variety,
                source_locator="Actuación en vivo de One Direction interpretando 'Little Things'.",
                role="performer",
                status="draft",
                note="Louis Tomlinson actuó en vivo con One Direction en la 100.ª Royal Variety Performance.",
            ),
            EventParticipantInput(
                type_id="arts.performed_together",
                subject_id=niall_id,
                source_id=src_royal_variety,
                source_locator="Actuación en vivo de One Direction interpretando 'Little Things'.",
                role="performer",
                status="draft",
                note="Niall Horan tocó la guitarra y cantó en vivo con One Direction en el Royal Albert Hall.",
            ),
            EventParticipantInput(
                type_id="arts.performed_together",
                subject_id=placido_id,
                source_id=src_royal_variety,
                source_locator="Dúo estelar lírico de Plácido Domingo con Katherine Jenkins en la gala centenaria.",
                role="performer",
                status="draft",
                note="Plácido Domingo ofreció un aclamado dúo operístico en el mismo escenario del Royal Albert Hall en la misma velada que One Direction.",
            ),
        ],
    )
)

# ==============================================================================
# 4. HECHOS Y RELACIONES CURIOSAS Y DIRECTAS
# ==============================================================================
print("\n--- 4. Creando Hechos Directos y Relaciones Curiosas ---")

# 4.1 Colaboración en "Steal My Girl" con Danny DeVito (arts.collaborated_on_work)
members_and_roles = [
    (harry_id, "performer", "Harry Styles protagonizó la escena del 'Amor' con bailarinas y Danny DeVito."),
    (zayn_id, "performer", "Zayn Malik coprotagonizó la escena del 'Misterio' con luchadores de sumo y Danny DeVito."),
    (liam_id, "creator", "Liam Payne coescribió y coprotagonizó el sencillo 'Steal My Girl' (rol 'Poder')."),
    (louis_id, "creator", "Louis Tomlinson coescribió y coprotagonizó el sencillo 'Steal My Girl' (rol 'Peligro', con un chimpancé)."),
    (niall_id, "performer", "Niall Horan coprotagonizó la escena de la 'Luz' con danzantes masai y Danny DeVito."),
    (devito_id, "director", "Danny DeVito dirigió artísticamente y protagonizó el video como el director visionario del desierto."),
]

for p_id, role, note in members_and_roles:
    get_or_create_verified_fact(
        FactInput(
            type_id="arts.collaborated_on_work",
            subject_id=p_id,
            object_id=work_steal_my_girl_id,
            role=role,
            period=Period(
                start=HistoricalDate(year=2014, precision="year"),
                end=HistoricalDate(year=2014, precision="year"),
            ),
            source_id=src_steal_my_girl,
            source_locator="Créditos oficiales del videoclip 'Steal My Girl', Syco Music / Columbia Records, 2014.",
            note=note,
            status="draft",
            location=LocationInput(
                name="Desierto de Palmdale",
                city="Palmdale",
                country="US",
                lat=34.5794,
                lng=-118.1165,
            ),
        )
    )

# 4.2 Mentoría de Simon Cowell a los integrantes de One Direction (professional.mentor_of)
for member_id, member_name in [
    (harry_id, "Harry Styles"),
    (zayn_id, "Zayn Malik"),
    (liam_id, "Liam Payne"),
    (louis_id, "Louis Tomlinson"),
    (niall_id, "Niall Horan"),
]:
    get_or_create_verified_fact(
        FactInput(
            type_id="professional.mentor_of",
            subject_id=cowell_id,
            object_id=member_id,
            period=Period(
                start=HistoricalDate(year=2010, precision="year"),
                end=HistoricalDate(year=2015, precision="year"),
            ),
            source_id=src_xfactor,
            source_locator="The X Factor UK 2010: Simon Cowell asignado como mentor de la categoría de grupos.",
            note=(
                f"Simon Cowell ejerció como mentor profesional de {member_name} tras agrupar a One Direction "
                "en The X Factor UK en 2010 y ficharlos para su sello Syco Music."
            ),
            status="draft",
            location=LocationInput(
                name="Wembley Arena",
                city="Londres",
                country="GB",
                lat=51.5582,
                lng=-0.2828,
            ),
        )
    )

# 4.3 Encuentro en la línea de honor con la Reina Isabel II (personal.met, 19 de noviembre de 2012)
for member_id, member_name, extra_anecdote in [
    (harry_id, "Harry Styles", "Harry Styles elogió espontáneamente a Su Majestad diciéndole a la prensa que la Reina tenía 'gran cabello'."),
    (liam_id, "Liam Payne", "Liam Payne saludó formalmente a la soberana británica tras su presentación."),
    (louis_id, "Louis Tomlinson", "Louis Tomlinson estrechó la mano de la Reina Isabel II en la línea de recepción real."),
    (niall_id, "Niall Horan", "Niall Horan charló brevemente con la Reina sobre las próximas fechas de la gira internacional."),
    (zayn_id, "Zayn Malik", "Zayn Malik recibió las felicitaciones de la Reina Isabel II tras el concierto del centenario."),
]:
    get_or_create_verified_fact(
        FactInput(
            type_id="personal.met",
            subject_id=member_id,
            object_id=elizabeth_id,
            period=Period(
                start=HistoricalDate(year=2012, month=11, day=19, precision="day"),
                end=HistoricalDate(year=2012, month=11, day=19, precision="day"),
            ),
            source_id=src_royal_variety,
            source_locator="Línea de honor tras bambalinas en el Royal Albert Hall, 19 de noviembre de 2012.",
            note=(
                f"{member_name} se reunió en persona y conversó con la Reina Isabel II durante el saludo protocolar "
                f"de la 100.ª Royal Variety Performance en el Royal Albert Hall de Londres. {extra_anecdote}"
            ),
            status="draft",
            location=LocationInput(
                name="Royal Albert Hall",
                city="Londres",
                country="GB",
                lat=51.5009,
                lng=-0.1774,
            ),
        )
    )

# 4.4 El cómico y surrealista encontronazo con Donald Trump en Nueva York (2012)
for member_id, member_name in [
    (liam_id, "Liam Payne"),
    (niall_id, "Niall Horan"),
]:
    get_or_create_verified_fact(
        FactInput(
            type_id="personal.met",
            subject_id=trump_id,
            object_id=member_id,
            period=Period(
                start=HistoricalDate(year=2012, precision="year"),
                end=HistoricalDate(year=2012, precision="year"),
            ),
            source_id=src_trump_incident,
            source_locator="Trump International Hotel and Tower, Nueva York, temporada de 2012.",
            note=(
                f"Donald Trump tuvo un cómico desencuentro con One Direction (relatado por {member_name}) en el Trump International "
                "Hotel de Nueva York en 2012: tras pedir que los músicos se despertaran para conocer a la hija de un conocido "
                "y recibir una negativa porque estaban exhaustos durmiendo, Trump les canceló el acceso al garaje y los echó del hotel."
            ),
            status="draft",
            location=LocationInput(
                name="Trump International Hotel and Tower",
                city="Nueva York",
                country="US",
                lat=40.7692,
                lng=-73.9818,
            ),
        )
    )

# 4.5 Encuentro futbolero de Niall Horan con Wayne Rooney (29 de julio de 2015)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=niall_id,
        object_id=rooney_id,
        period=Period(
            start=HistoricalDate(year=2015, month=7, day=29, precision="day"),
            end=HistoricalDate(year=2015, month=7, day=29, precision="day"),
        ),
        source_id=src_niall_rooney,
        source_locator="Vestuarios de Soldier Field, Chicago, tras el partido Manchester United vs PSG, 29 de julio de 2015.",
        note=(
            "Niall Horan, ferviente seguidor del fútbol británico, visitó el vestuario del Manchester United tras su encuentro "
            "amistoso en Chicago y convivió en persona con el capitán histórico Wayne Rooney."
        ),
        status="draft",
        location=LocationInput(
            name="Soldier Field",
            city="Chicago",
            country="US",
            lat=41.8623,
            lng=-87.6167,
        ),
    )
)

# 4.6 Danny DeVito en el set con Harry Styles y Louis Tomlinson (29 de septiembre de 2014)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=devito_id,
        object_id=harry_id,
        period=Period(
            start=HistoricalDate(year=2014, month=9, day=29, precision="day"),
            end=HistoricalDate(year=2014, month=9, day=29, precision="day"),
        ),
        source_id=src_steal_my_girl,
        source_locator="Set de filmación del videoclip 'Steal My Girl' en Palmdale, California, 29 de septiembre de 2014.",
        note=(
            "Danny DeVito y Harry Styles compartieron el set de rodaje en el desierto de Palmdale el 29 de septiembre de 2014, "
            "donde DeVito instruyó a Harry en su interpretación del 'Amor' con un abrigo de leopardo y bailarinas de ballet."
        ),
        status="draft",
        location=LocationInput(
            name="Desierto de Palmdale",
            city="Palmdale",
            country="US",
            lat=34.5794,
            lng=-118.1165,
        ),
    )
)

get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=devito_id,
        object_id=louis_id,
        period=Period(
            start=HistoricalDate(year=2014, month=9, day=29, precision="day"),
            end=HistoricalDate(year=2014, month=9, day=29, precision="day"),
        ),
        source_id=src_steal_my_girl,
        source_locator="Set de filmación en Palmdale, California, 29 de septiembre de 2014.",
        note=(
            "Danny DeVito interactuó y grabó junto a Louis Tomlinson en el desierto de Palmdale, asignándole el concepto 'Peligro' "
            "junto a un chimpancé amaestrado."
        ),
        status="draft",
        location=LocationInput(
            name="Desierto de Palmdale",
            city="Palmdale",
            country="US",
            lat=34.5794,
            lng=-118.1165,
        ),
    )
)

# ==============================================================================
# 5. VERIFICACIÓN Y PREVIEWS EN EL GRAFO
# ==============================================================================
print("\n--- 5. Verificando Conexiones Derivadas ---")

for member_id, member_name in [
    (harry_id, "Harry Styles"),
    (niall_id, "Niall Horan"),
    (liam_id, "Liam Payne"),
]:
    print(f"\n[Conexiones derivadas para {member_name}]:")
    preview = connection_preview(repo, member_id)
    for conn in preview:
        target_person = repo.get("people", conn["person_id"])
        target_name = target_person.get("search_name") or target_person.get("name")
        loc_name = conn.get("location", {}).get("name") if conn.get("location") else "N/A"
        print(f"  -> Conectado con: {target_name} vía {conn['type_id']} ({loc_name})")

print("\n--- Conexiones derivadas para Danny DeVito ---")
preview_devito = connection_preview(repo, devito_id)
for conn in preview_devito:
    target_person = repo.get("people", conn["person_id"])
    target_name = target_person.get("search_name") or target_person.get("name")
    print(f"  -> Conectado con: {target_name} vía {conn['type_id']}")

print("\n--- Verificando caminos más cortos curiosos ---")
with driver.session() as session:
    # Camino Harry Styles -> Chicharito
    chicha_res = session.run(
        """
        MATCH (chicha:Person {wikidata_id: 'Q186438'}), (harry:Person {id: $h_id})
        MATCH path = shortestPath((harry)-[*..12]-(chicha))
        RETURN [node IN nodes(path) | coalesce(node.search_name, node.name, labels(node)[0])] AS names,
               length(path) AS hops
        """,
        h_id=harry_id,
    ).single()
    if chicha_res:
        print(f"Camino Harry Styles -> Chicharito: {chicha_res['hops']} saltos: {' -> '.join(chicha_res['names'])}")

    # Camino Donald Trump -> Nikola Tesla
    tesla_res = session.run(
        """
        MATCH (tesla:Person {wikidata_id: 'Q9036'}), (trump:Person {id: $t_id})
        MATCH path = shortestPath((trump)-[*..15]-(tesla))
        RETURN [node IN nodes(path) | coalesce(node.search_name, node.name, labels(node)[0])] AS names,
               length(path) AS hops
        """,
        t_id=trump_id,
    ).single()
    if tesla_res:
        print(f"Camino Donald Trump -> Nikola Tesla: {tesla_res['hops']} saltos: {' -> '.join(tesla_res['names'])}")

print("\n================================================================================")
print("  CARGA DE ONE DIRECTION COMPLETADA CON ÉXITO")
print("================================================================================")
