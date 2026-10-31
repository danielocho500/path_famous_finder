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
print("  CONEXIÓN EXPLICABLE: PESO PLUMA -> LALISA (LISA)")
print("================================================================================")

# ==============================================================================
# 1. PERSONAS (Verificadas antes de crear para evitar duplicados)
# ==============================================================================
print("\n--- 1. Verificando / Creando Personas ---")

# 1.1 Peso Pluma
peso_pluma_id = get_or_create_person(
    PersonInput(
        name="Peso Pluma",
        aliases=["Hassan Emilio Kabande Laija", "La Doble P"],
        description=(
            "Cantante y compositor mexicano, referente e icono global del movimiento de corridos tumbados "
            "y música regional mexicana urbana. Ganador del Premio Grammy."
        ),
        country="MX",
        city_born="Zapopan",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Peso_Pluma_at_the_2023_MTV_Video_Music_Awards.png/800px-Peso_Pluma_at_the_2023_MTV_Video_Music_Awards.png",
        wikidata_id="Q117355204",
        birth=HistoricalDate(year=1999, month=6, day=15, precision="day"),
    ),
    {
        "real_name": "Hassan Emilio Kabande Laija",
        "best_known_for": "Peso Pluma",
        "principal_occupation": "Cantante y compositor de música regional mexicana y urbana",
    },
)

# 1.2 Lalisa (Lisa de BLACKPINK)
lalisa_id = get_or_create_person(
    PersonInput(
        name="Lalisa",
        aliases=["Lisa", "Lalisa Manobal", "Pranpriya Manobal", "Lisa de BLACKPINK"],
        description=(
            "Rapera, cantante y bailarina tailandesa radicada en Corea del Sur. Miembro estelar del fenómeno global "
            "de K-pop BLACKPINK y exitosa solista con múltiples récords Guinness y premios MTV VMA."
        ),
        country="TH",
        city_born="Buriram",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Lalisa_Manobal_at_Bvlgari_event_in_2023.jpg/800px-Lalisa_Manobal_at_Bvlgari_event_in_2023.jpg",
        wikidata_id="Q24039860",
        birth=HistoricalDate(year=1997, month=3, day=27, precision="day"),
    ),
    {
        "real_name": "Lalisa Manobal",
        "best_known_for": "Lalisa",
        "principal_occupation": "Rapera, cantante y bailarina de BLACKPINK y solista internacional",
    },
)

# 1.3 DJ Snake
dj_snake_id = get_or_create_person(
    PersonInput(
        name="DJ Snake",
        aliases=["William Sami Étienne Grigahcine", "William Grigahcine"],
        description=(
            "DJ, compositor y productor musical francés de música electrónica y urbana, nominado al Grammy. "
            "Puente global que colaboró tanto con Lalisa ('SG') como con Peso Pluma ('Teka')."
        ),
        country="FR",
        city_born="París",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/DJ_Snake_Cannes_2018.jpg/800px-DJ_Snake_Cannes_2018.jpg",
        wikidata_id="Q15964227",
        birth=HistoricalDate(year=1986, month=6, day=13, precision="day"),
    ),
    {
        "real_name": "William Sami Étienne Grigahcine",
        "best_known_for": "DJ Snake",
        "principal_occupation": "DJ y productor discográfico internacional",
    },
)

# 1.4 Anitta
anitta_id = get_or_create_person(
    PersonInput(
        name="Anitta",
        aliases=["Larissa de Macedo Machado"],
        description=(
            "Cantante, compositora y empresaria brasileña, máxima referente internacional del funk carioca y pop latino. "
            "Colaboró con Peso Pluma en 'BELLAKEO' y compartió momentos memorables con Lisa de BLACKPINK en los MTV VMAs."
        ),
        country="BR",
        city_born="Río de Janeiro",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/Anitta_at_the_2023_MTV_Video_Music_Awards.png/800px-Anitta_at_the_2023_MTV_Video_Music_Awards.png",
        wikidata_id="Q35964",
        birth=HistoricalDate(year=1993, month=3, day=30, precision="day"),
    ),
    {
        "real_name": "Larissa de Macedo Machado",
        "best_known_for": "Anitta",
        "principal_occupation": "Cantautora, bailarina y empresaria",
    },
)

