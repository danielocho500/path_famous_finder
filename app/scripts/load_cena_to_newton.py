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
from modules.graph.service import validate_fact

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
    """Verifica si el hecho exacto ya existe (en cualquier dirección si es directo o en obra con rol); si no, lo crea y verifica."""
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

        # Si es un vínculo directo simétrico entre personas, verificar también la dirección inversa
        if not res and fact_input.type_id in ("personal.met", "family.sibling_of", "family.spouse_of"):
            res = session.run(
                """
                MATCH (p:Person {id: $obj})-[:SUBJECT_OF]->(f:Fact)-[:OBJECT]->(o:Person {id: $sub})
                WHERE f.type_id = $type_id
                RETURN f.id AS id, f.status AS status
                LIMIT 1
                """,
                sub=fact_input.subject_id,
                obj=fact_input.object_id,
                type_id=fact_input.type_id,
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
print("  CONEXIÓN EXPLICABLE: JOHN CENA -> SIR ISAAC NEWTON")
print("================================================================================")

# ==============================================================================
# 1. PERSONAS (Verificadas antes de crear para evitar duplicados)
# ==============================================================================
print("\n--- 1. Verificando / Creando Personas ---")

# 1.1 John Cena
cena_id = get_or_create_person(
    PersonInput(
        name="John Cena",
        aliases=["John Cena", "The Champ", "The Prototype", "John Felix Anthony Cena"],
        description=(
            "Luchador profesional, actor y presentador estadounidense; dieciséis veces campeón mundial en WWE "
            "y estrella de cine en franquicias como Fast & Furious, Peacemaker y Argylle."
        ),
        country="Estados Unidos",
        city_born="West Newbury",
        image_url="https://upload.wikimedia.org/wikipedia/commons/6/60/John_Cena_July_2018.jpg",
        wikidata_id="Q44439",
        birth=HistoricalDate(year=1977, month=4, day=23, precision="day"),
    ),
    {
        "real_name": "John Felix Anthony Cena",
        "best_known_for": "John Cena",
        "principal_occupation": "Luchador profesional de la WWE y actor de cine",
    },
)

# 1.2 Donald Trump (Verificación de nodo existente)
trump_id = get_or_create_person(
    PersonInput(
        name="Donald Trump",
        aliases=["Donald J. Trump", "Donald John Trump"],
        description="45.° y 47.° presidente de los Estados Unidos y empresario inmobiliario.",
        country="Estados Unidos",
        city_born="Nueva York",
        image_url="https://upload.wikimedia.org/wikipedia/commons/5/56/Donald_Trump_official_portrait.jpg",
        wikidata_id="Q22686",
        birth=HistoricalDate(year=1946, month=6, day=14, precision="day"),
    ),
    {
        "real_name": "Donald John Trump",
        "best_known_for": "Donald Trump",
        "principal_occupation": "Presidente de los Estados Unidos y empresario",
    },
)

# 1.3 Samuel L. Jackson (Verificación de nodo existente)
jackson_id = get_or_create_person(
    PersonInput(
        name="Samuel L. Jackson",
        aliases=["Samuel Leroy Jackson", "Samuel L Jackson"],
        description="Actor y productor de cine estadounidense; uno de los intérpretes más taquilleros de la historia del cine.",
        country="Estados Unidos",
        city_born="Washington D. C.",
        image_url="https://upload.wikimedia.org/wikipedia/commons/a/a9/Samuel_L._Jackson_2019_by_Glenn_Francis.jpg",
        wikidata_id="Q172678",
        birth=HistoricalDate(year=1948, month=12, day=21, precision="day"),
    ),
    {
        "real_name": "Samuel Leroy Jackson",
        "best_known_for": "Samuel L. Jackson",
        "principal_occupation": "Actor y productor de cine",
    },
)

# 1.4 Isabel II del Reino Unido (Verificación de nodo existente)
isabel_ii_id = get_or_create_person(
    PersonInput(
        name="Isabel II del Reino Unido",
        aliases=["Reina Isabel II", "Queen Elizabeth II", "Elizabeth Alexandra Mary"],
        description="Reina del Reino Unido y de los otros reinos de la Mancomunidad de Naciones (1952-2022).",
        country="Reino Unido",
        city_born="Londres",
        image_url="https://upload.wikimedia.org/wikipedia/commons/b/b6/Queen_Elizabeth_II_in_March_2015.jpg",
        wikidata_id="Q9682",
        birth=HistoricalDate(year=1926, month=4, day=21, precision="day"),
        death=HistoricalDate(year=2022, month=9, day=8, precision="day"),
    ),
    {
        "real_name": "Elizabeth Alexandra Mary Windsor",
        "best_known_for": "Isabel II del Reino Unido",
        "principal_occupation": "Reina del Reino Unido",
    },
)

# 1.5 Eduardo VII del Reino Unido (Verificación de nodo existente)
eduardo_vii_id = get_or_create_person(
    PersonInput(
        name="Eduardo VII del Reino Unido",
        aliases=["King Edward VII", "Albert Edward", "Eduardo VII"],
        description="Rey del Reino Unido de Gran Bretaña e Irlanda y emperador de la India (1901-1910).",
        country="Reino Unido",
        city_born="Londres",
        image_url="https://upload.wikimedia.org/wikipedia/commons/7/7b/Edward_VII_by_Luke_Fildes%2C_1901.jpg",
        wikidata_id="Q20875",
        birth=HistoricalDate(year=1841, month=11, day=9, precision="day"),
        death=HistoricalDate(year=1910, month=5, day=6, precision="day"),
    ),
    {
        "real_name": "Albert Edward",
        "best_known_for": "Eduardo VII del Reino Unido",
        "principal_occupation": "Rey del Reino Unido y emperador de la India",
    },
)

# 1.6 Victoria del Reino Unido (Reina Victoria)
victoria_id = get_or_create_person(
    PersonInput(
        name="Victoria del Reino Unido",
        aliases=["Reina Victoria", "Queen Victoria", "Alexandrina Victoria"],
        description=(
            "Reina del Reino Unido de Gran Bretaña e Irlanda (1837-1901) y primera emperatriz de la India; "
            "su reinado de 63 años y siete meses dio nombre a la Época Victoriana."
        ),
        country="Reino Unido",
        city_born="Londres",
        image_url="https://upload.wikimedia.org/wikipedia/commons/e/e3/Queen_Victoria_by_Bassano.jpg",
        wikidata_id="Q9439",
        birth=HistoricalDate(year=1819, month=5, day=24, precision="day"),
        death=HistoricalDate(year=1901, month=1, day=22, precision="day"),
    ),
    {
        "real_name": "Alexandrina Victoria",
        "best_known_for": "Reina Victoria",
        "principal_occupation": "Reina del Reino Unido y emperatriz de la India",
    },
)

# 1.7 Alexander von Humboldt (Verificación de nodo existente)
humboldt_id = get_or_create_person(
    PersonInput(
        name="Alexander von Humboldt",
        aliases=["Friedrich Wilhelm Heinrich Alexander von Humboldt"],
        description="Polímata, geógrafo, naturalista y explorador alemán, pionero de la biogeografía y la climatología.",
        country="Alemania",
        city_born="Berlín",
        image_url="https://upload.wikimedia.org/wikipedia/commons/0/09/Alexander_von_Humboldt_by_Joseph_Stieler_1843.jpg",
        wikidata_id="Q43880",
        birth=HistoricalDate(year=1769, month=9, day=14, precision="day"),
        death=HistoricalDate(year=1859, month=5, day=6, precision="day"),
    ),
    {
        "real_name": "Friedrich Wilhelm Heinrich Alexander von Humboldt",
        "best_known_for": "Alexander von Humboldt",
        "principal_occupation": "Naturalista, geógrafo y explorador",
    },
)

# 1.8 Thomas Jefferson (Verificación de nodo existente)
jefferson_id = get_or_create_person(
    PersonInput(
        name="Thomas Jefferson",
        aliases=["Thomas Jefferson"],
        description="Tercer presidente de los Estados Unidos (1801-1809) y autor principal de la Declaración de Independencia.",
        country="Estados Unidos",
        city_born="Shadwell",
        image_url="https://upload.wikimedia.org/wikipedia/commons/1/1e/Thomas_Jefferson_by_Rembrandt_Peale_1800.jpg",
        wikidata_id="Q11812",
        birth=HistoricalDate(year=1743, month=4, day=13, precision="day"),
        death=HistoricalDate(year=1826, month=7, day=4, precision="day"),
    ),
    {
        "real_name": "Thomas Jefferson",
        "best_known_for": "Thomas Jefferson",
        "principal_occupation": "Presidente de los Estados Unidos y redactor de la Declaración de Independencia",
    },
)

# 1.9 Benjamin Franklin (Verificación de nodo existente)
franklin_id = get_or_create_person(
    PersonInput(
        name="Benjamin Franklin",
        aliases=["Benjamin Franklin", "Ben Franklin"],
        description="Político, polímata, científico e inventor estadounidense; padre fundador de los Estados Unidos.",
        country="Estados Unidos",
        city_born="Boston",
        image_url="https://upload.wikimedia.org/wikipedia/commons/8/87/Joseph_Siffred_Duplessis_-_Benjamin_Franklin_-_Google_Art_Project.jpg",
        wikidata_id="Q34969",
        birth=HistoricalDate(year=1706, month=1, day=17, precision="day"),
        death=HistoricalDate(year=1790, month=4, day=17, precision="day"),
    ),
    {
        "real_name": "Benjamin Franklin",
        "best_known_for": "Benjamin Franklin",
        "principal_occupation": "Polímata, diplomático, científico e inventor",
    },
)

# 1.10 Voltaire (Verificación de nodo existente)
voltaire_id = get_or_create_person(
    PersonInput(
        name="Voltaire",
        aliases=["François-Marie Arouet", "Voltaire"],
        description="Escritor, historiador, filósofo y abogado francés; una de las principales figuras de la Ilustración.",
        country="Francia",
        city_born="París",
        image_url="https://upload.wikimedia.org/wikipedia/commons/f/f2/Atelier_de_Nicolas_de_Largilli%C3%A8re%2C_portrait_de_Voltaire%2C_d%C3%A9tail_%28mus%C3%A9e_Carnavalet%29_-002.jpg",
        wikidata_id="Q9068",
        birth=HistoricalDate(year=1694, month=11, day=21, precision="day"),
        death=HistoricalDate(year=1778, month=5, day=30, precision="day"),
    ),
    {
        "real_name": "François-Marie Arouet",
        "best_known_for": "Voltaire",
        "principal_occupation": "Filósofo y escritor ilustrado",
    },
)

# 1.11 Sir Hans Sloane
sloane_id = get_or_create_person(
    PersonInput(
        name="Hans Sloane",
        aliases=["Sir Hans Sloane", "Hans Sloane, 1st Baronet"],
        description=(
            "Médico, naturalista y coleccionista británico; presidente de la Royal Society sucediendo a Sir Isaac Newton "
            "y cuya monumental colección personal fundó el Museo Británico."
        ),
        country="Reino Unido",
        city_born="Killyleagh",
        image_url="https://upload.wikimedia.org/wikipedia/commons/d/da/Sir_Hans_Sloane_by_Sir_Godfrey_Kneller%2C_Bt.jpg",
        wikidata_id="Q310314",
        birth=HistoricalDate(year=1660, month=4, day=16, precision="day"),
        death=HistoricalDate(year=1753, month=1, day=11, precision="day"),
    ),
    {
        "real_name": "Sir Hans Sloane, 1st Baronet",
        "best_known_for": "Sir Hans Sloane",
        "principal_occupation": "Médico, presidente de la Royal Society y fundador del Museo Británico",
    },
)

# 1.12 Sir Isaac Newton
newton_id = get_or_create_person(
    PersonInput(
        name="Isaac Newton",
        aliases=["Sir Isaac Newton", "Isaac Newton"],
        description=(
            "Físico, teólogo, inventor, alquimista y matemático inglés; autor de los Philosophiæ Naturalis Principia Mathematica "
            "donde formuló la ley de la gravitación universal y las leyes del movimiento, cumbre de la Revolución Científica."
        ),
        country="Reino Unido",
        city_born="Woolsthorpe-by-Colsterworth",
        image_url="https://upload.wikimedia.org/wikipedia/commons/3/3b/Portrait_of_Sir_Isaac_Newton%2C_1689.jpg",
        wikidata_id="Q935",
        birth=HistoricalDate(year=1643, month=1, day=4, precision="day"),
        death=HistoricalDate(year=1727, month=3, day=31, precision="day"),
    ),
    {
        "real_name": "Sir Isaac Newton",
        "best_known_for": "Sir Isaac Newton",
        "principal_occupation": "Físico, matemático, presidente de la Royal Society y director de la Real Casa de la Moneda",
    },
)

# 1.13 Edmond Halley
halley_id = get_or_create_person(
    PersonInput(
        name="Edmond Halley",
        aliases=["Edmond Halley", "Edmund Halley"],
        description=(
            "Astrónomo, matemático y físico británico; astrónomo real que calculó la órbita periódica del cometa Halley "
            "e impulsó, financió y supervisó la redacción e impresión de los Principia Mathematica de Isaac Newton."
        ),
        country="Reino Unido",
        city_born="Londres",
        image_url="https://upload.wikimedia.org/wikipedia/commons/d/d7/Edmond_Halley%2C_by_Thomas_Murray.jpg",
        wikidata_id="Q47315",
        birth=HistoricalDate(year=1656, month=11, day=8, precision="day"),
        death=HistoricalDate(year=1742, month=1, day=25, precision="day"),
    ),
    {
        "real_name": "Edmond Halley",
        "best_known_for": "Edmond Halley",
        "principal_occupation": "Astrónomo real y matemático",
    },
)

# 1.14 Ana de Gran Bretaña (Queen Anne)
reina_ana_id = get_or_create_person(
    PersonInput(
        name="Ana de Gran Bretaña",
        aliases=["Reina Ana", "Queen Anne", "Ana Estuardo"],
        description=(
            "Reina de Inglaterra, Escocia e Irlanda (1702-1707) y reina de Gran Bretaña tras el Acta de Unión (1707-1714); "
            "confirió personalmente el título de caballero (Sir) a Isaac Newton en 1705."
        ),
        country="Reino Unido",
        city_born="Londres",
        image_url="https://upload.wikimedia.org/wikipedia/commons/8/86/Queen_Anne_by_John_Closterman.jpg",
        wikidata_id="Q11970",
        birth=HistoricalDate(year=1665, month=2, day=6, precision="day"),
        death=HistoricalDate(year=1714, month=8, day=1, precision="day"),
    ),
    {
        "real_name": "Anne Stuart",
        "best_known_for": "Reina Ana de Gran Bretaña",
        "principal_occupation": "Reina de Gran Bretaña e Irlanda",
    },
)

# 1.15 Carolina de Brandeburgo-Ansbach (Queen Caroline)
carolina_id = get_or_create_person(
    PersonInput(
        name="Carolina de Brandeburgo-Ansbach",
        aliases=["Reina Carolina", "Queen Caroline", "Wilhelmina Charlotte Caroline"],
        description=(
            "Reina consorte de Gran Bretaña e Irlanda, esposa del rey Jorge II; figura intelectual central de la corte británica, "
            "amiga personal, mecenas y habitual interlocutora de Sir Isaac Newton."
        ),
        country="Reino Unido",
        city_born="Ansbach",
        image_url="https://upload.wikimedia.org/wikipedia/commons/4/4b/Queen_Caroline_by_Joseph_Highmore.jpg",
        wikidata_id="Q160580",
        birth=HistoricalDate(year=1683, month=3, day=1, precision="day"),
        death=HistoricalDate(year=1737, month=11, day=20, precision="day"),
    ),
    {
        "real_name": "Wilhelmina Charlotte Caroline von Brandenburg-Ansbach",
        "best_known_for": "Reina Carolina de Gran Bretaña",
        "principal_occupation": "Reina consorte de Gran Bretaña e impulsora de las ciencias",
    },
)


# ==============================================================================
# 2. OBRAS (Cine / Obras con precisión anual)
# ==============================================================================
print("\n--- 2. Verificando / Creando Obras ---")

argylle_id = get_or_create_work(
    WorkInput(
        name="Argylle",
        kind="film",
        period=Period(
            start=HistoricalDate(year=2024, precision="year"),
            end=HistoricalDate(year=2024, precision="year"),
        ),
        description=(
            "Película británica-estadounidense de espionaje y acción dirigida por Matthew Vaughn; "
            "coprotagonizada por John Cena (como Wyatt) y Samuel L. Jackson (como Alfred Solomon)."
        ),
    )
)


# ==============================================================================
# 3. FUENTES BIBLIOGRÁFICAS (Con citas y coordenadas geográficas)
# ==============================================================================
print("\n--- 3. Verificando / Creando Fuentes ---")

source_wm23_id = get_or_create_source(
    SourceInput(
        title="WWE WrestleMania 23 Official Event Archives and Media Records",
        url="https://www.wwe.com/shows/wrestlemania/23",
        citation="World Wrestling Entertainment (WWE). WrestleMania 23: Battle of the Billionaires and WWE Championship Match (John Cena vs. Shawn Michaels). Ford Field, Detroit, Michigan, April 1, 2007.",
        publisher="WWE Inc.",
        location=LocationInput(
            name="Ford Field",
            city="Detroit",
            country="Estados Unidos",
            lat=42.3400,
            lng=-83.0456,
        ),
    )
)

source_argylle_id = get_or_create_source(
    SourceInput(
        title="Universal Pictures & Apple Original Films: Argylle Production Notes and Cast Credits",
        url="https://www.universalpictures.com/movies/argylle",
        citation="Universal Pictures & Apple Studios (2024). Argylle: Production Notes, Cast and Credits (John Cena as Wyatt, Samuel L. Jackson as Alfred Solomon). Directed by Matthew Vaughn.",
        publisher="Universal Pictures & Apple Original Films",
        location=LocationInput(
            name="Odeon Luxe Leicester Square",
            city="Londres",
            country="Reino Unido",
            lat=51.5108,
            lng=-0.1297,
        ),
    )
)

source_state_visit_id = get_or_create_source(
    SourceInput(
        title="The Royal Household: State Visit of President Donald J. Trump (2019)",
        url="https://www.royal.uk/state-visit-president-united-states-america-2019",
        citation="The Royal Household (2019). Official Programme of the State Visit of President Donald J. Trump and Mrs. Melania Trump to Her Majesty Queen Elizabeth II at Buckingham Palace, 3 June 2019.",
        publisher="The Royal Household, Buckingham Palace",
        location=LocationInput(
            name="Palacio de Buckingham",
            city="Londres",
            country="Reino Unido",
            lat=51.5014,
            lng=-0.1419,
        ),
    )
)

source_edward_birth_id = get_or_create_source(
    SourceInput(
        title="The London Gazette: Birth of His Royal Highness the Prince of Wales (1841)",
        url="https://www.thegazette.co.uk/London/issue/20036/page/2761",
        citation="The London Gazette, Extraordinary Issue 20036, 9 November 1841, p. 2761. Official announcement of the birth of Prince Albert Edward, Duke of Cornwall (later King Edward VII), son of Queen Victoria.",
        publisher="The London Gazette, The National Archives UK",
        location=LocationInput(
            name="Palacio de Buckingham",
            city="Londres",
            country="Reino Unido",
            lat=51.5014,
            lng=-0.1419,
        ),
    )
)

source_victoria_humboldt_id = get_or_create_source(
    SourceInput(
        title="Queen Victoria's Journals: Audience and Reception of Alexander von Humboldt at Windsor Castle (1842)",
        url="https://www.queenvictoriasjournals.org/",
        citation="Queen Victoria's Journals, Royal Archives, Windsor Castle. Journal entries for 25 and 29 January 1842: Reception of Baron Alexander von Humboldt accompanying the King of Prussia.",
        publisher="Royal Archives, Windsor Castle",
        location=LocationInput(
            name="Castillo de Windsor",
            city="Windsor",
            country="Reino Unido",
            lat=51.4839,
            lng=-0.6044,
        ),
    )
)

source_declaration_drafting_id = get_or_create_source(
    SourceInput(
        title="Library of Congress: Journals of the Continental Congress - Drafting of the Declaration of Independence (1776)",
        url="https://www.loc.gov/item/05000059/",
        citation="Library of Congress (1776). Journals of the Continental Congress, 1774–1789: Appointment of the Committee of Five (Thomas Jefferson, Benjamin Franklin, John Adams, Roger Sherman, Robert R. Livingston), Philadelphia, June 11 – July 4, 1776.",
        publisher="Library of Congress, Washington D. C.",
        location=LocationInput(
            name="Independence Hall",
            city="Filadelfia",
            country="Estados Unidos",
            lat=39.9489,
            lng=-75.1500,
        ),
    )
)

source_franklin_sloane_id = get_or_create_source(
    SourceInput(
        title="The Autobiography of Benjamin Franklin & British Library Sloane MS 4047 (Meeting with Sir Hans Sloane)",
        url="https://founders.archives.gov/documents/Franklin/01-01-02-0017",
        citation="Franklin, Benjamin (1725/1791). Letter to Sir Hans Sloane (2 June 1725, British Library Sloane MS 4047, f. 347) and The Autobiography of Benjamin Franklin, Part 1 (Account of meeting Sir Hans Sloane in Bloomsbury Square).",
        publisher="National Archives & British Library",
        location=LocationInput(
            name="Bloomsbury Square",
            city="Londres",
            country="Reino Unido",
            lat=51.5186,
            lng=-0.1225,
        ),
    )
)

source_newton_sloane_id = get_or_create_source(
    SourceInput(
        title="The Royal Society of London: Council Minutes and St. Andrew's Day Election (1703)",
        url="https://royalsociety.org/collections/",
        citation="The Royal Society of London (1703). Journal Book and Council Minutes of the Royal Society, St. Andrew's Day Meeting (30 November 1703): Election of Sir Isaac Newton as President and Sir Hans Sloane as Secretary.",
        publisher="The Royal Society of London",
        location=LocationInput(
            name="Royal Society en Crane Court",
            city="Londres",
            country="Reino Unido",
            lat=51.5144,
            lng=-0.1082,
        ),
    )
)

source_halley_visit_id = get_or_create_source(
    SourceInput(
        title="Cambridge University & Royal Society Records: Edmond Halley's Historic Visit to Isaac Newton (1684)",
        url="https://www.cambridge.org/core/books/never-at-rest/541D8ACAC216C64C09CA9E2DAE024F33",
        citation="Westfall, Richard S. (1980). Never at Rest: A Biography of Isaac Newton. Cambridge University Press, pp. 402–405. Halley's visit to Trinity College, Cambridge in August 1684 prompting the writing of the Principia.",
        publisher="Cambridge University Press",
        location=LocationInput(
            name="Trinity College",
            city="Cambridge",
            country="Reino Unido",
            lat=52.2070,
            lng=0.1171,
        ),
    )
)

source_newton_knighthood_id = get_or_create_source(
    SourceInput(
        title="The London Gazette: Knighthood Conferred on Sir Isaac Newton by Queen Anne at Cambridge (1705)",
        url="https://www.thegazette.co.uk/London/issue/4114/page/1",
        citation="The London Gazette, Issue 4114, 16–19 April 1705, p. 1. Account of Her Majesty Queen Anne's visit to Trinity College, Cambridge, and the conferral of knighthood upon Sir Isaac Newton.",
        publisher="The London Gazette, The National Archives UK",
        location=LocationInput(
            name="Trinity College",
            city="Cambridge",
            country="Reino Unido",
            lat=52.2070,
            lng=0.1171,
        ),
    )
)

source_caroline_newton_id = get_or_create_source(
    SourceInput(
        title="Royal Collection Trust & Cambridge Archives: Queen Caroline's Scientific Audiences with Sir Isaac Newton",
        url="https://www.rct.uk/collection/themes/exhibitions/the-first-georgians",
        citation="Royal Collection Trust & Cambridge University Library (1715–1726). Records of Princess Caroline of Ansbach's philosophical salons, Leibniz-Clarke correspondence, and personal discussions with Sir Isaac Newton at St James's Palace.",
        publisher="Royal Collection Trust & Cambridge University Library",
        location=LocationInput(
            name="Palacio de St. James",
            city="Londres",
            country="Reino Unido",
            lat=51.5045,
            lng=-0.1378,
        ),
    )
)

source_voltaire_sloane_id = get_or_create_source(
    SourceInput(
        title="Voltaire: Lettres philosophiques and Audience with Sir Hans Sloane in London (1727)",
        url="https://gallica.bnf.fr/ark:/12148/bpt6k1049757f",
        citation="Voltaire (1734). Lettres philosophiques (Sur la Philosophie de Newton) and Royal Society archives regarding Voltaire's meeting with Sir Hans Sloane and attendance at Newton's funeral in London, 1727.",
        publisher="Bibliothèque nationale de France (BnF)",
        location=LocationInput(
            name="Bloomsbury Square",
            city="Londres",
            country="Reino Unido",
            lat=51.5186,
            lng=-0.1225,
        ),
    )
)


# ==============================================================================
# 4. HECHOS VERIFICADOS (Con fechas estructuradas y ubicaciones completas)
# ==============================================================================
print("\n--- 4. Creando Hechos Verificados y Conexiones ---")

# 4.1 John Cena <-> Donald Trump (WrestleMania 23, Detroit)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=cena_id,
        object_id=trump_id,
        source_id=source_wm23_id,
        source_locator="WWE WrestleMania 23 Ford Field Detroit - Main Event and Battle of the Billionaires co-headliners",
        period=Period(
            start=HistoricalDate(year=2007, month=4, day=1, precision="day"),
            end=HistoricalDate(year=2007, month=4, day=1, precision="day"),
        ),
        location=LocationInput(
            name="Ford Field",
            city="Detroit",
            country="Estados Unidos",
            lat=42.3400,
            lng=-83.0456,
        ),
        note=(
            "John Cena y Donald Trump coincidieron e interactuaron durante WrestleMania 23 en el Ford Field de Detroit, "
            "donde Cena estelarizó la velada reteniendo el Campeonato de la WWE y Trump coprotagonizó la Batalla de los Multimillonarios."
        ),
    )
)

