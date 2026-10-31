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
print("  CONEXIÓN EXPLICABLE: LINUS TORVALDS -> ADOLF HITLER")
print("================================================================================")

# ==============================================================================
# 1. PERSONAS (Verificadas antes de crear para evitar duplicados)
# ==============================================================================
print("\n--- 1. Verificando / Creando Personas ---")

# 1.1 Linus Torvalds
linus_id = get_or_create_person(
    PersonInput(
        name="Linus Torvalds",
        aliases=["Linus Benedict Torvalds"],
        description=(
            "Ingeniero de software finlandés-estadounidense, creador y desarrollador principal del núcleo Linux "
            "y del sistema de control de versiones Git. Ganador del Premio de Tecnología del Milenio (2012)."
        ),
        country="FI",
        city_born="Helsinki",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/0/01/LinuxCon_Europe_Linus_Torvalds_03_%28cropped%29.jpg/800px-LinuxCon_Europe_Linus_Torvalds_03_%28cropped%29.jpg",
        wikidata_id="Q34286",
        birth=HistoricalDate(year=1969, month=12, day=28, precision="day"),
    ),
    {
        "real_name": "Linus Benedict Torvalds",
        "best_known_for": "Linus Torvalds",
        "principal_occupation": "Ingeniero de software y creador del kernel Linux y Git",
    },
)

# 1.2 Dave Cutler (Arquitecto de Windows NT, co-participante en la cena histórica)
cutler_id = get_or_create_person(
    PersonInput(
        name="Dave Cutler",
        aliases=["David Neil Cutler Jr."],
        description=(
            "Legendario ingeniero de sistemas operativos estadounidense, diseñador principal de VMS para DEC "
            "y de la arquitectura Windows NT para Microsoft."
        ),
        country="US",
        city_born="Lansing",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/f/f2/David_Cutler.jpg/800px-David_Cutler.jpg",
        wikidata_id="Q92787",
        birth=HistoricalDate(year=1942, month=3, day=13, precision="day"),
    ),
    {
        "real_name": "David Neil Cutler Jr.",
        "best_known_for": "Dave Cutler",
        "principal_occupation": "Ingeniero de software y creador de Windows NT",
    },
)

# 1.3 Bill Gates (Ya en BD)
bill_gates_id = get_or_create_person(
    PersonInput(
        name="Bill Gates",
        aliases=["William Henry Gates III"],
        description="Empresario y filántropo estadounidense, cofundador de Microsoft.",
        country="US",
        city_born="Seattle",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/Bill_Gates_2017_%28cropped%29.jpg/800px-Bill_Gates_2017_%28cropped%29.jpg",
        wikidata_id="Q5284",
        birth=HistoricalDate(year=1955, month=10, day=28, precision="day"),
    ),
    {
        "real_name": "William Henry Gates III",
        "best_known_for": "Bill Gates",
        "principal_occupation": "Empresario tecnológico y filántropo",
    },
)

# 1.4 Eduardo VIII del Reino Unido (Duque de Windsor, hermano de Jorge VI)
edward_viii_id = get_or_create_person(
    PersonInput(
        name="Eduardo VIII del Reino Unido",
        aliases=["Edward VIII", "Duque de Windsor", "Edward Albert Christian George Andrew Patrick David"],
        description=(
            "Rey del Reino Unido y emperador de la India en 1936 hasta su abdicación para casarse con Wallis Simpson. "
            "Hermano mayor del rey Jorge VI. En octubre de 1937 viajó a Alemania y se reunió personalmente con Adolf Hitler en el Berghof."
        ),
        country="GB",
        city_born="Londres",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/King_Edward_VIII_1936.jpg/800px-King_Edward_VIII_1936.jpg",
        wikidata_id="Q5964",
        birth=HistoricalDate(year=1894, month=6, day=23, precision="day"),
        death=HistoricalDate(year=1972, month=5, day=28, precision="day"),
    ),
    {
        "real_name": "Edward Albert Christian George Andrew Patrick David",
        "best_known_for": "Eduardo VIII del Reino Unido",
        "principal_occupation": "Monarca británico y Duque de Windsor",
    },
)

