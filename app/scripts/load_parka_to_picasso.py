import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import (
    FactInput,
    HistoricalDate,
    LocationInput,
    OrganizationInput,
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


def get_or_create_organization(org_input: OrganizationInput):
    """Verifica si la organización/equipo ya existe antes de crearla."""
    with driver.session() as session:
        res = session.run(
            """
            MATCH (o:Organization)
            WHERE toLower(coalesce(o.search_name, '')) = toLower($name)
            RETURN o.id AS id, o.search_name AS name
            LIMIT 1
            """,
            name=org_input.name,
        ).single()
        if res:
            print(f"[EXISTE ORGANIZACIÓN] '{res['name']}' (ID: {res['id']})")
            return res["id"]

    print(f"[NUEVA ORGANIZACIÓN] Creando: '{org_input.name}'...")
    created = repo.create("organizations", org_input.model_dump(mode="json"))
    print(f"[CREADA ORGANIZACIÓN] ID: {created['id']}")
    return created["id"]


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

    # Verificar hecho
    current = repo.get("facts", fact_id)
    data = {k: v for k, v in current.items() if k not in ("id", "revision", "created_at", "updated_at")}
    data["status"] = "verified"
    repo.update("facts", fact_id, current["revision"], validate_fact(repo, data), "verify")
    print(f"[HECHO VERIFICADO] ID {fact_id} creado y verificado.")
    return fact_id


print("================================================================================")
print("  CONEXIÓN EXPLICABLE: LA PARKA -> PABLO PICASSO (CON TODAS LAS REGLAS)")
print("================================================================================")

# ==============================================================================
# 1. PERSONAS (Verificación de no duplicados)
# ==============================================================================
print("\n--- 1. Verificando / Creando Personas ---")

# 1.1 La Parka (Jesús Alfonso Huerta Escoboza)
parka_id = get_or_create_person(
    PersonInput(
        name="La Parka",
        aliases=["La Parka Jr.", "Jesús Alfonso Huerta Escoboza", "Chuy Escoboza"],
        description=(
            "Ícono indiscutible de la lucha libre mexicana y estandarte histórico de la empresa Lucha Libre AAA Worldwide. "
            "Ganador de múltiples ediciones del torneo Rey de Reyes y de Triplemanía, encarnó al personaje de La Parka durante más de 20 años."
        ),
        country="MX",
        city_born="Hermosillo",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/La_Parka_AAA.jpg/800px-La_Parka_AAA.jpg",
        wikidata_id="Q6464293",
        birth=HistoricalDate(year=1966, month=5, day=24, precision="day"),
        death=HistoricalDate(year=2020, month=1, day=11, precision="day"),
    ),
    {
        "real_name": "Jesús Alfonso Huerta Escoboza",
        "best_known_for": "La Parka",
        "principal_occupation": "Luchador profesional (AAA)",
    },
)

# 1.2 L.A. Park (Adolfo Tapia Ibarra) - Involucrado directo en la histórica rivalidad por el nombre
la_park_id = get_or_create_person(
    PersonInput(
        name="L.A. Park",
        aliases=["La Parka Original", "Adolfo Tapia", "Adolfo Margarito Tapia Ibarra"],
        description=(
            "Luchador profesional mexicano de renombre internacional. Creador original del personaje de La Parka en 1992 en AAA, "
            "con destacada trayectoria en WCW, CMLL y en el circuito independiente."
        ),
        country="MX",
        city_born="Monclova",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/L.A._Park_in_2019.jpg/800px-L.A._Park_in_2019.jpg",
        wikidata_id="Q6457187",
        birth=HistoricalDate(year=1965, month=11, day=14, precision="day"),
    ),
    {
        "real_name": "Adolfo Margarito Tapia Ibarra",
        "best_known_for": "L.A. Park",
        "principal_occupation": "Luchador profesional",
    },
)

# 1.3 El Hijo del Santo (Jorge Ernesto Guzmán Rodríguez)
hijo_santo_id = get_or_create_person(
    PersonInput(
        name="El Hijo del Santo",
        aliases=["Jorge Guzmán", "Jorge Ernesto Guzmán Rodríguez"],
        description=(
            "Luchador profesional mexicano y activista ambiental, continuador del legado de la máxima leyenda de la lucha libre, El Santo. "
            "Figura estelar fundadora de Lucha Libre AAA y campeón mundial en múltiples categorías."
        ),
        country="MX",
        city_born="Ciudad de México",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/El_Hijo_del_Santo_2012.jpg/800px-El_Hijo_del_Santo_2012.jpg",
        wikidata_id="Q3050073",
        birth=HistoricalDate(year=1963, month=8, day=2, precision="day"),
    ),
    {
        "real_name": "Jorge Ernesto Guzmán Rodríguez",
        "best_known_for": "El Hijo del Santo",
        "principal_occupation": "Luchador profesional y activista",
    },
)

# 1.4 El Santo (Rodolfo Guzmán Huerta)
santo_id = get_or_create_person(
    PersonInput(
        name="El Santo",
        aliases=["El Enmascarado de Plata", "Rodolfo Guzmán Huerta"],
        description=(
            "La máxima leyenda del pancracio y de la cultura popular mexicana del siglo XX. Luchador profesional invicto en luchas de apuestas "
            "y protagonista de más de 50 películas de culto internacional donde combatió a villanos, científicos y criaturas fantásticas."
        ),
        country="MX",
        city_born="Tulancingo",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/El_Santo_en_1965.jpg/800px-El_Santo_en_1965.jpg",
        wikidata_id="Q504786",
        birth=HistoricalDate(year=1917, month=9, day=23, precision="day"),
        death=HistoricalDate(year=1984, month=2, day=5, precision="day"),
    ),
    {
        "real_name": "Rodolfo Guzmán Huerta",
        "best_known_for": "El Santo",
        "principal_occupation": "Luchador profesional y actor cinematográfico",
    },
)

# 1.5 Claudio Brook (Claude Sydney Brook Marnat)
brook_id = get_or_create_person(
    PersonInput(
        name="Claudio Brook",
        aliases=["Claude Sydney Brook Marnat", "Claude Brook"],
        description=(
            "Primer actor mexicano de cine, teatro y televisión, reconocido por su versatilidad y prolífica trayectoria internacional. "
            "Coprotagonizó con El Santo la película 'Santo en el museo de cera' (1963) e interpretó papeles protagónicos estelares para Luis Buñuel."
        ),
        country="MX",
        city_born="Ciudad de México",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/Claudio_Brook_1965.jpg/800px-Claudio_Brook_1965.jpg",
        wikidata_id="Q1095992",
        birth=HistoricalDate(year=1927, month=8, day=28, precision="day"),
        death=HistoricalDate(year=1995, month=10, day=18, precision="day"),
    ),
    {
        "real_name": "Claude Sydney Brook Marnat",
        "best_known_for": "Claudio Brook",
        "principal_occupation": "Actor de cine, teatro y televisión",
    },
)

# 1.6 Rubén Rojo (Actor coprotagonista en 'Santo en el museo de cera')
ruben_rojo_id = get_or_create_person(
    PersonInput(
        name="Rubén Rojo",
        aliases=["Rubén Rojo Pinto"],
        description=(
            "Destacado actor hispanomexicano de la Época de Oro del cine mexicano y del cine español. "
            "Coprotagonista junto a El Santo y Claudio Brook en 'Santo en el museo de cera' (1963)."
        ),
        country="ES",
        city_born="Madrid",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/Ruben_Rojo_1950.jpg/800px-Ruben_Rojo_1950.jpg",
        wikidata_id="Q115352",
        birth=HistoricalDate(year=1922, month=12, day=15, precision="day"),
        death=HistoricalDate(year=1993, month=6, day=11, precision="day"),
    ),
    {
        "real_name": "Rubén Rojo Pinto",
        "best_known_for": "Rubén Rojo",
        "principal_occupation": "Actor cinematográfico",
    },
)

# 1.7 Silvia Pinal (Actriz coprotagonista con Claudio Brook en Buñuel y retratada por Diego Rivera)
pinal_id = get_or_create_person(
    PersonInput(
        name="Silvia Pinal",
        aliases=["Silvia Pinal Hidalgo"],
        description=(
            "Gran diva del cine, teatro y televisión mexicana, cumbre de la Época de Oro. Musa y protagonista de la trilogía maestra de Luis Buñuel "
            "('Viridiana', 'El ángel exterminador', 'Simón del desierto'), y célebre modelo retratada por Diego Rivera en 1956."
        ),
        country="MX",
        city_born="Guaymas",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/Silvia_Pinal_1962.jpg/800px-Silvia_Pinal_1962.jpg",
        wikidata_id="Q284355",
        birth=HistoricalDate(year=1931, month=9, day=12, precision="day"),
    ),
    {
        "real_name": "Silvia Pinal Hidalgo",
        "best_known_for": "Silvia Pinal",
        "principal_occupation": "Actriz pionera del cine mexicano",
    },
)

# 1.8 Luis Buñuel (Luis Buñuel Portolés)
bunuel_id = get_or_create_person(
    PersonInput(
        name="Luis Buñuel",
        aliases=["Luis Buñuel Portolés"],
        description=(
            "Uno de los directores más influyentes e innovadores en la historia del cine mundial. Máxima figura del cine surrealista, "
            "organizó culturalmente el Pabellón de la República Española en la Exposición Internacional de París de 1937 colaborando con Pablo Picasso en el 'Guernica'."
        ),
        country="ES",
        city_born="Calanda",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/Luis_Bu%C3%B1uel_1968.jpg/800px-Luis_Bu%C3%B1uel_1968.jpg",
        wikidata_id="Q51545",
        birth=HistoricalDate(year=1900, month=2, day=22, precision="day"),
        death=HistoricalDate(year=1983, month=7, day=29, precision="day"),
    ),
    {
        "real_name": "Luis Buñuel Portolés",
        "best_known_for": "Luis Buñuel",
        "principal_occupation": "Director de cine y escritor surrealista",
    },
)

# 1.9 Max Aub (Escritor y diplomático que gestionó el encargo de Guernica a Picasso)
max_aub_id = get_or_create_person(
    PersonInput(
        name="Max Aub",
        aliases=["Max Aub Mohrenwitz"],
        description=(
            "Célebre escritor, dramaturgo y diplomático hispanomexicano. Como agregado cultural de la Embajada de la República Española en París en 1937, "
            "gestionó junto con Luis Buñuel el encargo oficial de 'Guernica' a Pablo Picasso para el Pabellón Español."
        ),
        country="ES",
        city_born="París",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/aa/Max_Aub.jpg/800px-Max_Aub.jpg",
        wikidata_id="Q705355",
        birth=HistoricalDate(year=1903, month=6, day=2, precision="day"),
        death=HistoricalDate(year=1972, month=7, day=22, precision="day"),
    ),
    {
        "real_name": "Max Aub Mohrenwitz",
        "best_known_for": "Max Aub",
        "principal_occupation": "Escritor y diplomático hispanomexicano",
    },
)

# 1.10 Diego Rivera (Diego María de la Concepción Juan Nepomuceno Estanislao de la Rivera y Barrientos Acosta y Rodríguez)
diego_rivera_id = get_or_create_person(
    PersonInput(
        name="Diego Rivera",
        aliases=["Diego María Rivera", "Diego Rivera Barrientos"],
        description=(
            "Ilustre pintor y muralista mexicano de renombre universal, figura central del Renacimiento Muralista Mexicano. "
            "Residió en París (1911–1920) donde trabó estrecha amistad y debate artístico cubista con Pablo Picasso."
        ),
        country="MX",
        city_born="Guanajuato",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Diego_Rivera_1932.jpg/800px-Diego_Rivera_1932.jpg",
        wikidata_id="Q326969",
        birth=HistoricalDate(year=1886, month=12, day=8, precision="day"),
        death=HistoricalDate(year=1957, month=11, day=24, precision="day"),
    ),
    {
        "real_name": "Diego María Rivera y Barrientos",
        "best_known_for": "Diego Rivera",
        "principal_occupation": "Pintor y muralista",
    },
)

# 1.11 Frida Kahlo (Magdalena Carmen Frida Kahlo Calderón)
frida_kahlo_id = get_or_create_person(
    PersonInput(
        name="Frida Kahlo",
        aliases=["Magdalena Carmen Frida Kahlo Calderón"],
        description=(
            "Pintora mexicana universalmente aclamada por sus autorretratos y expresión de la identidad y el dolor. "
            "En la primavera de 1939 conoció a Pablo Picasso en París, quien la elogió efusivamente y le obsequió los famosos pendientes en forma de manos."
        ),
        country="MX",
        city_born="Coyoacán",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/0/06/Frida_Kahlo%2C_by_Guillermo_Kahlo.jpg/800px-Frida_Kahlo%2C_by_Guillermo_Kahlo.jpg",
        wikidata_id="Q5588",
        birth=HistoricalDate(year=1907, month=7, day=6, precision="day"),
        death=HistoricalDate(year=1954, month=7, day=13, precision="day"),
    ),
    {
        "real_name": "Magdalena Carmen Frida Kahlo Calderón",
        "best_known_for": "Frida Kahlo",
        "principal_occupation": "Pintora",
    },
)

# 1.12 Pablo Picasso (Pablo Ruiz Picasso)
picasso_id = get_or_create_person(
    PersonInput(
        name="Pablo Picasso",
        aliases=["Pablo Ruiz Picasso"],
        description=(
            "Genio indiscutible de las artes plásticas del siglo XX, pintor y escultor español, cofundador del cubismo y autor de 'Guernica' y 'Las señoritas de Avignon'. "
            "Su obra transformó radicalmente el curso del arte contemporáneo."
        ),
        country="ES",
        city_born="Málaga",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/9/98/Pablo_picasso_1.jpg/800px-Pablo_picasso_1.jpg",
        wikidata_id="Q5593",
        birth=HistoricalDate(year=1881, month=10, day=25, precision="day"),
        death=HistoricalDate(year=1973, month=4, day=8, precision="day"),
    ),
    {
        "real_name": "Pablo Ruiz Picasso",
        "best_known_for": "Pablo Picasso",
        "principal_occupation": "Pintor, escultor y grabador, creador del cubismo",
    },
)

# ==============================================================================
# 2. ORGANIZACIONES Y OBRAS (Contextos compartidos reales)
# ==============================================================================
print("\n--- 2. Verificando / Creando Organizaciones y Obras ---")

# Organización: Lucha Libre AAA Worldwide
aaa_org_id = get_or_create_organization(
    OrganizationInput(
        name="Lucha Libre AAA Worldwide",
        kind="team",
        description="Empresa y elenco profesional de lucha libre mexicana fundada en 1992 por Antonio Peña Herrada.",
    )
)

# Obra cinematográfica 1: Santo en el museo de cera (1963)
museo_cera_id = get_or_create_work(
    WorkInput(
        name="Santo en el museo de cera",
        kind="film",
        period=Period(
            start=HistoricalDate(year=1963, precision="year"),
            end=HistoricalDate(year=1963, precision="year"),
        ),
        description="Largometraje clásico de misterio y suspenso dirigido por Alfonso Corona Blake, protagonizado por El Santo y Claudio Brook.",
    )
)

# Obra cinematográfica 2: Simón del desierto (1965)
simon_desierto_id = get_or_create_work(
    WorkInput(
        name="Simón del desierto",
        kind="film",
        period=Period(
            start=HistoricalDate(year=1965, precision="year"),
            end=HistoricalDate(year=1965, precision="year"),
        ),
        description="Obra maestra surrealista dirigida por Luis Buñuel, protagonizada por Claudio Brook y Silvia Pinal, galardonada con el Premio Especial del Jurado en el Festival de Venecia.",
    )
)

# ==============================================================================
# 3. FUENTES DOCUMENTALES (Con ubicación geográfica precisa)
# ==============================================================================
print("\n--- 3. Verificando / Creando Fuentes Documentales ---")

source_aaa = get_or_create_source(
    SourceInput(
        title="Historia Oficial y Rosters de Lucha Libre AAA Worldwide (1992–2020)",
        url="https://luchalibreaaa.com/historia/",
        publisher="Lucha Libre AAA Worldwide / Televisa Deportes",
        author="AAA Récords y Prensa",
        location=LocationInput(
            name="Sede Central de Lucha Libre AAA Worldwide",
            city="Ciudad de México",
            country="MX",
            lat=19.4978,
            lng=-99.2275,
        ),
    )
)

source_santo_family = get_or_create_source(
    SourceInput(
        title="El Santo, el Enmascarado de Plata: Biografía y Archivo Familiar de Rodolfo Guzmán Huerta",
        citation="Guzmán Rodríguez, Jorge. 'El Santo: Memoria y linaje del Enmascarado de Plata', Conaculta / Editorial Planeta, 2012.",
        publisher="Consejo Nacional para la Cultura y las Artes (Conaculta)",
        author="Jorge Ernesto Guzmán Rodríguez (El Hijo del Santo)",
        location=LocationInput(
            name="Museo del Santo / Registro Civil de Tulancingo y CDMX",
            city="Ciudad de México",
            country="MX",
            lat=19.4326,
            lng=-99.1332,
        ),
    )
)

source_museo_cera = get_or_create_source(
    SourceInput(
        title="Ficha Filmográfica Oficial: 'Santo en el museo de cera' (1963)",
        url="https://www.cinetecanacional.net/pelicula/santo-en-el-museo-de-cera",
        publisher="Cineteca Nacional de México / Filmadora Panamericana",
        author="Cineteca Nacional - Centro de Documentación e Investigación",
        location=LocationInput(
            name="Cineteca Nacional de México",
            city="Ciudad de México",
            country="MX",
            lat=19.3601,
            lng=-99.1645,
        ),
    )
)

source_simon_desierto = get_or_create_source(
    SourceInput(
        title="Ficha Oficial de Producción y Rodaje: 'Simón del desierto' de Luis Buñuel (1965)",
        citation="Gubern, Román y Hammond, Paul. 'Los años rojos de Luis Buñuel', Ediciones Cátedra, Madrid, 2009.",
        publisher="Cátedra / Filmoteca Española / Cineteca Nacional",
        author="Román Gubern & Paul Hammond",
        location=LocationInput(
            name="Estudios Churubusco Azteca",
            city="Ciudad de México",
            country="MX",
            lat=19.3556,
            lng=-99.1417,
        ),
    )
)

source_bunuel_picasso = get_or_create_source(
    SourceInput(
        title="Memorias de Luis Buñuel: 'Mi último suspiro' - El Pabellón de París de 1937 y el encargo del Guernica",
        citation="Buñuel, Luis. 'Mi último suspiro' (Mon dernier soupir), cap. 'La guerra de España: París y el Guernica', Plaza & Janés / Éditions Robert Laffont, 1982.",
        publisher="Plaza & Janés Editores",
        author="Luis Buñuel Portolés",
        location=LocationInput(
            name="Taller de Pablo Picasso, 7 Rue des Grands-Augustins",
            city="París",
            country="FR",
            lat=48.8546,
            lng=2.3387,
        ),
    )
)

source_pinal_rivera = get_or_create_source(
    SourceInput(
        title="Autobiografía de Silvia Pinal: Sesiones del 'Retrato de Silvia Pinal' con Diego Rivera",
        citation="Pinal, Silvia. 'Esta soy yo', Editorial Porrúa, México, 2015, pp. 110-118.",
        publisher="Editorial Porrúa / Museo Casa Estudio Diego Rivera y Frida Kahlo",
        author="Silvia Pinal Hidalgo",
        location=LocationInput(
            name="Casa Estudio Diego Rivera y Frida Kahlo en San Ángel",
            city="Ciudad de México",
            country="MX",
            lat=19.3496,
            lng=-99.1963,
        ),
    )
)

source_rivera_picasso = get_or_create_source(
    SourceInput(
        title="La vida fabulosa de Diego Rivera: La etapa de Montparnasse y la amistad con Pablo Picasso",
        citation="Wolfe, Bertram D. 'The Fabulous Life of Diego Rivera', Stein and Day, New York, 1963, cap. 'Cubism and Picasso'.",
        publisher="Stein and Day / Fondo de Cultura Económica",
        author="Bertram D. Wolfe",
        location=LocationInput(
            name="Estudios de Montparnasse",
            city="París",
            country="FR",
            lat=48.8421,
            lng=2.3219,
        ),
    )
)

source_frida_picasso = get_or_create_source(
    SourceInput(
        title="Frida: Una biografía de Frida Kahlo - La exposición 'Mexique' en París y el encuentro con Picasso",
        citation="Herrera, Hayden. 'Frida: A Biography of Frida Kahlo', Harper & Row, New York, 1983, cap. 'Paris 1939'.",
        publisher="Harper & Row / Editorial Diana",
        author="Hayden Herrera",
        location=LocationInput(
            name="Galerie Renou et Colle / Estudio de Picasso",
            city="París",
            country="FR",
            lat=48.8708,
            lng=2.3134,
        ),
    )
)

source_diego_frida = get_or_create_source(
    SourceInput(
        title="Acta Matrimonial de Diego Rivera y Frida Kahlo",
        citation="Registro Civil de la Ciudad de México, Acta de Matrimonio No. 256, Delegación Coyoacán, 21 de agosto de 1929.",
        publisher="Registro Civil de la Ciudad de México",
        author="Juez del Registro Civil de Coyoacán",
        location=LocationInput(
            name="Juzgado del Registro Civil de Coyoacán",
            city="Ciudad de México",
            country="MX",
            lat=19.3498,
            lng=-99.1622,
        ),
    )
)

# ==============================================================================
# 4. HECHOS (Fechas por año para equipos/obras, fecha completa para encuentros)
# ==============================================================================
print("\n--- 4. Conectando Hechos con Fechas y Lugares ---")

# 4.1 LA PARKA en Lucha Libre AAA Worldwide (Mismo equipo, precisión de año)
get_or_create_verified_fact(
    FactInput(
        type_id="sports.same_team",
        subject_id=parka_id,
        object_id=aaa_org_id,
        period=Period(
            start=HistoricalDate(year=1992, precision="year"),
            end=HistoricalDate(year=2020, precision="year"),
        ),
        source_id=source_aaa,
        source_locator="Roster estelar histórico de Lucha Libre AAA 1992-2020, titular del personaje de La Parka desde 1996 hasta su fallecimiento en 2020.",
        note="Jesús Alfonso Huerta Escoboza militó en Lucha Libre AAA Worldwide desde su año fundacional de 1992 hasta 2020, consagrándose como la máxima figura de la empresa.",
        status="draft",
        location=LocationInput(
            name="Giras y Eventos Televisados de Lucha Libre AAA",
            city="Ciudad de México",
            country="MX",
            lat=19.4978,
            lng=-99.2275,
        ),
    )
)

# 4.2 EL HIJO DEL SANTO en Lucha Libre AAA Worldwide (Mismo equipo, precisión de año)
get_or_create_verified_fact(
    FactInput(
        type_id="sports.same_team",
        subject_id=hijo_santo_id,
        object_id=aaa_org_id,
        period=Period(
            start=HistoricalDate(year=1992, precision="year"),
            end=HistoricalDate(year=1995, precision="year"),
        ),
        source_id=source_aaa,
        source_locator="Roster inaugural de Lucha Libre AAA 1992-1995, figura estelar en Triplemanía I (1993), Triplemanía II (1994) y Triplemanía III (1995).",
        note="El Hijo del Santo formó parte del elenco fundador de Lucha Libre AAA Worldwide entre 1992 y 1995, encabezando carteleras históricas junto al elenco de Antonio Peña.",
        status="draft",
        location=LocationInput(
            name="Plaza de Toros México / Giras AAA",
            city="Ciudad de México",
            country="MX",
            lat=19.3826,
            lng=-99.1795,
        ),
    )
)

# 4.3 L.A. PARK en Lucha Libre AAA Worldwide (Involucrado directo en la disputa de la máscara)
get_or_create_verified_fact(
    FactInput(
        type_id="sports.same_team",
        subject_id=la_park_id,
        object_id=aaa_org_id,
        period=Period(
            start=HistoricalDate(year=1992, precision="year"),
            end=HistoricalDate(year=2013, precision="year"),
        ),
        source_id=source_aaa,
        source_locator="Roster de Lucha Libre AAA 1992-1996 y 2010-2013; lucha estelar en Triplemanía XVIII por el nombre de La Parka.",
        note="Adolfo Tapia compitió en Lucha Libre AAA Worldwide como creador del personaje en los noventa y regresó en 2010 para la célebre rivalidad con Jesús Huerta.",
        status="draft",
        location=LocationInput(
            name="Palacio de los Deportes / Giras AAA",
            city="Ciudad de México",
            country="MX",
            lat=19.4042,
            lng=-99.0963,
        ),
    )
)

# 4.4 PARENTESCO: El Santo es padre de El Hijo del Santo (Fecha completa de nacimiento)
get_or_create_verified_fact(
    FactInput(
        type_id="family.parent_of",
        subject_id=santo_id,
        object_id=hijo_santo_id,
        period=Period(
            start=HistoricalDate(year=1963, month=8, day=2, precision="day"),
            end=HistoricalDate(year=1963, month=8, day=2, precision="day"),
        ),
        source_id=source_santo_family,
        source_locator="Registro Civil de la Ciudad de México y biografía 'El Santo: Memoria y linaje del Enmascarado de Plata', p. 45.",
        note="Rodolfo Guzmán Huerta (El Santo) es padre biológico de Jorge Ernesto Guzmán Rodríguez (El Hijo del Santo), nacido en la Ciudad de México el 2 de agosto de 1963.",
        status="draft",
        location=LocationInput(
            name="Ciudad de México",
            city="Ciudad de México",
            country="MX",
            lat=19.4326,
            lng=-99.1332,
        ),
    )
)

# 4.5 CINE: El Santo y Claudio Brook coprotagonizan 'Santo en el museo de cera' (1963)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=santo_id,
        object_id=museo_cera_id,
        role="actor",
        period=Period(
            start=HistoricalDate(year=1963, precision="year"),
            end=HistoricalDate(year=1963, precision="year"),
        ),
        source_id=source_museo_cera,
        source_locator="Créditos estelares del filme 'Santo en el museo de cera' (1963), personaje protagonista 'El Santo'.",
        note="El Santo protagonizó como héroe epónimo la película de culto 'Santo en el museo de cera' de Alfonso Corona Blake en 1963.",
        status="draft",
        location=LocationInput(
            name="Estudios América y Centro Histórico",
            city="Ciudad de México",
            country="MX",
            lat=19.3248,
            lng=-99.1396,
        ),
    )
)

