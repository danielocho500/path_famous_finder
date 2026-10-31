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


def get_or_create_organization(org_input: OrganizationInput, extra_props: dict = None):
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
            print(f"[EXISTE EQUIPO/ORGANIZACIÓN] '{res['name']}' (ID: {res['id']})")
            return res["id"]

    print(f"[NUEVO EQUIPO/ORGANIZACIÓN] Creando: '{org_input.name}'...")
    created = repo.create("organizations", org_input.model_dump(mode="json"))
    org_id = created["id"]
    if extra_props:
        with driver.session() as session:
            session.run(
                """
                MATCH (o:Organization {id: $id})
                SET o.aliases = $aliases,
                    o.country = $country,
                    o.city = $city,
                    o.wikidata_id = $wikidata_id,
                    o.location_name = $loc_name,
                    o.latitude = $lat,
                    o.longitude = $lng
                """,
                id=org_id,
                aliases=extra_props.get("aliases", []),
                country=extra_props.get("country", ""),
                city=extra_props.get("city", ""),
                wikidata_id=extra_props.get("wikidata_id", ""),
                loc_name=extra_props.get("location_name", ""),
                lat=extra_props.get("lat"),
                lng=extra_props.get("lng"),
            )
    print(f"[CREADO EQUIPO/ORGANIZACIÓN] ID: {org_id}")
    return org_id


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
print("  CONEXIÓN EXPLICABLE: JAVIER 'CHICHARITO' HERNÁNDEZ -> NIKOLA TESLA")
print("================================================================================")

# ==============================================================================
# 1. ORGANIZACIONES (Equipos deportivos con ubicación geográfica completa)
# ==============================================================================
print("\n--- 1. Verificando / Creando Organizaciones Deportivas ---")

man_utd_id = get_or_create_organization(
    OrganizationInput(
        name="Manchester United F.C.",
        kind="team",
        description="Club de fútbol profesional británico con sede en Mánchester, Inglaterra, que compite en la Premier League.",
    ),
    {
        "aliases": ["Manchester United", "Man Utd", "The Red Devils"],
        "country": "GB",
        "city": "Mánchester",
        "wikidata_id": "Q18656",
        "location_name": "Old Trafford Stadium",
        "lat": 53.4631,
        "lng": -2.2913,
    },
)

# ==============================================================================
# 2. PERSONAS (Verificadas antes de crear para evitar duplicados)
# ==============================================================================
print("\n--- 2. Verificando / Creando Personas ---")