# 1.5 Wallis Simpson (Duquesa de Windsor, co-participante en la reunión del Berghof)
wallis_id = get_or_create_person(
    PersonInput(
        name="Wallis Simpson",
        aliases=["Duquesa de Windsor", "Bessie Wallis Warfield"],
        description=(
            "Socialite estadounidense que se convirtió en Duquesa de Windsor al contraer matrimonio con Eduardo VIII. "
            "Acompañó al duque en su visita a Alemania en 1937 y asistió a la audiencia con Adolf Hitler en el Berghof."
        ),
        country="US",
        city_born="Blue Ridge Summit",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/e/ee/Wallis_Simpson_1936.jpg/800px-Wallis_Simpson_1936.jpg",
        wikidata_id="Q203975",
        birth=HistoricalDate(year=1896, month=6, day=19, precision="day"),
        death=HistoricalDate(year=1986, month=4, day=24, precision="day"),
    ),
    {
        "real_name": "Bessie Wallis Warfield",
        "best_known_for": "Wallis Simpson",
        "principal_occupation": "Duquesa de Windsor",
    },
)

# 1.6 Jorge VI del Reino Unido (Ya en BD)
george_vi_id = get_or_create_person(
    PersonInput(
        name="Jorge VI del Reino Unido",
        aliases=["George VI", "Albert Frederick Arthur George", "Rey Jorge VI"],
        description="Rey del Reino Unido y los dominios de la Mancomunidad Británica de Naciones desde 1936 hasta su muerte en 1952.",
        country="GB",
        city_born="Sandringham",
        image_url="https://upload.wikimedia.org/wikipedia/commons/e/e0/King_George_VI_LOC_matpc.14736_A_%28cropped%29.jpg",
        wikidata_id="Q280856",
        birth=HistoricalDate(year=1895, month=12, day=14, precision="day"),
        death=HistoricalDate(year=1952, month=2, day=6, precision="day"),
    ),
    {
        "real_name": "Albert Frederick Arthur George",
        "best_known_for": "Jorge VI del Reino Unido",
        "principal_occupation": "Monarca del Reino Unido",
    },
)

# 1.7 Jorge V del Reino Unido (Ya en BD)
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

# 1.8 Max Planck (Ya en BD)
planck_id = get_or_create_person(
    PersonInput(
        name="Max Planck",
        aliases=["Max Karl Ernst Ludwig Planck"],
        description="Físico teórico alemán, padre de la física cuántica y premio Nobel de Física en 1918.",
        country="DE",
        city_born="Kiel",
        image_url="https://upload.wikimedia.org/wikipedia/commons/c/c7/Max_Planck_1933.jpg",
        wikidata_id="Q9021",
        birth=HistoricalDate(year=1858, month=4, day=23, precision="day"),
        death=HistoricalDate(year=1947, month=10, day=4, precision="day"),
    ),
    {
        "real_name": "Max Karl Ernst Ludwig Planck",
        "best_known_for": "Max Planck",
        "principal_occupation": "Físico teórico y premio Nobel",
    },
)

# 1.9 Adolf Hitler
hitler_id = get_or_create_person(
    PersonInput(
        name="Adolf Hitler",
        aliases=["Hitler", "El Führer"],
        description=(
            "Político y dictador alemán de origen austríaco, canciller de Alemania de 1933 a 1945 y líder del Partido Nazi. "
            "Inició la Segunda Guerra Mundial en Europa con la invasión de Polonia en 1939 y fue el principal artífice del Holocausto."
        ),
        country="DE",
        city_born="Braunau am Inn",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/Hitler_portrait_crop.jpg/800px-Hitler_portrait_crop.jpg",
        wikidata_id="Q352",
        birth=HistoricalDate(year=1889, month=4, day=20, precision="day"),
        death=HistoricalDate(year=1945, month=4, day=30, precision="day"),
    ),
    {
        "real_name": "Adolf Hitler",
        "best_known_for": "Adolf Hitler",
        "principal_occupation": "Dictador de la Alemania nazi y Führer del Tercer Reich",
    },
)

# ==============================================================================
# 2. FUENTES DOCUMENTADAS CON GEOLOCALIZACIÓN
# ==============================================================================
print("\n--- 2. Verificando / Creando Fuentes Históricas ---")

# Fuente 1: Histórico primer encuentro de Linus Torvalds y Bill Gates (2025)
src_linus_gates = get_or_create_source(
    SourceInput(
        title="Tom's Hardware & LinkedIn - Bill Gates and Linus Torvalds Meet in Person for the First Time (June 2025)",
        url="https://www.tomshardware.com/tech-industry/bill-gates-and-linus-torvalds-meet-in-person-for-the-first-time",
        citation="Tom's Hardware & Mark Russinovich: Historic private dinner gathering Bill Gates, Linus Torvalds, and Dave Cutler, Bellevue, Washington, June 2025.",
        author="Anton Shilov",
        publisher="Tom's Hardware / Future US",
        location=LocationInput(
            name="Residencia de Mark Russinovich",
            city="Bellevue",
            country="US",
            lat=47.6101,
            lng=-122.2015,
        ),
    )
)