get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=brook_id,
        object_id=museo_cera_id,
        role="actor",
        period=Period(
            start=HistoricalDate(year=1963, precision="year"),
            end=HistoricalDate(year=1963, precision="year"),
        ),
        source_id=source_museo_cera,
        source_locator="Créditos del filme 'Santo en el museo de cera' (1963), papel del Dr. Karol (antagonista principal).",
        note="Claudio Brook interpretó al enigmático escultor y antagonista Dr. Karol en 'Santo en el museo de cera' (1963), compartiendo cartel estelar con El Santo.",
        status="draft",
        location=LocationInput(
            name="Estudios América y Centro Histórico",
            city="Ciudad de México",
            country="MX",
            lat=19.3248,
            lng=-99.1396,
        ),
    )
)

get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=ruben_rojo_id,
        object_id=museo_cera_id,
        role="actor",
        period=Period(
            start=HistoricalDate(year=1963, precision="year"),
            end=HistoricalDate(year=1963, precision="year"),
        ),
        source_id=source_museo_cera,
        source_locator="Créditos del filme 'Santo en el museo de cera' (1963), papel de Ricardo Carbajal.",
        note="Rubén Rojo coprotagonizó 'Santo en el museo de cera' como el periodista Ricardo Carbajal junto a El Santo y Claudio Brook.",
        status="draft",
        location=LocationInput(
            name="Estudios América",
            city="Ciudad de México",
            country="MX",
            lat=19.3248,
            lng=-99.1396,
        ),
    )
)