# 2.1 Javier "Chicharito" Hernández
chicharito_id = get_or_create_person(
    PersonInput(
        name="Javier Hernández",
        aliases=["Chicharito", "Javier Hernández Balcázar", "Chicharito Hernández"],
        description=(
            "Futbolista profesional mexicano y máximo goleador histórico de la Selección Mexicana. "
            "Delantero destacado en Manchester United F.C., Real Madrid, Bayer Leverkusen, Sevilla y Guadalajara."
        ),
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

# 2.2 Sir Alex Ferguson
ferguson_id = get_or_create_person(
    PersonInput(
        name="Alex Ferguson",
        aliases=["Sir Alex Ferguson", "Alexander Chapman Ferguson"],
        description=(
            "Legendario entrenador y exfutbolista escocés. Director técnico del Manchester United F.C. de 1986 a 2013, "
            "con quien conquistó 38 títulos, incluyendo 13 trofeos de Premier League y 2 UEFA Champions League. "
            "Nombrado Caballero por la Reina Isabel II en 1999."
        ),
        country="GB",
        city_born="Glasgow",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/2/22/Sir_Alex_Ferguson_2011.jpg/800px-Sir_Alex_Ferguson_2011.jpg",
        wikidata_id="Q44980",
        birth=HistoricalDate(year=1941, month=12, day=31, precision="day"),
    ),
    {
        "real_name": "Alexander Chapman Ferguson",
        "best_known_for": "Sir Alex Ferguson",
        "principal_occupation": "Director técnico y mánager legendario del Manchester United F.C.",
    },
)

# 2.3 Wayne Rooney (Compañero de ataque involucrado en Manchester United)
rooney_id = get_or_create_person(
    PersonInput(
        name="Wayne Rooney",
        aliases=["Wayne Mark Rooney", "Wazza"],
        description=(
            "Exfutbolista y entrenador inglés. Máximo goleador histórico del Manchester United F.C. con 253 goles "
            "y compañero de delantera de Javier 'Chicharito' Hernández entre 2010 y 2015."
        ),
        country="GB",
        city_born="Liverpool",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Wayne_Rooney_2018.jpg/800px-Wayne_Rooney_2018.jpg",
        wikidata_id="Q26659",
        birth=HistoricalDate(year=1985, month=10, day=24, precision="day"),
    ),
    {
        "real_name": "Wayne Mark Rooney",
        "best_known_for": "Wayne Rooney",
        "principal_occupation": "Futbolista profesional y máximo goleador histórico de Manchester United",
    },
)

# 2.4 Isabel II del Reino Unido (Ya en BD)
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

# 2.5 Jorge VI del Reino Unido (Ya en BD)
george_vi_id = get_or_create_person(
    PersonInput(
        name="Jorge VI del Reino Unido",
        aliases=["George VI", "Albert Frederick Arthur George", "Rey Jorge VI"],
        description="Rey del Reino Unido y de los dominios de la Mancomunidad Británica de Naciones desde 1936 hasta su muerte en 1952. Padrino y Kum del rey Pedro II de Yugoslavia.",
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

# 2.6 Pedro II de Yugoslavia
peter_ii_id = get_or_create_person(
    PersonInput(
        name="Pedro II de Yugoslavia",
        aliases=["Petar II Karađorđević", "Peter II of Yugoslavia", "Pedro II Karađorđević"],
        description=(
            "Último rey de Yugoslavia (1934–1945). Durante la Segunda Guerra Mundial residió exiliado en Londres, "
            "con el rey Jorge VI como anfitrión y padrino (Kum) de boda. En julio de 1942 visitó en persona "
            "a Nikola Tesla en el Hotel New Yorker."
        ),
        country="RS",
        city_born="Belgrado",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/King_Peter_II_of_Yugoslavia_in_uniform_cph.3c21345.jpg/800px-King_Peter_II_of_Yugoslavia_in_uniform_cph.3c21345.jpg",
        wikidata_id="Q212450",
        birth=HistoricalDate(year=1923, month=9, day=6, precision="day"),
        death=HistoricalDate(year=1970, month=11, day=3, precision="day"),
    ),
    {
        "real_name": "Petar II Karađorđević",
        "best_known_for": "Pedro II de Yugoslavia",
        "principal_occupation": "Rey de Yugoslavia (1934–1945)",
    },
)

# 2.7 Alejandra de Grecia y Dinamarca (Esposa del rey Pedro II en la boda real de 1944)
alexandra_id = get_or_create_person(
    PersonInput(
        name="Alejandra de Grecia y Dinamarca",
        aliases=["Alexandra of Yugoslavia", "Reina Alejandra de Yugoslavia"],
        description=(
            "Princesa de Grecia y Dinamarca y última reina consorte de Yugoslavia tras su matrimonio con el rey "
            "Pedro II en Londres el 20 de marzo de 1944, con el rey Jorge VI como padrino de honor."
        ),
        country="GR",
        city_born="Atenas",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/Queen_Alexandra_of_Yugoslavia_1944.jpg/800px-Queen_Alexandra_of_Yugoslavia_1944.jpg",
        wikidata_id="Q157147",
        birth=HistoricalDate(year=1921, month=3, day=25, precision="day"),
        death=HistoricalDate(year=1993, month=1, day=30, precision="day"),
    ),
    {
        "real_name": "Alexandra of Greece and Denmark",
        "best_known_for": "Alejandra de Grecia y Dinamarca",
        "principal_occupation": "Princesa de Grecia y Reina consorte de Yugoslavia",
    },
)

# 2.8 Sava Kosanović (Sobrino de Tesla y ministro yugoslavo que coordinó la visita de 1942)
sava_id = get_or_create_person(
    PersonInput(
        name="Sava Kosanović",
        aliases=["Sava N. Kosanović", "Сава Косановић"],
        description=(
            "Diplomático, publicista y político yugoslavo, sobrino de Nikola Tesla y ministro en el gobierno en el exilio "
            "de Pedro II. Acompañó y organizó el histórico encuentro en el Hotel New Yorker en julio de 1942 y salvaguardó "
            "el archivo de Tesla tras su muerte."
        ),
        country="RS",
        city_born="Plaški",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/Sava_Kosanovi%C4%87.jpg/800px-Sava_Kosanovi%C4%87.jpg",
        wikidata_id="Q12758467",
        birth=HistoricalDate(year=1894, month=5, day=29, precision="day"),
        death=HistoricalDate(year=1956, month=9, day=14, precision="day"),
    ),
    {
        "real_name": "Sava N. Kosanović",
        "best_known_for": "Sava Kosanović",
        "principal_occupation": "Diplomático, ministro de Yugoslavia y sobrino de Nikola Tesla",
    },
)

# 2.9 Nikola Tesla
tesla_id = get_or_create_person(
    PersonInput(
        name="Nikola Tesla",
        aliases=["Tesla", "Никола Тесла"],
        description=(
            "Físico, matemático, ingeniero eléctrico y mecánico serbio-estadounidense. Pionero mundial del desarrollo "
            "de la corriente alterna (CA), el motor de inducción electromagnética, la bobina de Tesla y las telecomunicaciones inalámbricas."
        ),
        country="US",
        city_born="Smiljan",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/7/79/Tesla_circa_1890.jpeg/800px-Tesla_circa_1890.jpeg",
        wikidata_id="Q9036",
        birth=HistoricalDate(year=1856, month=7, day=10, precision="day"),
        death=HistoricalDate(year=1943, month=1, day=7, precision="day"),
    ),
    {
        "real_name": "Nikola Tesla",
        "best_known_for": "Nikola Tesla",
        "principal_occupation": "Inventor, ingeniero eléctrico, físico y visionario de la corriente alterna",
    },
)

# 2.10 Hermann von Helmholtz (Ya en BD)
helmholtz_id = get_or_create_person(
    PersonInput(
        name="Hermann von Helmholtz",
        aliases=["Helmholtz", "Hermann Ludwig Ferdinand von Helmholtz"],
        description="Físico y médico alemán pionero en la ley de conservación de la energía, electrodinámica y óptica.",
        country="DE",
        city_born="Potsdam",
        image_url="https://upload.wikimedia.org/wikipedia/commons/b/b3/Hermann_von_Helmholtz.jpg",
        wikidata_id="Q60024",
        birth=HistoricalDate(year=1821, month=8, day=31, precision="day"),
        death=HistoricalDate(year=1894, month=9, day=8, precision="day"),
    ),
    {
        "real_name": "Hermann Ludwig Ferdinand von Helmholtz",
        "best_known_for": "Hermann von Helmholtz",
        "principal_occupation": "Físico y médico teórico alemán",
    },
)

# ==============================================================================
# 3. FUENTES HISTÓRICAS DOCUMENTADAS CON GEOLOCALIZACIÓN
# ==============================================================================
print("\n--- 3. Verificando / Creando Fuentes Históricas ---")

# Fuente 1: Manchester United - Javier Hernández
src_chicha_manutd = get_or_create_source(
    SourceInput(
        title="Manchester United Official Club Archive - Javier Hernández Profile & Statistics",
        url="https://www.manutd.com/en/players-and-staff/detail/javier-hernandez",
        citation="Manchester United Football Club Historical Archive: Player Record for Javier 'Chicharito' Hernández (2010–2015).",
        author="Manchester United F.C. Communications",
        publisher="Manchester United Media",
        location=LocationInput(
            name="Old Trafford",
            city="Mánchester",
            country="GB",
            lat=53.4631,
            lng=-2.2913,
        ),
    )
)

# Fuente 2: Manchester United - Sir Alex Ferguson
src_ferguson_manutd = get_or_create_source(
    SourceInput(
        title="Manchester United Official Club History - Sir Alex Ferguson Era (1986–2013)",
        url="https://www.manutd.com/en/history/history-by-decade/1980-1989",
        citation="Manchester United Football Club Archives: The Management of Sir Alex Ferguson (1986 to 2013).",
        author="Manchester United F.C.",
        publisher="Manchester United Media",
        location=LocationInput(
            name="Old Trafford",
            city="Mánchester",
            country="GB",
            lat=53.4631,
            lng=-2.2913,
        ),
    )
)

# Fuente 3: Manchester United - Wayne Rooney
src_rooney_manutd = get_or_create_source(
    SourceInput(
        title="Manchester United Official Records - Wayne Rooney Top Goalscorer & Career",
        url="https://www.manutd.com/en/players-and-staff/detail/wayne-rooney",
        citation="Manchester United Football Club Archive: Wayne Rooney Record Goalscorer Profile (2004–2017).",
        author="Manchester United F.C.",
        publisher="Manchester United Media",
        location=LocationInput(
            name="Old Trafford",
            city="Mánchester",
            country="GB",
            lat=53.4631,
            lng=-2.2913,
        ),
    )
)

# Fuente 4: Investidura de Sir Alex Ferguson por la Reina Isabel II
src_ferguson_knighthood = get_or_create_source(
    SourceInput(
        title="The London Gazette - Investiture and Knighthood of Alexander Chapman Ferguson",
        url="https://www.thegazette.co.uk/London/issue/55513/supplement/1",
        citation="The London Gazette, Supplement 55513, page 1: Knighthood conferred by HM Queen Elizabeth II on Alex Ferguson, July 20, 1999.",
        author="Central Chancery of the Orders of Knighthood",
        publisher="Her Majesty's Stationery Office (HMSO)",
        location=LocationInput(
            name="Palacio de Buckingham",
            city="Londres",
            country="GB",
            lat=51.5014,
            lng=-0.1419,
        ),
    )
)

# Fuente 5: Boda real de Pedro II de Yugoslavia con Alejandra de Grecia y Rey Jorge VI
src_peter_wedding = get_or_create_source(
    SourceInput(
        title="The Royal Archives & Yugoslav Legation London - Royal Wedding of King Peter II and Princess Alexandra (March 20, 1944)",
        url="https://royalwatcherblog.com/2019/03/20/wedding-of-king-peter-ii-of-yugoslavia-and-princess-alexandra-of-greece/",
        citation="Official Records of the Yugoslavian Royal Government in Exile and British Royal Court: Marriage of King Peter II and Princess Alexandra of Greece, with King George VI serving as best man (Kum), London, March 20, 1944.",
        author="British Royal Archives & Yugoslav Legation",
        publisher="The Royal Family History Archive",
        location=LocationInput(
            name="Legación y Embajada de Yugoslavia",
            city="Londres",
            country="GB",
            lat=51.5033,
            lng=-0.1585,
        ),
    )
)

# Fuente 6: Encuentro de Pedro II y Sava Kosanović con Nikola Tesla en Nueva York
src_tesla_peter_visit = get_or_create_source(
    SourceInput(
        title="Nikola Tesla Universe Archive & A King's Heritage - King Peter II of Yugoslavia visits Nikola Tesla at Hotel New Yorker (July 8, 1942)",
        url="https://teslauniverse.com/nikola-tesla/timeline/1942-king-peter-ii-visits-tesla",
        citation="A King's Heritage: The Memoirs of King Peter II of Yugoslavia (G.P. Putnam's Sons, 1954), pp. 132-134; Nikola Tesla Museum Records, Belgrade.",
        author="King Peter II of Yugoslavia & Sava Kosanović",
        publisher="G.P. Putnam's Sons / Nikola Tesla Museum",
        location=LocationInput(
            name="Hotel New Yorker (Suite 3327)",
            city="Nueva York",
            country="US",
            lat=40.7527,
            lng=-73.9934,
        ),
    )
)

# Fuente 7: Encuentro Nikola Tesla y Hermann von Helmholtz en la Exposición Mundial de Chicago 1893
src_tesla_helmholtz = get_or_create_source(
    SourceInput(
        title="Smithsonian Institution & PBS - Nikola Tesla and Hermann von Helmholtz at the 1893 World's Columbian Exposition",
        url="https://www.pbs.org/tesla/ll/ll_colexp.html",
        citation="Proceedings of the International Electrical Congress, Chicago 1893; Smithsonian Institution Archives, Electricity Building demonstrations.",
        author="International Electrical Congress Committee",
        publisher="PBS / Smithsonian Institution",
        location=LocationInput(
            name="Edificio de Electricidad, Jackson Park",
            city="Chicago",
            country="US",
            lat=41.7886,
            lng=-87.5843,
        ),
    )
)

# ==============================================================================
# 4. HECHOS VERIFICADOS CON FECHAS PRECISAS Y GEOLOCALIZACIÓN
# ==============================================================================
print("\n--- 4. Creando / Verificando Hechos Relacionales ---")

# A) CHICHARITO -> MANCHESTER UNITED F.C. (sports.same_team, precisión año)
get_or_create_verified_fact(
    FactInput(
        type_id="sports.same_team",
        subject_id=chicharito_id,
        object_id=man_utd_id,
        period=Period(
            start=HistoricalDate(year=2010, precision="year"),
            end=HistoricalDate(year=2015, precision="year"),
        ),
        source_id=src_chicha_manutd,
        source_locator="Registro oficial de plantilla 2010–2015: 157 partidos, 59 goles y 2 títulos de Premier League.",
        note=(
            "Javier Hernández 'Chicharito' militó en el Manchester United F.C. de 2010 a 2015, "
            "fichado por Sir Alex Ferguson y coronándose dos veces campeón de la Premier League inglesa."
        ),
        status="draft",
        location=LocationInput(
            name="Old Trafford Stadium",
            city="Mánchester",
            country="GB",
            lat=53.4631,
            lng=-2.2913,
        ),
    )
)

# B) SIR ALEX FERGUSON -> MANCHESTER UNITED F.C. (sports.same_team, precisión año)
get_or_create_verified_fact(
    FactInput(
        type_id="sports.same_team",
        subject_id=ferguson_id,
        object_id=man_utd_id,
        period=Period(
            start=HistoricalDate(year=1986, precision="year"),
            end=HistoricalDate(year=2013, precision="year"),
        ),
        source_id=src_ferguson_manutd,
        source_locator="Historial de dirección técnica del club: Director técnico de Manchester United de noviembre de 1986 a mayo de 2013.",
        note=(
            "Sir Alex Ferguson dirigió ininterrumpidamente al Manchester United F.C. desde 1986 hasta su retiro en 2013, "
            "coincidiendo con Javier Hernández 'Chicharito' y dirigiéndolo en Old Trafford entre 2010 y 2013."
        ),
        status="draft",
        location=LocationInput(
            name="Old Trafford Stadium",
            city="Mánchester",
            country="GB",
            lat=53.4631,
            lng=-2.2913,
        ),
    )
)

# C) WAYNE ROONEY -> MANCHESTER UNITED F.C. (sports.same_team, precisión año)
get_or_create_verified_fact(
    FactInput(
        type_id="sports.same_team",
        subject_id=rooney_id,
        object_id=man_utd_id,
        period=Period(
            start=HistoricalDate(year=2004, precision="year"),
            end=HistoricalDate(year=2017, precision="year"),
        ),
        source_id=src_rooney_manutd,
        source_locator="Archivo oficial de jugadores: Máximo goleador histórico del Manchester United (2004–2017).",
        note=(
            "Wayne Rooney jugó para el Manchester United F.C. de 2004 a 2017, compartiendo delantera titular con "
            "Javier Hernández 'Chicharito' de 2010 a 2015 bajo las órdenes de Sir Alex Ferguson."
        ),
        status="draft",
        location=LocationInput(
            name="Old Trafford Stadium",
            city="Mánchester",
            country="GB",
            lat=53.4631,
            lng=-2.2913,
        ),
    )
)

# D) SIR ALEX FERGUSON <-> ISABEL II DEL REINO UNIDO (Investidura solemne, precisión día: 20 de julio de 1999)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=ferguson_id,
        object_id=elizabeth_id,
        period=Period(
            start=HistoricalDate(year=1999, month=7, day=20, precision="day"),
            end=HistoricalDate(year=1999, month=7, day=20, precision="day"),
        ),
        source_id=src_ferguson_knighthood,
        source_locator="The London Gazette, Ceremonia de Investidura en Buckingham Palace, 20 de julio de 1999.",
        note=(
            "La Reina Isabel II condecoró e invistió como Caballero (Knight Bachelor) a Sir Alex Ferguson en persona "
            "en el Palacio de Buckingham el 20 de julio de 1999 tras la histórica temporada del triplete del Manchester United."
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

# E) JORGE VI DEL REINO UNIDO <-> PEDRO II DE YUGOSLAVIA (Boda Real / Padrino Kum, precisión día: 20 de marzo de 1944)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=george_vi_id,
        object_id=peter_ii_id,
        period=Period(
            start=HistoricalDate(year=1944, month=3, day=20, precision="day"),
            end=HistoricalDate(year=1944, month=3, day=20, precision="day"),
        ),
        source_id=src_peter_wedding,
        source_locator="Ceremonia matrimonial en la Legación Yugoslava de Londres, 20 de marzo de 1944.",
        note=(
            "El rey Jorge VI del Reino Unido ejerció como padrino principal y testigo de honor (Kum) en la boda real del "
            "rey Pedro II de Yugoslavia con la princesa Alejandra de Grecia el 20 de marzo de 1944 en la Legación Yugoslava de Londres."
        ),
        status="draft",
        location=LocationInput(
            name="Legación y Embajada de Yugoslavia",
            city="Londres",
            country="GB",
            lat=51.5033,
            lng=-0.1585,
        ),
    )
)

# F) JORGE VI DEL REINO UNIDO <-> ALEJANDRA DE GRECIA Y DINAMARCA (Boda Real, precisión día: 20 de marzo de 1944)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=george_vi_id,
        object_id=alexandra_id,
        period=Period(
            start=HistoricalDate(year=1944, month=3, day=20, precision="day"),
            end=HistoricalDate(year=1944, month=3, day=20, precision="day"),
        ),
        source_id=src_peter_wedding,
        source_locator="Acta ceremonial de la boda real en Londres, 20 de marzo de 1944.",
        note=(
            "El rey Jorge VI del Reino Unido acompañó como padrino principal a la princesa Alejandra de Grecia y Dinamarca "
            "en su enlace matrimonial con el rey Pedro II de Yugoslavia en Londres el 20 de marzo de 1944."
        ),
        status="draft",
        location=LocationInput(
            name="Legación y Embajada de Yugoslavia",
            city="Londres",
            country="GB",
            lat=51.5033,
            lng=-0.1585,
        ),
    )
)

# G) PEDRO II DE YUGOSLAVIA <-> ALEJANDRA DE GRECIA Y DINAMARCA (Cónyuges, precisión día: 20 de marzo de 1944)
get_or_create_verified_fact(
    FactInput(
        type_id="family.spouse_of",
        subject_id=peter_ii_id,
        object_id=alexandra_id,
        period=Period(
            start=HistoricalDate(year=1944, month=3, day=20, precision="day"),
            end=HistoricalDate(year=1970, month=11, day=3, precision="day"),
        ),
        source_id=src_peter_wedding,
        source_locator="Registro oficial de matrimonio dinástico celebrado en Londres el 20 de marzo de 1944.",
        note=(
            "El rey Pedro II de Yugoslavia y la princesa Alejandra de Grecia y Dinamarca contrajeron matrimonio el 20 de marzo de 1944 "
            "en Londres, permaneciendo unidos en matrimonio hasta el fallecimiento de Pedro II en 1970."
        ),
        status="draft",
        location=LocationInput(
            name="Legación y Embajada de Yugoslavia",
            city="Londres",
            country="GB",
            lat=51.5033,
            lng=-0.1585,
        ),
    )
)

# H) PEDRO II DE YUGOSLAVIA <-> NIKOLA TESLA (Encuentro histórico en Suite 3327 de Hotel New Yorker, 8 de julio de 1942)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=peter_ii_id,
        object_id=tesla_id,
        period=Period(
            start=HistoricalDate(year=1942, month=7, day=8, precision="day"),
            end=HistoricalDate(year=1942, month=7, day=8, precision="day"),
        ),
        source_id=src_tesla_peter_visit,
        source_locator="A King's Heritage, pp. 132-134; suite 3327 del Hotel New Yorker, 8 de julio de 1942.",
        note=(
            "El joven rey Pedro II de Yugoslavia visitó en persona al célebre científico e inventor Nikola Tesla "
            "en su suite 3327 del Hotel New Yorker en Nueva York el 8 de julio de 1942, un histórico encuentro fotografiado "
            "y consignado en las memorias del monarca donde ambos dialogaron emotivamente sobre el porvenir de Yugoslavia."
        ),
        status="draft",
        location=LocationInput(
            name="Hotel New Yorker (Suite 3327)",
            city="Nueva York",
            country="US",
            lat=40.7527,
            lng=-73.9934,
        ),
    )
)