# 1.5 Rosalía
rosalia_id = get_or_create_person(
    PersonInput(
        name="Rosalía",
        aliases=["Rosalía Vila Tobella", "La Rosalía"],
        description=(
            "Cantautora y productora española aclamada mundialmente por su innovadora fusión de flamenco tradicional con sonidos urbanos. "
            "Colaboró con Lalisa (Lisa) en el sencillo global 'New Woman' (2024)."
        ),
        country="ES",
        city_born="San Cugat del Vallés",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/Rosalia_Grammys_2020.png/800px-Rosalia_Grammys_2020.png",
        wikidata_id="Q56322301",
        birth=HistoricalDate(year=1992, month=9, day=25, precision="day"),
    ),
    {
        "real_name": "Rosalía Vila Tobella",
        "best_known_for": "Rosalía",
        "principal_occupation": "Cantautora y productora musical",
    },
)

# 1.6 Javier "Chicharito" Hernández (Ya en BD)
chicharito_id = get_or_create_person(
    PersonInput(
        name="Javier Hernández",
        aliases=["Chicharito", "Javier Hernández Balcázar", "Chicharito Hernández"],
        description="Futbolista profesional mexicano y máximo goleador histórico de la Selección Mexicana.",
        country="MX",
        city_born="Guadalajara",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/Javier_Hern%C3%A1ndez_2018.jpg/800px-Javier_Hern%C3%A1ndez_2018.jpg",
        wikidata_id="Q186438",
        birth=HistoricalDate(year=1988, month=6, day=1, precision="day"),
    ),
    {
        "real_name": "Javier Hernández Balcázar",
        "best_known_for": "Chicharito",
        "principal_occupation": "Futbolista profesional y máximo goleador de México",
    },
)

# ==============================================================================
# 2. FUENTES DOCUMENTADAS CON GEOLOCALIZACIÓN
# ==============================================================================
print("\n--- 2. Verificando / Creando Fuentes Históricas ---")

# Fuente 1: "Teka" (DJ Snake & Peso Pluma en Coachella)
src_teka = get_or_create_source(
    SourceInput(
        title="EDM.com & Interscope Records - DJ Snake and Peso Pluma 'Teka' Coachella Premiere (2024)",
        url="https://edm.com/music-releases/dj-snake-peso-pluma-teka-coachella",
        citation="EDM.com & Interscope Records: Live premiere of 'Teka' by DJ Snake featuring Peso Pluma at Coachella Sahara Stage, Indio, California, April 14, 2024.",
        author="EDM.com Editorial",
        publisher="Interscope Records / Universal Music",
        location=LocationInput(
            name="Empire Polo Club",
            city="Indio",
            country="US",
            lat=33.6799,
            lng=-116.2372,
        ),
    )
)

# Fuente 2: "SG" (DJ Snake, Lisa, Ozuna, Megan Thee Stallion)
src_sg = get_or_create_source(
    SourceInput(
        title="Rolling Stone & Interscope Records - DJ Snake, Ozuna, Megan Thee Stallion and Lisa 'SG' (2021)",
        url="https://www.rollingstone.com/music/music-news/dj-snake-ozuna-megan-thee-stallion-lisa-sg-video-1246141/",
        citation="Rolling Stone Official Review: 'SG' collaborative music video directed by Colin Tilley, starring DJ Snake, Ozuna, Megan Thee Stallion, and Lisa, October 22, 2021.",
        author="Althea Legaspi",
        publisher="Rolling Stone & Interscope Records",
        location=LocationInput(
            name="South Beach Studios",
            city="Miami",
            country="US",
            lat=25.7617,
            lng=-80.1918,
        ),
    )
)

# Fuente 3: "BELLAKEO" (Peso Pluma & Anitta en TikTok In The Mix)
src_bellakeo = get_or_create_source(
    SourceInput(
        title="Billboard & TikTok - Peso Pluma and Anitta Live Premiere of BELLAKEO (2023)",
        url="https://www.billboard.com/music/latin/peso-pluma-anitta-bellakeo-tiktok-in-the-mix-1235552309/",
        citation="Billboard Latin: 'Peso Pluma and Anitta Heat Up TikTok In The Mix with Live Debut of BELLAKEO', Sloan Park, Mesa, Arizona, December 10, 2023.",
        author="Griselda Flores",
        publisher="Billboard & TikTok",
        location=LocationInput(
            name="Sloan Park",
            city="Mesa",
            country="US",
            lat=33.4357,
            lng=-111.8845,
        ),
    )
)