# 4.6 CINE: Claudio Brook, Silvia Pinal y Luis Buñuel en 'Simón del desierto' (1965)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=brook_id,
        object_id=simon_desierto_id,
        role="actor",
        period=Period(
            start=HistoricalDate(year=1965, precision="year"),
            end=HistoricalDate(year=1965, precision="year"),
        ),
        source_id=source_simon_desierto,
        source_locator="Créditos de 'Simón del desierto' (1965), papel protagónico titular de Simón el Estilita.",
        note="Claudio Brook encarnó al santo anacoreta Simón el Estilita en el largometraje 'Simón del desierto' dirigido por Luis Buñuel.",
        status="draft",
        location=LocationInput(
            name="Desierto de los Leones y Estudios Churubusco",
            city="Ciudad de México",
            country="MX",
            lat=19.3556,
            lng=-99.1417,
        ),
    )
)

get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=pinal_id,
        object_id=simon_desierto_id,
        role="actor",
        period=Period(
            start=HistoricalDate(year=1965, precision="year"),
            end=HistoricalDate(year=1965, precision="year"),
        ),
        source_id=source_simon_desierto,
        source_locator="Créditos de 'Simón del desierto' (1965), papel estelar femenino de la tentación diabólica.",
        note="Silvia Pinal coprotagonizó 'Simón del desierto' encarnando al diablo que seduce a Simón (Claudio Brook), bajo la dirección de Luis Buñuel.",
        status="draft",
        location=LocationInput(
            name="Desierto de los Leones y Estudios Churubusco",
            city="Ciudad de México",
            country="MX",
            lat=19.3556,
            lng=-99.1417,
        ),
    )
)