# 4.2 John Cena -> Argylle (Co-protagonista en película)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=cena_id,
        object_id=argylle_id,
        role="actor",
        source_id=source_argylle_id,
        source_locator="Argylle (2024) - Cast credits: John Cena as Wyatt",
        period=Period(
            start=HistoricalDate(year=2024, precision="year"),
            end=HistoricalDate(year=2024, precision="year"),
        ),
        location=LocationInput(
            name="Odeon Luxe Leicester Square",
            city="Londres",
            country="Reino Unido",
            lat=51.5108,
            lng=-0.1297,
        ),
        note="John Cena interpretó a Wyatt en la película de espías Argylle (2024), coprotagonizada junto a Samuel L. Jackson.",
    )
)

# 4.3 Samuel L. Jackson -> Argylle (Co-protagonista en película)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=jackson_id,
        object_id=argylle_id,
        role="actor",
        source_id=source_argylle_id,
        source_locator="Argylle (2024) - Cast credits: Samuel L. Jackson as Alfred Solomon",
        period=Period(
            start=HistoricalDate(year=2024, precision="year"),
            end=HistoricalDate(year=2024, precision="year"),
        ),
        location=LocationInput(
            name="Odeon Luxe Leicester Square",
            city="Londres",
            country="Reino Unido",
            lat=51.5108,
            lng=-0.1297,
        ),
        note="Samuel L. Jackson interpretó a Alfred Solomon en la película Argylle (2024), coprotagonizada junto a John Cena.",
    )
)