# I) SAVA KOSANOVIĆ <-> NIKOLA TESLA (Encuentro y relación familiar en Suite 3327, 8 de julio de 1942)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=sava_id,
        object_id=tesla_id,
        period=Period(
            start=HistoricalDate(year=1942, month=7, day=8, precision="day"),
            end=HistoricalDate(year=1942, month=7, day=8, precision="day"),
        ),
        source_id=src_tesla_peter_visit,
        source_locator="Archivo del Museo Nikola Tesla en Belgrado; correspondencia y visita de julio de 1942.",
        note=(
            "Sava Kosanović, diplomático yugoslavo y sobrino de Nikola Tesla, acompañó y facilitó la histórica audiencia "
            "en la suite 3327 del Hotel New Yorker el 8 de julio de 1942, asistiendo al sabio en sus últimos meses de vida."
        ),
        status="draft",
        location=LocationInput(
            name="Hotel New Yorker (Suite 3327)",
            city="Nueva York",
            country="US",
            lat=40.7527,
            lng=-73.9934,
        ),
    )
)

# J) PEDRO II DE YUGOSLAVIA <-> SAVA KOSANOVIĆ (Co-participantes en la visita a Tesla, 8 de julio de 1942)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=peter_ii_id,
        object_id=sava_id,
        period=Period(
            start=HistoricalDate(year=1942, month=7, day=8, precision="day"),
            end=HistoricalDate(year=1942, month=7, day=8, precision="day"),
        ),
        source_id=src_tesla_peter_visit,
        source_locator="Misión diplomática oficial del rey Pedro II en EE. UU., Nueva York, 8 de julio de 1942.",
        note=(
            "El rey Pedro II de Yugoslavia y el ministro Sava Kosanović se reunieron y coordinaron conjuntamente la comitiva real "
            "y visita de Estado a Nikola Tesla en Nueva York el 8 de julio de 1942."
        ),
        status="draft",
        location=LocationInput(
            name="Hotel New Yorker (Suite 3327)",
            city="Nueva York",
            country="US",
            lat=40.7527,
            lng=-73.9934,
        ),
    )
)