get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=bunuel_id,
        object_id=simon_desierto_id,
        role="director",
        period=Period(
            start=HistoricalDate(year=1965, precision="year"),
            end=HistoricalDate(year=1965, precision="year"),
        ),
        source_id=source_simon_desierto,
        source_locator="Créditos de dirección y guion de 'Simón del desierto' (1965).",
        note="Luis Buñuel escribió y dirigió 'Simón del desierto' (1965), reuniendo en el elenco estelar a Claudio Brook y Silvia Pinal.",
        status="draft",
        location=LocationInput(
            name="Estudios Churubusco",
            city="Ciudad de México",
            country="MX",
            lat=19.3556,
            lng=-99.1417,
        ),
    )
)

get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=brook_id,
        object_id=simon_desierto_id,
        role="performer",
        period=Period(
            start=HistoricalDate(year=1965, precision="year"),
            end=HistoricalDate(year=1965, precision="year"),
        ),
        source_id=source_simon_desierto,
        source_locator="Créditos de actuación de 'Simón del desierto' (1965).",
        note="Claudio Brook colaboró como intérprete principal bajo la dirección directa de Luis Buñuel en 'Simón del desierto'.",
        status="draft",
        location=LocationInput(
            name="Estudios Churubusco",
            city="Ciudad de México",
            country="MX",
            lat=19.3556,
            lng=-99.1417,
        ),
    )
)