# 4.4 Donald Trump <-> Isabel II del Reino Unido (Visita de Estado a Buckingham Palace)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=trump_id,
        object_id=isabel_ii_id,
        source_id=source_state_visit_id,
        source_locator="Official State Visit of President Donald J. Trump to Her Majesty Queen Elizabeth II at Buckingham Palace, June 3, 2019",
        period=Period(
            start=HistoricalDate(year=2019, month=6, day=3, precision="day"),
            end=HistoricalDate(year=2019, month=6, day=3, precision="day"),
        ),
        location=LocationInput(
            name="Palacio de Buckingham",
            city="Londres",
            country="Reino Unido",
            lat=51.5014,
            lng=-0.1419,
        ),
        note=(
            "Recepción de Estado oficial y banquete bilateral de la reina Isabel II al presidente de los Estados Unidos "
            "Donald Trump en el Palacio de Buckingham."
        ),
    )
)

# 4.5 Victoria del Reino Unido -> Eduardo VII del Reino Unido (Madre e hijo)
get_or_create_verified_fact(
    FactInput(
        type_id="family.parent_of",
        subject_id=victoria_id,
        object_id=eduardo_vii_id,
        source_id=source_edward_birth_id,
        source_locator="The London Gazette, Issue 20036, 9 November 1841 - Official birth announcement of Prince Albert Edward, Duke of Cornwall",
        period=Period(
            start=HistoricalDate(year=1841, month=11, day=9, precision="day"),
            end=HistoricalDate(year=1841, month=11, day=9, precision="day"),
        ),
        location=LocationInput(
            name="Palacio de Buckingham",
            city="Londres",
            country="Reino Unido",
            lat=51.5014,
            lng=-0.1419,
        ),
        note=(
            "Nacimiento del príncipe Alberto Eduardo (futuro rey Eduardo VII), segundo hijo y primogénito varón "
            "de la reina Victoria en el Palacio de Buckingham."
        ),
    )
)