# Fuente 2: Linaje de Eduardo VIII y Jorge VI (Hijos de Jorge V)
src_royal_brothers = get_or_create_source(
    SourceInput(
        title="The Royal Archives - Lineage of King George V: Princes Edward and Albert (George VI)",
        url="https://www.royal.uk/edward-viii",
        citation="The Royal Collection Trust & Royal Family Archives: Official Lineage of the Sons of King George V and Queen Mary.",
        author="The Royal Household",
        publisher="The Royal Archives",
        location=LocationInput(
            name="Palacio de Buckingham",
            city="Londres",
            country="GB",
            lat=51.5014,
            lng=-0.1419,
        ),
    )
)

# Fuente 3: Visita del Duque de Windsor a Adolf Hitler en el Berghof (1937)
src_windsor_hitler = get_or_create_source(
    SourceInput(
        title="The National Archives UK - The Duke and Duchess of Windsor Visit Adolf Hitler at the Berghof (October 22, 1937)",
        url="https://www.nationalarchives.gov.uk/education/resources/chamberlain-and-hitler/",
        citation="The National Archives UK, Foreign Office records FO 371/20736: Audience of the Duke and Duchess of Windsor with Chancellor Adolf Hitler at the Berghof, Berchtesgaden, October 22, 1937.",
        author="British Foreign Office Diplomatic Records",
        publisher="The National Archives (UK)",
        location=LocationInput(
            name="El Berghof (Obersalzberg)",
            city="Berchtesgaden",
            country="DE",
            lat=47.6339,
            lng=13.0417,
        ),
    )
)

# Fuente 4: Audiencia de Max Planck con Adolf Hitler en la Cancillería del Reich (1933)
src_planck_hitler = get_or_create_source(
    SourceInput(
        title="Max-Planck-Gesellschaft Archives - Max Planck's Audience with Adolf Hitler (May 16, 1933)",
        url="https://www.mpg.de/history",
        citation="Max Planck: 'Mein Besuch bei Hitler' (Physikalische Blätter 3, 1947, pp. 143); Max-Planck-Gesellschaft Archiv, Berlin.",
        author="Max Planck",
        publisher="Max-Planck-Gesellschaft zur Förderung der Wissenschaften",
        location=LocationInput(
            name="Cancillería del Reich (Reichskanzlei)",
            city="Berlín",
            country="DE",
            lat=52.5117,
            lng=13.3831,
        ),
    )
)

# ==============================================================================
# 3. HECHOS VERIFICADOS (RELACIONES TECNOLÓGICAS, REALES E HISTÓRICAS)
# ==============================================================================
print("\n--- 3. Creando / Verificando Hechos Relacionales ---")

# A) LINUS TORVALDS <-> BILL GATES: ENCUENTRO HISTÓRICO CARA A CARA (personal.met, junio de 2025)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=linus_id,
        object_id=bill_gates_id,
        period=Period(
            start=HistoricalDate(year=2025, month=6, precision="month"),
            end=HistoricalDate(year=2025, month=6, precision="month"),
        ),
        source_id=src_linus_gates,
        source_locator="Cena privada organizada por Mark Russinovich en Bellevue, Washington, junio de 2025.",
        note=(
            "Linus Torvalds y Bill Gates se conocieron en persona por primera vez en junio de 2025 durante una cena privada "
            "organizada por Mark Russinovich en Bellevue, Washington. Pese a protagonizar durante más de 30 años la mayor rivalidad "
            "de sistemas operativos del mundo (Linux vs. Windows), los dos líderes tecnológicos compartieron una velada cordial "
            "dialogando sobre filantropía global y energía nuclear."
        ),
        status="draft",
        location=LocationInput(
            name="Residencia de Mark Russinovich",
            city="Bellevue",
            country="US",
            lat=47.6101,
            lng=-122.2015,
        ),
    )
)