# 4.7 ENCUENTRO HISTÓRICO: Luis Buñuel <-> Pablo Picasso (Fecha completa: 20 de mayo de 1937)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=bunuel_id,
        object_id=picasso_id,
        period=Period(
            start=HistoricalDate(year=1937, month=5, day=20, precision="day"),
            end=HistoricalDate(year=1937, month=5, day=20, precision="day"),
        ),
        source_id=source_bunuel_picasso,
        source_locator="Buñuel, 'Mi último suspiro', cap. 'La guerra de España: París y el Guernica', pp. 162-168.",
        note=(
            "Luis Buñuel, como responsable de propaganda cultural de la Embajada de la República Española en París, "
            "se reunió personalmente con Pablo Picasso en su taller de la Rue des Grands-Augustins en mayo de 1937 para coordinar "
            "la creación, encargo e instalación del monumental cuadro 'Guernica' en el Pabellón Español de la Exposición Internacional."
        ),
        status="draft",
        location=LocationInput(
            name="Taller de Pablo Picasso, 7 Rue des Grands-Augustins",
            city="París",
            country="FR",
            lat=48.8546,
            lng=2.3387,
        ),
    )
)

# 4.8 ENCUENTRO HISTÓRICO: Max Aub <-> Pablo Picasso (Fecha completa: 28 de mayo de 1937)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=max_aub_id,
        object_id=picasso_id,
        period=Period(
            start=HistoricalDate(year=1937, month=5, day=28, precision="day"),
            end=HistoricalDate(year=1937, month=5, day=28, precision="day"),
        ),
        source_id=source_bunuel_picasso,
        source_locator="Recibo oficial de pago de 150.000 francos firmado por Pablo Picasso y entregado por Max Aub, Archivo Histórico Nacional de España, 28 de mayo de 1937.",
        note=(
            "Max Aub, agregado cultural de la Embajada de España en París, se reunió con Pablo Picasso en su taller parisino el 28 de mayo de 1937 "
            "para entregarle el cheque de 150.000 francos por el encargo de 'Guernica' para el Pabellón de la República Española."
        ),
        status="draft",
        location=LocationInput(
            name="Embajada de España / Taller de Grands-Augustins",
            city="París",
            country="FR",
            lat=48.8546,
            lng=2.3387,
        ),
    )
)