# Fuente 4: MTV VMAs 2022 (Anitta y Lisa / BLACKPINK)
src_vmas = get_or_create_source(
    SourceInput(
        title="MTV Video Music Awards Official Broadcast - BLACKPINK and Anitta Backstage Meeting (2022)",
        url="https://www.mtv.com/vma/2022",
        citation="MTV Video Music Awards Official Broadcast and Press Room: BLACKPINK introduces Anitta on stage and historic backstage encounter, Prudential Center, Newark, New Jersey, August 28, 2022.",
        author="MTV News / Paramount Media",
        publisher="MTV Media",
        location=LocationInput(
            name="Prudential Center",
            city="Newark",
            country="US",
            lat=40.7335,
            lng=-74.1711,
        ),
    )
)

# Fuente 5: Encuentro Peso Pluma y Chicharito en Crypto.com Arena
src_chicha_peso = get_or_create_source(
    SourceInput(
        title="MedioTiempo & Los Angeles Times - Encuentro de Chicharito y Peso Pluma en la NBA (2023)",
        url="https://www.mediotiempo.com/futbol/liga-mx/chicharito-cuenta-divertida-anecdota-de-cuando-conocio-a-peso-pluma",
        citation="MedioTiempo: Crónica del encuentro viral entre Javier 'Chicharito' Hernández y Peso Pluma en el Juego 6 Lakers vs Grizzlies, Crypto.com Arena, Los Ángeles, 28 de abril de 2023.",
        author="Redacción MedioTiempo",
        publisher="MedioTiempo / Los Angeles Times",
        location=LocationInput(
            name="Crypto.com Arena",
            city="Los Ángeles",
            country="US",
            lat=34.0430,
            lng=-118.2673,
        ),
    )
)

# Fuente 6: "New Woman" (Lisa & Rosalía)
src_new_woman = get_or_create_source(
    SourceInput(
        title="Variety & LLOUD - Lisa and Rosalía 'New Woman' Collaboration (2024)",
        url="https://variety.com/2024/music/news/lisa-blackpink-rosalia-new-woman-single-1236108151/",
        citation="Variety: 'Lisa and Rosalía Team Up for High-Octane Single New Woman', LLOUD Co. & RCA Records, August 15, 2024.",
        author="Thania Garcia",
        publisher="Variety & RCA Records",
        location=LocationInput(
            name="RCA Records Studios",
            city="Los Ángeles",
            country="US",
            lat=34.0522,
            lng=-118.2437,
        ),
    )
)

# ==============================================================================
# 3. OBRAS MUSICALES Y EVENTO EN VIVO
# ==============================================================================
print("\n--- 3. Creando Obras Musicales y Eventos ---")

# 3.1 Obra: "Teka" (DJ Snake & Peso Pluma, 2024)
work_teka_id = get_or_create_work(
    WorkInput(
        name="Teka",
        kind="music",
        period=Period(
            start=HistoricalDate(year=2024, precision="year"),
            end=HistoricalDate(year=2024, precision="year"),
        ),
        description="Canción bilingüe de electrónica y música urbana producida por DJ Snake e interpretada por Peso Pluma.",
    )
)

# 3.2 Obra: "SG" (DJ Snake, Lisa, Ozuna, Megan Thee Stallion, 2021)
work_sg_id = get_or_create_work(
    WorkInput(
        name="SG",
        kind="music",
        period=Period(
            start=HistoricalDate(year=2021, precision="year"),
            end=HistoricalDate(year=2021, precision="year"),
        ),
        description="Sencillo colaborativo global bilingüe de DJ Snake con Lalisa (Lisa de BLACKPINK), Ozuna y Megan Thee Stallion.",
    )
)

# 3.3 Obra: "BELLAKEO" (Peso Pluma & Anitta, 2023)
work_bellakeo_id = get_or_create_work(
    WorkInput(
        name="BELLAKEO",
        kind="music",
        period=Period(
            start=HistoricalDate(year=2023, precision="year"),
            end=HistoricalDate(year=2023, precision="year"),
        ),
        description="Exitoso sencillo de reguetón y perreo colaborativo de Peso Pluma y Anitta.",
    )
)