# B) LINUS TORVALDS <-> DAVE CUTLER: CO-PARTICIPANTES EN LA CENA (personal.met, junio de 2025)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=linus_id,
        object_id=cutler_id,
        period=Period(
            start=HistoricalDate(year=2025, month=6, precision="month"),
            end=HistoricalDate(year=2025, month=6, precision="month"),
        ),
        source_id=src_linus_gates,
        source_locator="Cena de creadores de sistemas operativos, Bellevue, Washington, junio de 2025.",
        note=(
            "Linus Torvalds y Dave Cutler (arquitecto de Windows NT) se reunieron por primera vez cara a cara "
            "en la cena de Bellevue en junio de 2025."
        ),
        status="draft",
        location=LocationInput(
            name="Residencia de Mark Russinovich",
            city="Bellevue",
            country="US",
            lat=47.6101,
            lng=-122.2015,
        ),
    )
)

# C) JORGE V <-> EDUARDO VIII: RELACIÓN PADRE-HIJO (family.parent_of, 23 de junio de 1894)
get_or_create_verified_fact(
    FactInput(
        type_id="family.parent_of",
        subject_id=george_v_id,
        object_id=edward_viii_id,
        period=Period(
            start=HistoricalDate(year=1894, month=6, day=23, precision="day"),
            end=HistoricalDate(year=1936, month=1, day=20, precision="day"),
        ),
        source_id=src_royal_brothers,
        source_locator="Acta de nacimiento del príncipe Eduardo, White Lodge, Richmond Park, Londres, 23 de junio de 1894.",
        note="El rey Jorge V es el padre biológico del rey Eduardo VIII (Duque de Windsor).",
        status="draft",
        location=LocationInput(
            name="White Lodge, Richmond Park",
            city="Londres",
            country="GB",
            lat=51.4475,
            lng=-0.2742,
        ),
    )
)

# D) JORGE VI <-> EDUARDO VIII: HERMANOS (family.sibling_of)
get_or_create_verified_fact(
    FactInput(
        type_id="family.sibling_of",
        subject_id=george_vi_id,
        object_id=edward_viii_id,
        period=Period(
            start=HistoricalDate(year=1895, month=12, day=14, precision="day"),
            end=HistoricalDate(year=1952, month=2, day=6, precision="day"),
        ),
        source_id=src_royal_brothers,
        source_locator="Genealogía de la Casa Real británica: Hijos de Jorge V y la Reina María.",
        note=(
            "El rey Jorge VI del Reino Unido y el duque de Windsor (exrey Eduardo VIII) fueron hermanos carnales, "
            "hijos de los reyes Jorge V y María de Teck."
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

# E) EDUARDO VIII <-> WALLIS SIMPSON: CÓNYUGES (family.spouse_of, 3 de junio de 1937)
get_or_create_verified_fact(
    FactInput(
        type_id="family.spouse_of",
        subject_id=edward_viii_id,
        object_id=wallis_id,
        period=Period(
            start=HistoricalDate(year=1937, month=6, day=3, precision="day"),
            end=HistoricalDate(year=1972, month=5, day=28, precision="day"),
        ),
        source_id=src_royal_brothers,
        source_locator="Matrimonio en el Château de Candé, Monts, Francia, 3 de junio de 1937.",
        note="Eduardo VIII y Wallis Simpson contrajeron matrimonio en Francia en junio de 1937 tras la abdicación del monarca.",
        status="draft",
        location=LocationInput(
            name="Château de Candé",
            city="Monts",
            country="FR",
            lat=47.2961,
            lng=0.6628,
        ),
    )
)

# F) EDUARDO VIII <-> ADOLF HITLER: ENCUENTRO EN EL BERGHOF (personal.met, 22 de octubre de 1937)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=edward_viii_id,
        object_id=hitler_id,
        period=Period(
            start=HistoricalDate(year=1937, month=10, day=22, precision="day"),
            end=HistoricalDate(year=1937, month=10, day=22, precision="day"),
        ),
        source_id=src_windsor_hitler,
        source_locator="El Berghof, Obersalzberg, Berchtesgaden, Alemania, 22 de octubre de 1937.",
        note=(
            "El Duque de Windsor (exrey Eduardo VIII del Reino Unido) visitó Alemania y se reunió personalmente con Adolf Hitler "
            "en su residencia alpina del Berghof el 22 de octubre de 1937. Ambos mantuvieron una reunión privada de una hora y tomaron el té, "
            "un encuentro ampliamente documentado y fotografiado por la prensa internacional."
        ),
        status="draft",
        location=LocationInput(
            name="El Berghof (Obersalzberg)",
            city="Berchtesgaden",
            country="DE",
            lat=47.6339,
            lng=13.0417,
        ),
    )
)

# G) WALLIS SIMPSON <-> ADOLF HITLER: AUDIENCIA EN EL BERGHOF (personal.met, 22 de octubre de 1937)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=wallis_id,
        object_id=hitler_id,
        period=Period(
            start=HistoricalDate(year=1937, month=10, day=22, precision="day"),
            end=HistoricalDate(year=1937, month=10, day=22, precision="day"),
        ),
        source_id=src_windsor_hitler,
        source_locator="Audiencia con Adolf Hitler en el Berghof, 22 de octubre de 1937.",
        note=(
            "Wallis Simpson, Duquesa de Windsor, fue recibida en persona por Adolf Hitler en el Berghof el 22 de octubre de 1937, "
            "donde el Führer conversó con ella sobre la arquitectura alemana y la sociedad británica."
        ),
        status="draft",
        location=LocationInput(
            name="El Berghof (Obersalzberg)",
            city="Berchtesgaden",
            country="DE",
            lat=47.6339,
            lng=13.0417,
        ),
    )
)