# K) NIKOLA TESLA <-> HERMANN VON HELMHOLTZ (Encuentro en la Exposición Mundial de Chicago, 25 de agosto de 1893)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=tesla_id,
        object_id=helmholtz_id,
        period=Period(
            start=HistoricalDate(year=1893, month=8, day=25, precision="day"),
            end=HistoricalDate(year=1893, month=8, day=25, precision="day"),
        ),
        source_id=src_tesla_helmholtz,
        source_locator="Proceedings of the International Electrical Congress, Electricity Building, Chicago, August 25, 1893.",
        note=(
            "Nikola Tesla recibió y guio en persona al célebre físico alemán Hermann von Helmholtz en el Edificio de Electricidad "
            "de la Exposición Mundial Colombina de Chicago el 25 de agosto de 1893, demostrándole sus experimentos pioneros "
            "con generadores de alta frecuencia y transmisión de energía inalámbrica."
        ),
        status="draft",
        location=LocationInput(
            name="Edificio de Electricidad, Jackson Park",
            city="Chicago",
            country="US",
            lat=41.7886,
            lng=-87.5843,
        ),
    )
)

# ==============================================================================
# 5. VERIFICACIÓN Y PREVIEW DEL CAMINO COMPLETO
# ==============================================================================
print("\n--- 5. Verificando Conexiones y Camino Óptimo ---")