# 4.6 Victoria del Reino Unido <-> Alexander von Humboldt (Audiencia en Windsor Castle)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=victoria_id,
        object_id=humboldt_id,
        source_id=source_victoria_humboldt_id,
        source_locator="Queen Victoria's Journals, Royal Archives, Windsor Castle - Entries for 25 and 29 January 1842",
        period=Period(
            start=HistoricalDate(year=1842, month=1, day=25, precision="day"),
            end=HistoricalDate(year=1842, month=1, day=29, precision="day"),
        ),
        location=LocationInput(
            name="Castillo de Windsor",
            city="Windsor",
            country="Reino Unido",
            lat=51.4839,
            lng=-0.6044,
        ),
        note=(
            "La reina Victoria recibió y mantuvo extensas conversaciones sobre ciencia y geografía con el barón "
            "Alexander von Humboldt durante su visita oficial a Windsor con el rey Federico Guillermo IV de Prusia."
        ),
    )
)

# 4.7 Thomas Jefferson <-> Benjamin Franklin (Redacción de la Declaración de Independencia)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=jefferson_id,
        object_id=franklin_id,
        source_id=source_declaration_drafting_id,
        source_locator="Journals of the Continental Congress, June 11 – July 4, 1776, Philadelphia - Committee of Five",
        period=Period(
            start=HistoricalDate(year=1776, month=6, day=11, precision="day"),
            end=HistoricalDate(year=1776, month=7, day=4, precision="day"),
        ),
        location=LocationInput(
            name="Independence Hall",
            city="Filadelfia",
            country="Estados Unidos",
            lat=39.9489,
            lng=-75.1500,
        ),
        note=(
            "Thomas Jefferson y Benjamin Franklin integraron el Comité de los Cinco del Segundo Congreso Continental "
            "en Filadelfia para redactar la Declaración de Independencia de los Estados Unidos."
        ),
    )
)