# 3.4 Obra: "New Woman" (Lalisa & Rosalía, 2024)
work_new_woman_id = get_or_create_work(
    WorkInput(
        name="New Woman",
        kind="music",
        period=Period(
            start=HistoricalDate(year=2024, precision="year"),
            end=HistoricalDate(year=2024, precision="year"),
        ),
        description="Sencillo pop y electrónico vanguardista de Lalisa en colaboración con la estrella española Rosalía.",
    )
)

# 3.5 Evento Artístico: Coachella 2024 - DJ Snake & Peso Pluma
event_coachella_teka = get_or_create_event_with_facts(
    EventInput(
        name="Coachella 2024 - DJ Snake feat. Peso Pluma Sahara Stage",
        kind="arts.performance",
        place="Empire Polo Club, Indio, California",
        period=Period(
            start=HistoricalDate(year=2024, month=4, day=14, precision="day"),
            end=HistoricalDate(year=2024, month=4, day=14, precision="day"),
        ),
        source_id=src_teka,
        source_locator="Actuación en vivo en el escenario Sahara Tent, festival de Coachella, 14 de abril de 2024.",
        location=LocationInput(
            name="Empire Polo Club",
            city="Indio",
            country="US",
            lat=33.6799,
            lng=-116.2372,
        ),
        participants=[
            EventParticipantInput(
                type_id="arts.performed_together",
                subject_id=dj_snake_id,
                source_id=src_teka,
                source_locator="DJ Snake como DJ principal en el Sahara Tent de Coachella.",
                role="performer",
                status="draft",
                note="DJ Snake lideró su set en el Sahara Tent de Coachella estrenando 'Teka'.",
            ),
            EventParticipantInput(
                type_id="arts.performed_together",
                subject_id=peso_pluma_id,
                source_id=src_teka,
                source_locator="Peso Pluma como invitado sorpresa en vivo de DJ Snake.",
                role="performer",
                status="draft",
                note="Peso Pluma subió al escenario como invitado estelar para cantar en vivo el estreno mundial de 'Teka'.",
            ),
        ],
    )
)

# ==============================================================================
# 4. HECHOS VERIFICADOS (COLABORACIONES Y ENCUENTROS DIRECTOS)
# ==============================================================================
print("\n--- 4. Creando / Verificando Hechos Relacionales ---")

# A) COLABORACIÓN EN "TEKA": PESO PLUMA Y DJ SNAKE (arts.collaborated_on_work)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=peso_pluma_id,
        object_id=work_teka_id,
        role="performer",
        period=Period(
            start=HistoricalDate(year=2024, precision="year"),
            end=HistoricalDate(year=2024, precision="year"),
        ),
        source_id=src_teka,
        source_locator="Créditos oficiales del sencillo 'Teka', Interscope Records, abril de 2024.",
        note="Peso Pluma puso la voz estelar y coescribió el sencillo 'Teka' con DJ Snake.",
        status="draft",
        location=LocationInput(
            name="Empire Polo Club",
            city="Indio",
            country="US",
            lat=33.6799,
            lng=-116.2372,
        ),
    )
)

get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=dj_snake_id,
        object_id=work_teka_id,
        role="creator",
        period=Period(
            start=HistoricalDate(year=2024, precision="year"),
            end=HistoricalDate(year=2024, precision="year"),
        ),
        source_id=src_teka,
        source_locator="Créditos de producción de 'Teka', Interscope Records, abril de 2024.",
        note="DJ Snake compuso y produjo los ritmos electrónicos de 'Teka' junto a Peso Pluma.",
        status="draft",
        location=LocationInput(
            name="Empire Polo Club",
            city="Indio",
            country="US",
            lat=33.6799,
            lng=-116.2372,
        ),
    )
)

# B) COLABORACIÓN EN "SG": DJ SNAKE Y LALISA (arts.collaborated_on_work)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=lalisa_id,
        object_id=work_sg_id,
        role="performer",
        period=Period(
            start=HistoricalDate(year=2021, precision="year"),
            end=HistoricalDate(year=2021, precision="year"),
        ),
        source_id=src_sg,
        source_locator="Créditos del sencillo 'SG', DJ Snake Music Productions / Interscope Records, 2021.",
        note="Lalisa (Lisa de BLACKPINK) cantó, rapeó y protagonizó el videoclip internacional de 'SG'.",
        status="draft",
        location=LocationInput(
            name="South Beach Studios",
            city="Miami",
            country="US",
            lat=25.7617,
            lng=-80.1918,
        ),
    )
)