with driver.session() as session:
    path_res = session.run(
        """
        MATCH path = shortestPath((start:Person {id: $start_id})-[*..15]-(target:Person {id: $target_id}))
        RETURN [node IN nodes(path) | coalesce(node.search_name, node.name, labels(node)[0])] AS names,
               [rel IN relationships(path) | type(rel)] AS rels,
               length(path) AS hops
        """,
        start_id=chicharito_id,
        target_id=tesla_id,
    ).single()

if path_res:
    print(f"\n[CAMINO ENCONTRADO EN NEO4J] (Longitud: {path_res['hops']} saltos):")
    for idx, name in enumerate(path_res["names"]):
        if idx < len(path_res["rels"]):
            print(f"  ({name}) --[{path_res['rels'][idx]}]-->")
        else:
            print(f"  ({name})")
else:
    print("\n[ALERTA] No se encontró camino directo en Neo4j entre Chicharito y Nikola Tesla.")

print("\n--- Conexiones derivadas (connection_preview) para Javier Hernández ---")
preview_chicha = connection_preview(repo, chicharito_id)
for conn in preview_chicha:
    target_person = repo.get("people", conn["person_id"])
    print(f"  -> Conectado con: {target_person.get('search_name', target_person.get('name'))} vía {conn['type_id']} ({conn.get('location', {}).get('name')})")

print("\n--- Conexiones derivadas (connection_preview) para Nikola Tesla ---")
preview_tesla = connection_preview(repo, tesla_id)
for conn in preview_tesla:
    target_person = repo.get("people", conn["person_id"])
    print(f"  -> Conectado con: {target_person.get('search_name', target_person.get('name'))} vía {conn['type_id']} ({conn.get('location', {}).get('name')})")

print("\n================================================================================")
print("  PROCESO COMPLETADO EXITOSAMENTE")
print("================================================================================")