# 4.9 ENLACES CRUZADOS: Diego Rivera <-> Silvia Pinal (Fecha completa: 3 de noviembre de 1956)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=diego_rivera_id,
        object_id=pinal_id,
        period=Period(
            start=HistoricalDate(year=1956, month=11, day=3, precision="day"),
            end=HistoricalDate(year=1956, month=11, day=3, precision="day"),
        ),
        source_id=source_pinal_rivera,
        source_locator="Pinal, Silvia. 'Esta soy yo', pp. 110-118; fecha de dedicatoria y firma del óleo sobre tela 'Retrato de Silvia Pinal', 3 de noviembre de 1956.",
        note=(
            "Diego Rivera recibió a Silvia Pinal en su estudio de San Ángel para posar en las sesiones de su emblemático retrato al óleo, "
            "entregado y firmado por el maestro muralista el 3 de noviembre de 1956."
        ),
        status="draft",
        location=LocationInput(
            name="Estudio de Diego Rivera en San Ángel",
            city="Ciudad de México",
            country="MX",
            lat=19.3496,
            lng=-99.1963,
        ),
    )
)

# 4.10 ENLACES CRUZADOS: Diego Rivera <-> Pablo Picasso (París, 1914)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=diego_rivera_id,
        object_id=picasso_id,
        period=Period(
            start=HistoricalDate(year=1914, precision="year"),
            end=HistoricalDate(year=1915, precision="year"),
        ),
        source_id=source_rivera_picasso,
        source_locator="Wolfe, Bertram D. 'The Fabulous Life of Diego Rivera', pp. 68-75, visitas a los talleres de Rue Schoelcher y debate sobre el cubismo sintético.",
        note=(
            "Diego Rivera y Pablo Picasso forjaron una estrecha amistad y colaboración artística en Montparnasse, París, hacia 1914, "
            "donde Rivera visitaba el taller de Picasso para debatir las premisas del cubismo."
        ),
        status="draft",
        location=LocationInput(
            name="Talleres de Montparnasse",
            city="París",
            country="FR",
            lat=48.8421,
            lng=2.3219,
        ),
    )
)