get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=dj_snake_id,
        object_id=work_sg_id,
        role="creator",
        period=Period(
            start=HistoricalDate(year=2021, precision="year"),
            end=HistoricalDate(year=2021, precision="year"),
        ),
        source_id=src_sg,
        source_locator="Créditos de autoría y producción de 'SG', Interscope Records, 2021.",
        note="DJ Snake creó y produjo el tema 'SG' uniendo a Lisa, Ozuna y Megan Thee Stallion.",
        status="draft",
        location=LocationInput(
            name="South Beach Studios",
            city="Miami",
            country="US",
            lat=25.7617,
            lng=-80.1918,
        ),
    )
)

# C) COLABORACIÓN EN "BELLAKEO": PESO PLUMA Y ANITTA (arts.collaborated_on_work)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=peso_pluma_id,
        object_id=work_bellakeo_id,
        role="performer",
        period=Period(
            start=HistoricalDate(year=2023, precision="year"),
            end=HistoricalDate(year=2023, precision="year"),
        ),
        source_id=src_bellakeo,
        source_locator="Lanzamiento oficial de 'BELLAKEO', Double P Records, diciembre de 2023.",
        note="Peso Pluma compuso y grabó 'BELLAKEO' en colaboración con Anitta.",
        status="draft",
        location=LocationInput(
            name="Sloan Park",
            city="Mesa",
            country="US",
            lat=33.4357,
            lng=-111.8845,
        ),
    )
)

get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=anitta_id,
        object_id=work_bellakeo_id,
        role="performer",
        period=Period(
            start=HistoricalDate(year=2023, precision="year"),
            end=HistoricalDate(year=2023, precision="year"),
        ),
        source_id=src_bellakeo,
        source_locator="Créditos oficiales de 'BELLAKEO', diciembre de 2023.",
        note="Anitta coescribió e interpretó 'BELLAKEO' a dueto con Peso Pluma.",
        status="draft",
        location=LocationInput(
            name="Sloan Park",
            city="Mesa",
            country="US",
            lat=33.4357,
            lng=-111.8845,
        ),
    )
)

# D) ENCUENTRO EN VIVO: PESO PLUMA <-> ANITTA (personal.met, 10 de diciembre de 2023)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=peso_pluma_id,
        object_id=anitta_id,
        period=Period(
            start=HistoricalDate(year=2023, month=12, day=10, precision="day"),
            end=HistoricalDate(year=2023, month=12, day=10, precision="day"),
        ),
        source_id=src_bellakeo,
        source_locator="Festival TikTok In The Mix en Sloan Park, Mesa, Arizona, 10 de diciembre de 2023.",
        note=(
            "Peso Pluma y Anitta se presentaron juntos en vivo en el festival TikTok In The Mix para estrenar 'BELLAKEO', "
            "un momento viral en redes sociales por la cómica actitud tímida de Peso Pluma ante el baile de Anitta."
        ),
        status="draft",
        location=LocationInput(
            name="Sloan Park",
            city="Mesa",
            country="US",
            lat=33.4357,
            lng=-111.8845,
        ),
    )
)

# E) ENCUENTRO EN BACKSTAGE DE LOS VMAs: ANITTA <-> LALISA (personal.met, 28 de agosto de 2022)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=anitta_id,
        object_id=lalisa_id,
        period=Period(
            start=HistoricalDate(year=2022, month=8, day=28, precision="day"),
            end=HistoricalDate(year=2022, month=8, day=28, precision="day"),
        ),
        source_id=src_vmas,
        source_locator="MTV Video Music Awards en Prudential Center, Newark, Nueva Jersey, 28 de agosto de 2022.",
        note=(
            "Anitta y Lalisa (Lisa de BLACKPINK) se reunieron tras bambalinas en los MTV VMAs 2022 tras sus históricas presentaciones "
            "y premios respectivos, compartiendo fotos virales descansando juntas de los tacones."
        ),
        status="draft",
        location=LocationInput(
            name="Prudential Center",
            city="Newark",
            country="US",
            lat=40.7335,
            lng=-74.1711,
        ),
    )
)