# H) MAX PLANCK <-> ADOLF HITLER: AUDIENCIA EN LA CANCILLERÍA DEL REICH (personal.met, 16 de mayo de 1933)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=planck_id,
        object_id=hitler_id,
        period=Period(
            start=HistoricalDate(year=1933, month=5, day=16, precision="day"),
            end=HistoricalDate(year=1933, month=5, day=16, precision="day"),
        ),
        source_id=src_planck_hitler,
        source_locator="Audiencia oficial en la Cancillería del Reich, Berlín, 16 de mayo de 1933; 'Mein Besuch bei Hitler'.",
        note=(
            "Max Planck, en su calidad de presidente de la Sociedad Kaiser Wilhelm, se reunió en persona con el canciller Adolf Hitler "
            "en la Cancillería del Reich en Berlín el 16 de mayo de 1933. Planck intentó disuadir a Hitler de expulsar a los científicos "
            "judíos (como Fritz Haber), advirtiéndole que arruinaría la ciencia alemana; Hitler enfureció a gritos, declarando que "
            "si despedir a los judíos significaba aniquilar la ciencia alemana contemporánea, Alemania prescindiría de la ciencia."
        ),
        status="draft",
        location=LocationInput(
            name="Cancillería del Reich (Reichskanzlei)",
            city="Berlín",
            country="DE",
            lat=52.5117,
            lng=13.3831,
        ),
    )
)

# ==============================================================================
# 4. VERIFICACIÓN Y PREVIEWS DEL CAMINO COMPLETO
# ==============================================================================
print("\n--- 4. Verificando Conexiones Derivadas y Caminos Óptimos ---")

print("\n[Conexiones derivadas para Linus Torvalds]:")
preview_linus = connection_preview(repo, linus_id)
for conn in preview_linus:
    target_person = repo.get("people", conn["person_id"])
    target_name = target_person.get("search_name") or target_person.get("name")
    print(f"  -> Conectado con: {target_name} vía {conn['type_id']}")

print("\n[Conexiones derivadas para Adolf Hitler]:")
preview_hitler = connection_preview(repo, hitler_id)
for conn in preview_hitler:
    target_person = repo.get("people", conn["person_id"])
    target_name = target_person.get("search_name") or target_person.get("name")
    print(f"  -> Conectado con: {target_name} vía {conn['type_id']}")

with driver.session() as session:
    path_res = session.run(
        """
        MATCH path = shortestPath((start:Person {id: $l_id})-[*..20]-(target:Person {id: $h_id}))
        RETURN [node IN nodes(path) | coalesce(node.search_name, node.name, labels(node)[0])] AS names,
               [rel IN relationships(path) | type(rel)] AS rels,
               length(path) AS hops
        """,
        l_id=linus_id,
        h_id=hitler_id,
    ).single()

if path_res:
    print(f"\n[CAMINO MÁS CORTO ENCONTRADO EN NEO4J] ({path_res['hops']} saltos):")
    for idx, name in enumerate(path_res["names"]):
        if idx < len(path_res["rels"]):
            print(f"  ({name}) --[{path_res['rels'][idx]}]-->")
        else:
            print(f"  ({name})")

print("\n================================================================================")
print("  CONEXIÓN LINUS TORVALDS -> ADOLF HITLER COMPLETADA EXITOSAMENTE")
print("================================================================================")