# 4.11 ENLACES CRUZADOS: Frida Kahlo <-> Pablo Picasso (Fecha completa: 25 de marzo de 1939)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=frida_kahlo_id,
        object_id=picasso_id,
        period=Period(
            start=HistoricalDate(year=1939, month=3, day=25, precision="day"),
            end=HistoricalDate(year=1939, month=3, day=25, precision="day"),
        ),
        source_id=source_frida_picasso,
        source_locator="Herrera, Hayden. 'Frida: A Biography of Frida Kahlo', pp. 248-254; carta de Picasso a Diego Rivera (París, marzo de 1939).",
        note=(
            "Pablo Picasso conoció personalmente a Frida Kahlo en París en marzo de 1939 durante su exposición 'Mexique' en la Galerie Renou et Colle; "
            "Picasso elogió su destreza pictórica y le regaló los célebres aretes de carey en forma de manos."
        ),
        status="draft",
        location=LocationInput(
            name="Galerie Renou et Colle / Taller de Picasso",
            city="París",
            country="FR",
            lat=48.8708,
            lng=2.3134,
        ),
    )
)

# 4.12 ENLACES CRUZADOS: Diego Rivera <-> Frida Kahlo (Cónyuges, fecha completa: 21 de agosto de 1929)
get_or_create_verified_fact(
    FactInput(
        type_id="family.spouse_of",
        subject_id=diego_rivera_id,
        object_id=frida_kahlo_id,
        period=Period(
            start=HistoricalDate(year=1929, month=8, day=21, precision="day"),
            end=HistoricalDate(year=1954, month=7, day=13, precision="day"),
        ),
        source_id=source_diego_frida,
        source_locator="Acta de Matrimonio No. 256, Juzgado de Coyoacán, Ciudad de México, 21 de agosto de 1929.",
        note=(
            "Diego Rivera y Frida Kahlo contrajeron matrimonio solemne en la delegación Coyoacán el 21 de agosto de 1929, "
            "conformando una de las alianzas artísticas y conyugales más universales de la historia del arte."
        ),
        status="draft",
        location=LocationInput(
            name="Coyoacán",
            city="Ciudad de México",
            country="MX",
            lat=19.3498,
            lng=-99.1622,
        ),
    )
)