# F) COLABORACIÓN EN "NEW WOMAN": LALISA Y ROSALÍA (arts.collaborated_on_work)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=lalisa_id,
        object_id=work_new_woman_id,
        role="performer",
        period=Period(
            start=HistoricalDate(year=2024, precision="year"),
            end=HistoricalDate(year=2024, precision="year"),
        ),
        source_id=src_new_woman,
        source_locator="Créditos del sencillo 'New Woman', LLOUD Co. / RCA Records, agosto de 2024.",
        note="Lalisa interpretó y protagonizó el sencillo global 'New Woman'.",
        status="draft",
        location=LocationInput(
            name="RCA Records Studios",
            city="Los Ángeles",
            country="US",
            lat=34.0522,
            lng=-118.2437,
        ),
    )
)

get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=rosalia_id,
        object_id=work_new_woman_id,
        role="performer",
        period=Period(
            start=HistoricalDate(year=2024, precision="year"),
            end=HistoricalDate(year=2024, precision="year"),
        ),
        source_id=src_new_woman,
        source_locator="Créditos del sencillo 'New Woman', LLOUD Co. / RCA Records, agosto de 2024.",
        note="Rosalía coescribió y cantó a dúo con Lisa en 'New Woman'.",
        status="draft",
        location=LocationInput(
            name="RCA Records Studios",
            city="Los Ángeles",
            country="US",
            lat=34.0522,
            lng=-118.2437,
        ),
    )
)

# G) ENCUENTRO CURIOSO EN LA NBA: PESO PLUMA <-> CHICHARITO HERNÁNDEZ (personal.met, 28 de abril de 2023)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=peso_pluma_id,
        object_id=chicharito_id,
        period=Period(
            start=HistoricalDate(year=2023, month=4, day=28, precision="day"),
            end=HistoricalDate(year=2023, month=4, day=28, precision="day"),
        ),
        source_id=src_chicha_peso,
        source_locator="Crypto.com Arena, Juego 6 de Playoffs Lakers vs Grizzlies, Los Ángeles, 28 de abril de 2023.",
        note=(
            "Peso Pluma saludó a Javier 'Chicharito' Hernández en el Crypto.com Arena de Los Ángeles el 28 de abril de 2023. "
            "Chicharito relató después que no lo reconoció en el primer instante, buscó sus fotos en Google, y al regresar le dijo entre risas "
            "que lo había agarrado en fuera de juego, culminando en un cálido abrazo y fotografía juntos."
        ),
        status="draft",
        location=LocationInput(
            name="Crypto.com Arena",
            city="Los Ángeles",
            country="US",
            lat=34.0430,
            lng=-118.2673,
        ),
    )
)

# ==============================================================================
# 5. VERIFICACIÓN Y PREVIEWS DEL CAMINO COMPLETO
# ==============================================================================
print("\n--- 5. Verificando Conexiones Derivadas y Caminos Óptimos ---")

print("\n[Conexiones derivadas para Peso Pluma]:")
preview_pp = connection_preview(repo, peso_pluma_id)
for conn in preview_pp:
    target_person = repo.get("people", conn["person_id"])
    target_name = target_person.get("search_name") or target_person.get("name")
    print(f"  -> Conectado con: {target_name} vía {conn['type_id']}")

print("\n[Conexiones derivadas para Lalisa]:")
preview_lisa = connection_preview(repo, lalisa_id)
for conn in preview_lisa:
    target_person = repo.get("people", conn["person_id"])
    target_name = target_person.get("search_name") or target_person.get("name")
    print(f"  -> Conectado con: {target_name} vía {conn['type_id']}")

with driver.session() as session:
    path_res = session.run(
        """
        MATCH path = shortestPath((start:Person {id: $p_id})-[*..10]-(target:Person {id: $l_id}))
        RETURN [node IN nodes(path) | coalesce(node.search_name, node.name, labels(node)[0])] AS names,
               [rel IN relationships(path) | type(rel)] AS rels,
               length(path) AS hops
        """,
        p_id=peso_pluma_id,
        l_id=lalisa_id,
    ).single()

if path_res:
    print(f"\n[CAMINO MÁS CORTO ENCONTRADO EN NEO4J] ({path_res['hops']} saltos):")
    for idx, name in enumerate(path_res["names"]):
        if idx < len(path_res["rels"]):
            print(f"  ({name}) --[{path_res['rels'][idx]}]-->")
        else:
            print(f"  ({name})")

print("\n================================================================================")
print("  CONEXIÓN PESO PLUMA -> LALISA COMPLETADA EXITOSAMENTE")
print("================================================================================")