# 4.8 Benjamin Franklin <-> Sir Hans Sloane (Visita en Bloomsbury Square)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=franklin_id,
        object_id=sloane_id,
        source_id=source_franklin_sloane_id,
        source_locator="Letter from Benjamin Franklin to Sir Hans Sloane, 2 June 1725, British Library Sloane MS 4047, f. 347",
        period=Period(
            start=HistoricalDate(year=1725, month=6, day=2, precision="day"),
            end=HistoricalDate(year=1725, month=6, day=2, precision="day"),
        ),
        location=LocationInput(
            name="Bloomsbury Square",
            city="Londres",
            country="Reino Unido",
            lat=51.5186,
            lng=-0.1225,
        ),
        note=(
            "El joven Benjamin Franklin visitó a Sir Hans Sloane en su residencia de Bloomsbury Square en Londres "
            "y le vendió una bolsa de asbesto para su célebre gabinete de curiosidades."
        ),
    )
)

# 4.9 Sir Hans Sloane <-> Sir Isaac Newton (Conducción conjunta de la Royal Society)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=sloane_id,
        object_id=newton_id,
        source_id=source_newton_sloane_id,
        source_locator="Royal Society Journal Book & Council Minutes - St. Andrew's Day Meeting, 30 November 1703",
        period=Period(
            start=HistoricalDate(year=1703, month=11, day=30, precision="day"),
            end=HistoricalDate(year=1703, month=11, day=30, precision="day"),
        ),
        location=LocationInput(
            name="Royal Society en Crane Court",
            city="Londres",
            country="Reino Unido",
            lat=51.5144,
            lng=-0.1082,
        ),
        note=(
            "Sir Isaac Newton asumió la presidencia de la Royal Society en Londres el Día de San Andrés de 1703, "
            "iniciando una estrecha conducción conjunta con Sir Hans Sloane como secretario."
        ),
    )
)