# ==============================================================================
# 5. VERIFICACIÓN DEL CAMINO MÁS CORTO EN NEO4J
# ==============================================================================
print("\n================================================================================")
print("  CONSULTANDO CAMINO MÁS CORTO: LA PARKA -> PABLO PICASSO")
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
                WHEN 'Organization' IN labels(n) THEN {
                    tipo: 'Organization', 
                    id: n.id, 
                    nombre: n.search_name
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
        start_id=parka_id,
        target_id=picasso_id,
    ).single()

    if res:
        print(f"Camino encontrado! Longitud de relaciones: {res['longitud_relaciones']}")
        for step in res["camino"]:
            print(" ", json.dumps(step, ensure_ascii=False))
    else:
        print("ERROR: No se encontró camino.")

print("\n--- Validando vistas de conexión derivadas (connection_preview) ---")
for person_name, pid in [("La Parka", parka_id), ("El Santo", santo_id), ("Claudio Brook", brook_id), ("Luis Buñuel", bunuel_id), ("Pablo Picasso", picasso_id)]:
    print(f"\nConexiones directas derivadas de {person_name}:")
    conns = connection_preview(repo, pid)
    for c in conns:
        other = repo.get("people", c["person_id"])
        ctx_name = ""
        if c.get("context_id"):
            try:
                ctx_name = f" mediante {repo.get('organizations', c['context_id']).get('name')}"
            except Exception:
                try:
                    ctx_name = f" mediante {repo.get('works', c['context_id']).get('name')}"
                except Exception:
                    pass
        print(f"  -> {c['type_id']} con {other.get('name')}{ctx_name} ({c['direction']})")