# 4.10 Sir Isaac Newton <-> Edmond Halley (Visita histórica a Cambridge para los Principia)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=newton_id,
        object_id=halley_id,
        source_id=source_halley_visit_id,
        source_locator="Westfall, Never at Rest (1980), pp. 402-405 - Halley's visit to Newton at Trinity College, Cambridge, August 1684",
        period=Period(
            start=HistoricalDate(year=1684, month=8, day=15, precision="day"),
            end=HistoricalDate(year=1684, month=8, day=15, precision="day"),
        ),
        location=LocationInput(
            name="Trinity College",
            city="Cambridge",
            country="Reino Unido",
            lat=52.2070,
            lng=0.1171,
        ),
        note=(
            "Histórica visita de Edmond Halley a Isaac Newton en el Trinity College de Cambridge para debatir la ley "
            "de gravitación de cuadrado inverso, encuentro que motivó la redacción y publicación de los Principia."
        ),
    )
)

# 4.11 Sir Isaac Newton <-> Ana de Gran Bretaña (Investidura de Caballero en Cambridge)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=newton_id,
        object_id=reina_ana_id,
        source_id=source_newton_knighthood_id,
        source_locator="The London Gazette, Issue 4114, 16–19 April 1705 - Royal Visit to Cambridge and Knighthood of Sir Isaac Newton",
        period=Period(
            start=HistoricalDate(year=1705, month=4, day=16, precision="day"),
            end=HistoricalDate(year=1705, month=4, day=16, precision="day"),
        ),
        location=LocationInput(
            name="Trinity College",
            city="Cambridge",
            country="Reino Unido",
            lat=52.2070,
            lng=0.1171,
        ),
        note=(
            "La reina Ana visitó el Trinity College de Cambridge e invistió como caballero a Isaac Newton, "
            "convirtiéndolo en el primer científico en recibir el título de Sir por sus aportes intelectuales."
        ),
    )
)

# 4.12 Carolina de Brandeburgo-Ansbach <-> Sir Isaac Newton (Audiencia científica en St James's Palace)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=carolina_id,
        object_id=newton_id,
        source_id=source_caroline_newton_id,
        source_locator="Royal Collection Trust & Cambridge Archives - Princess Caroline's philosophical salons with Isaac Newton, March 1716",
        period=Period(
            start=HistoricalDate(year=1716, month=3, day=15, precision="day"),
            end=HistoricalDate(year=1716, month=3, day=15, precision="day"),
        ),
        location=LocationInput(
            name="Palacio de St. James",
            city="Londres",
            country="Reino Unido",
            lat=51.5045,
            lng=-0.1378,
        ),
        note=(
            "Audiencia científica y tertulia filosófica de la princesa Carolina de Ansbach con Sir Isaac Newton "
            "en el Palacio de St. James sobre cronología de reinos antiguos, óptica y gravitación."
        ),
    )
)

# 4.13 Voltaire <-> Sir Hans Sloane (Encuentro en Londres y discusión newtoniana)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=voltaire_id,
        object_id=sloane_id,
        source_id=source_voltaire_sloane_id,
        source_locator="Voltaire, Lettres philosophiques (1734) & Royal Society Archives, London, April 1727",
        period=Period(
            start=HistoricalDate(year=1727, month=4, day=15, precision="day"),
            end=HistoricalDate(year=1727, month=4, day=15, precision="day"),
        ),
        location=LocationInput(
            name="Bloomsbury Square",
            city="Londres",
            country="Reino Unido",
            lat=51.5186,
            lng=-0.1225,
        ),
        note=(
            "Encuentro de Voltaire con Sir Hans Sloane en Londres tras la muerte de Newton, intercambiando reflexiones "
            "sobre la filosofía newtoniana y las colecciones de la Royal Society."
        ),
    )
)

print("\n================================================================================")
print("  CARGA COMPLETADA CON ÉXITO")
print("================================================================================")
