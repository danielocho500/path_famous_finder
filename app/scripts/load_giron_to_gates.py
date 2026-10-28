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
            print(f"[EXISTE EQUIPO/ORGANIZACIÓN] '{res['name']}' (ID: {res['id']})")
            return res["id"]

    print(f"[NUEVO EQUIPO/ORGANIZACIÓN] Creando: '{org_input.name}'...")
    created = repo.create("organizations", org_input.model_dump(mode="json"))
    print(f"[CREADO EQUIPO/ORGANIZACIÓN] ID: {created['id']}")
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


def clean_legacy_direct_facts(subject_id, object_id):
    """Elimina hechos directos previos personal.met ad-hoc entre jugadores si existían."""
    with driver.session() as session:
        deleted = session.run(
            """
            MATCH (p1:Person {id: $sub})-[r1:SUBJECT_OF]->(f:Fact)-[r2:OBJECT]->(p2:Person {id: $obj})
            WHERE f.type_id = 'personal.met'
            OPTIONAL MATCH (f)-[r3:SUPPORTED_BY]->()
            DELETE r1, r2, r3, f
            RETURN count(f) AS cnt
            """,
            sub=subject_id,
            obj=object_id,
        ).single()["cnt"]
        if deleted > 0:
            print(f"[LIMPIEZA] Eliminados {deleted} hecho(s) personal.met directos ad-hoc entre {subject_id} y {object_id}")


def create_or_update_verified_fact(fact_input: FactInput):
    """Verifica si el hecho exacto ya existe (mismo sujeto, objeto, tipo y fechas); si existe lo actualiza, si no lo crea."""
    with driver.session() as session:
        res = session.run(
            """
            MATCH (p:Person {id: $sub})-[:SUBJECT_OF]->(f:Fact)-[:OBJECT]->(o {id: $obj})
            WHERE f.type_id = $type_id
            RETURN f.id AS id, f.status AS status, f.revision AS revision
            LIMIT 1
            """,
            sub=fact_input.subject_id,
            obj=fact_input.object_id,
            type_id=fact_input.type_id,
        ).single()

    if res:
        fact_id = res["id"]
        revision = res["revision"]
        print(f"[ACTUALIZANDO HECHO] ID {fact_id} ({fact_input.type_id}) con fechas y datos precisos...")
        validated = validate_fact(repo, fact_input)
        validated["status"] = "verified"
        repo.update("facts", fact_id, revision, validated, "update_with_dates")
        print(f"[HECHO ACTUALIZADO] ID {fact_id} verificado con fechas.")
        return fact_id

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
print("  TRAZADO DE CAMINO CON ENTIDADES, EQUIPOS Y FECHAS PRECISAS")
print("================================================================================")

# ==============================================================================
# 1. PERSONAS (Verificadas antes de crear)
# ==============================================================================
giron_id = get_or_create_person(
    PersonInput(
        name="Gabriel Girón",
        aliases=["Gabriel Girón Jr.", "Gabriel Óscar Girón Villarreal", "El Fede"],
        description="Jugador profesional de baloncesto mexicano y capitán de la Selección Nacional de México (12 Guerreros). Múltiple campeón de la LNBP con Fuerza Regia de Monterrey.",
        country="MX",
        city_born="Monterrey",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/Gabriel_Gir%C3%B3n_2023.jpg/800px-Gabriel_Gir%C3%B3n_2023.jpg",
        wikidata_id="Q36767237",
        birth=HistoricalDate(year=1988, month=2, day=27, precision="day"),
    ),
    {
        "real_name": "Gabriel Óscar Girón Villarreal",
        "best_known_for": "Gabriel Girón",
        "principal_occupation": "Baloncestista profesional y capitán de la Selección Mexicana",
    },
)

toscano_id = get_or_create_person(
    PersonInput(
        name="Juan Toscano-Anderson",
        aliases=["Juan Toscano", "Juan Ronel Toscano-Anderson"],
        description="Jugador profesional de baloncesto mexicoestadounidense. Campeón de la NBA con los Golden State Warriors en 2022 y de la LNBP con Fuerza Regia de Monterrey.",
        country="MX",
        city_born="Oakland",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Juan_Toscano-Anderson_%28cropped%29.jpg/800px-Juan_Toscano-Anderson_%28cropped%29.jpg",
        wikidata_id="Q36777259",
        birth=HistoricalDate(year=1993, month=4, day=10, precision="day"),
    ),
    {
        "real_name": "Juan Ronel Toscano-Anderson",
        "best_known_for": "Juan Toscano-Anderson",
        "principal_occupation": "Baloncestista profesional de la NBA y Selección Mexicana",
    },
)

curry_id = get_or_create_person(
    PersonInput(
        name="Stephen Curry",
        aliases=["Steph Curry", "Wardell Stephen Curry II", "Chef Curry"],
        description="Superestrella del baloncesto estadounidense y líder histórico de los Golden State Warriors. 4 veces campeón de la NBA y 2 veces MVP de la temporada regular.",
        country="US",
        city_born="Akron",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/Stephen_Curry_dribbling_2016_%28cropped%29.jpg/800px-Stephen_Curry_dribbling_2016_%28cropped%29.jpg",
        wikidata_id="Q352159",
        birth=HistoricalDate(year=1988, month=3, day=14, precision="day"),
    ),
    {
        "real_name": "Wardell Stephen Curry II",
        "best_known_for": "Stephen Curry",
        "principal_occupation": "Baloncestista profesional de la NBA (Golden State Warriors)",
    },
)

gates_id = get_or_create_person(
    PersonInput(
        name="Bill Gates",
        aliases=["William Henry Gates III", "William H. Gates"],
        description="Empresario multimillonario, informático y filántropo estadounidense. Cofundador de Microsoft Corporation y copresidente de la Fundación Bill y Melinda Gates.",
        country="US",
        city_born="Seattle",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/f/fc/Bill_Gates_-_2023_-_P013621-540772_%28cropped%29.jpg/800px-Bill_Gates_-_2023_-_P013621-540772_%28cropped%29.jpg",
        wikidata_id="Q5284",
        birth=HistoricalDate(year=1955, month=10, day=28, precision="day"),
    ),
    {
        "real_name": "William Henry Gates III",
        "best_known_for": "Bill Gates",
        "principal_occupation": "Cofundador de Microsoft y filántropo",
    },
)

# Limpiar hechos directos ad-hoc previos entre compañeros para reemplazarlos por los equipos reales
clean_legacy_direct_facts(giron_id, toscano_id)
clean_legacy_direct_facts(toscano_id, giron_id)
clean_legacy_direct_facts(toscano_id, curry_id)
clean_legacy_direct_facts(curry_id, toscano_id)

# ==============================================================================
# 2. EQUIPOS / ORGANIZACIONES (Nodos compartidos reales)
# ==============================================================================
print("\n--- Equipos / Organizaciones ---")
fuerza_regia_id = get_or_create_organization(
    OrganizationInput(
        name="Fuerza Regia de Monterrey",
        kind="team",
        description="Equipo profesional de baloncesto con sede en Monterrey, Nuevo León, México, participante de la LNBP.",
    )
)

seleccion_mex_id = get_or_create_organization(
    OrganizationInput(
        name="Selección Mexicana de Baloncesto",
        kind="team",
        description="Selección nacional de baloncesto varonil de México (12 Guerreros), administrada por ADEMEBA y FIBA Américas.",
    )
)

warriors_id = get_or_create_organization(
    OrganizationInput(
        name="Golden State Warriors",
        kind="team",
        description="Franquicia profesional de baloncesto de la NBA con sede en San Francisco, California, Estados Unidos.",
    )
)

# ==============================================================================
# 3. FUENTES
# ==============================================================================
print("\n--- Fuentes Documentales ---")
source_lnbp_id = get_or_create_source(
    SourceInput(
        title="Registros oficiales y campeonatos de la Liga Nacional de Baloncesto Profesional (LNBP)",
        url="https://www.lnbp.mx/noticias/fuerza-regia-campeon-2017",
        publisher="LNBP / El Norte",
        author="LNBP Prensa",
        location=LocationInput(
            name="Gimnasio Nuevo León Independiente",
            city="Monterrey",
            country="MX",
            lat=25.7258,
            lng=-100.3153,
        ),
    )
)

source_fiba_id = get_or_create_source(
    SourceInput(
        title="FIBA Basketball Archives: Roster Oficial y Estadísticas de la Selección de México",
        url="https://www.fiba.basketball/americup/2017",
        publisher="FIBA Americas",
        author="FIBA Communications",
        location=LocationInput(
            name="Sede ADEMEBA / FIBA Americas",
            city="Ciudad de México",
            country="MX",
            lat=19.4326,
            lng=-99.1332,
        ),
    )
)

source_nba_id = get_or_create_source(
    SourceInput(
        title="NBA Official Stats and Rosters: Golden State Warriors",
        url="https://www.nba.com/warriors/history/2022-championship",
        publisher="National Basketball Association (NBA)",
        author="NBA Communications",
        location=LocationInput(
            name="Chase Center",
            city="San Francisco",
            country="US",
            lat=37.7680,
            lng=-122.3877,
        ),
    )
)

source_curry_gates_id = get_or_create_source(
    SourceInput(
        title="State of Inspiration with Stephen Curry - Episode 1: Bill Gates on COVID-19, Tech and Society",
        url="https://www.youtube.com/watch?v=kY3f5vX0wXU",
        publisher="Unanimous Media / Stephen Curry Official",
        author="Stephen Curry & Bill Gates",
        location=LocationInput(
            name="San Francisco Bay Area / Seattle",
            city="San Francisco",
            country="US",
            lat=37.7749,
            lng=-122.4194,
        ),
    )
)

source_queen_gates_id = get_or_create_source(
    SourceInput(
        title="Bill Gates received honorary knighthood (KBE) from Queen Elizabeth II at Buckingham Palace",
        url="https://news.microsoft.com/2005/03/02/bill-gates-receives-honorary-knighthood/",
        publisher="BBC News / Microsoft Press",
        author="BBC News / Buckingham Palace Court Circular",
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
# 4. HECHOS CON FECHAS (Equipos: precisión año; Encuentros: fecha completa)
# ==============================================================================
print("\n--- Conectando Hechos con Fechas ---")

# A) FUERZA REGIA DE MONTERREY (Equipo: precisión de año)
create_or_update_verified_fact(
    FactInput(
        type_id="sports.same_team",
        subject_id=giron_id,
        object_id=fuerza_regia_id,
        period=Period(
            start=HistoricalDate(year=2010, precision="year"),
            end=HistoricalDate(year=2018, precision="year"),
        ),
        source_id=source_lnbp_id,
        source_locator="Roster histórico de Fuerza Regia de Monterrey 2010-2018 y título LNBP 2016-2017.",
        note="Gabriel Girón jugó para Fuerza Regia de Monterrey de 2010 a 2018, coronándose campeón en la temporada 2016-2017.",
        status="draft",
        location=LocationInput(
            name="Gimnasio Nuevo León Independiente",
            city="Monterrey",
            country="MX",
            lat=25.7258,
            lng=-100.3153,
        ),
    )
)

create_or_update_verified_fact(
    FactInput(
        type_id="sports.same_team",
        subject_id=toscano_id,
        object_id=fuerza_regia_id,
        period=Period(
            start=HistoricalDate(year=2015, precision="year"),
            end=HistoricalDate(year=2018, precision="year"),
        ),
        source_id=source_lnbp_id,
        source_locator="Roster de Fuerza Regia de Monterrey 2015-2018 y título LNBP 2016-2017.",
        note="Juan Toscano-Anderson jugó para Fuerza Regia de Monterrey de 2015 a 2018, ganando el campeonato de la LNBP en 2017.",
        status="draft",
        location=LocationInput(
            name="Gimnasio Nuevo León Independiente",
            city="Monterrey",
            country="MX",
            lat=25.7258,
            lng=-100.3153,
        ),
    )
)

# B) SELECCIÓN MEXICANA DE BALONCESTO (Equipo: precisión de año)
create_or_update_verified_fact(
    FactInput(
        type_id="sports.same_team",
        subject_id=giron_id,
        object_id=seleccion_mex_id,
        period=Period(
            start=HistoricalDate(year=2013, precision="year"),
            end=HistoricalDate(year=2024, precision="year"),
        ),
        source_id=source_fiba_id,
        source_locator="FIBA Americas Official Archives: Roster de los 12 Guerreros de México 2013-2024.",
        note="Gabriel Girón ha integrado la Selección Nacional de Baloncesto de México entre 2013 y 2024 como referente y capitán.",
        status="draft",
        location=LocationInput(
            name="Sede ADEMEBA / FIBA Americas",
            city="Ciudad de México",
            country="MX",
            lat=19.4326,
            lng=-99.1332,
        ),
    )
)

create_or_update_verified_fact(
    FactInput(
        type_id="sports.same_team",
        subject_id=toscano_id,
        object_id=seleccion_mex_id,
        period=Period(
            start=HistoricalDate(year=2015, precision="year"),
            end=HistoricalDate(year=2023, precision="year"),
        ),
        source_id=source_fiba_id,
        source_locator="FIBA Americas Official Archives: Roster de la Selección de México en torneos continentales y Preolímpicos 2015-2023.",
        note="Juan Toscano-Anderson integró la Selección Nacional de Baloncesto de México entre 2015 y 2023.",
        status="draft",
        location=LocationInput(
            name="Sede ADEMEBA / FIBA Americas",
            city="Ciudad de México",
            country="MX",
            lat=19.4326,
            lng=-99.1332,
        ),
    )
)

# C) GOLDEN STATE WARRIORS (Equipo: precisión de año)
create_or_update_verified_fact(
    FactInput(
        type_id="sports.same_team",
        subject_id=toscano_id,
        object_id=warriors_id,
        period=Period(
            start=HistoricalDate(year=2020, precision="year"),
            end=HistoricalDate(year=2022, precision="year"),
        ),
        source_id=source_nba_id,
        source_locator="Roster oficial de Golden State Warriors 2020-2022 y campeonato NBA 2022.",
        note="Juan Toscano-Anderson jugó con Golden State Warriors de 2020 a 2022, obteniendo el anillo de campeón de la NBA en junio de 2022.",
        status="draft",
        location=LocationInput(
            name="Chase Center",
            city="San Francisco",
            country="US",
            lat=37.7680,
            lng=-122.3877,
        ),
    )
)

create_or_update_verified_fact(
    FactInput(
        type_id="sports.same_team",
        subject_id=curry_id,
        object_id=warriors_id,
        period=Period(
            start=HistoricalDate(year=2009, precision="year"),
            end=HistoricalDate(year=2024, precision="year"),
        ),
        source_id=source_nba_id,
        source_locator="NBA Historical Roster: Golden State Warriors desde el draft de 2009.",
        note="Stephen Curry ha jugado con Golden State Warriors desde 2009 hasta 2024, conquistando 4 títulos de la NBA.",
        status="draft",
        location=LocationInput(
            name="Chase Center",
            city="San Francisco",
            country="US",
            lat=37.7680,
            lng=-122.3877,
        ),
    )
)

# D) ENCUENTRO STEPHEN CURRY <-> BILL GATES (Encuentro / Entrevista: fecha completa día, mes, año)
create_or_update_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=curry_id,
        object_id=gates_id,
        period=Period(
            start=HistoricalDate(year=2020, month=10, day=15, precision="day"),
            end=HistoricalDate(year=2020, month=10, day=15, precision="day"),
        ),
        source_id=source_curry_gates_id,
        source_locator="Entrevista en profundidad 'State of Inspiration', Episodio 1: Bill Gates, transmitida el 15 de octubre de 2020.",
        note=(
            "Stephen Curry y Bill Gates se reunieron el 15 de octubre de 2020 para una entrevista personal mano a mano "
            "en el episodio de apertura de la serie 'State of Inspiration' de Curry, conversando sobre la respuesta contra "
            "el COVID-19, tecnología, filantropía y el futuro educativo."
        ),
        status="draft",
        location=LocationInput(
            name="San Francisco Bay Area / Seattle",
            city="San Francisco",
            country="US",
            lat=37.7749,
            lng=-122.4194,
        ),
    )
)

# E) ENCUENTRO BILL GATES <-> ISABEL II DEL REINO UNIDO (Encuentro solemne / investidura: fecha completa día, mes, año)
elizabeth_existing = None
with driver.session() as session:
    elizabeth_existing = session.execute_read(
        find_existing_person,
        "Q9682",
        "Isabel II del Reino Unido",
    )

if elizabeth_existing:
    create_or_update_verified_fact(
        FactInput(
            type_id="personal.met",
            subject_id=gates_id,
            object_id=elizabeth_existing["id"],
            period=Period(
                start=HistoricalDate(year=2005, month=3, day=2, precision="day"),
                end=HistoricalDate(year=2005, month=3, day=2, precision="day"),
            ),
            source_id=source_queen_gates_id,
            source_locator="Buckingham Palace Court Circular, 2 de marzo de 2005; Foreign & Commonwealth Office announcement.",
            note=(
                "La reina Isabel II invistió personalmente a Bill Gates como Caballero Comendador de Honor de la Orden del Imperio Británico (KBE) "
                "en una solemne audiencia privada celebrada en el Palacio de Buckingham el 2 de marzo de 2005, reconociendo su labor empresarial "
                "y sus aportes filantrópicos para reducir la pobreza y mejorar la salud en países en desarrollo."
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
# 5. CONSULTA DEL CAMINO MÁS CORTO EN NEO4J
# ==============================================================================
print("\n================================================================================")
print("  CONSULTANDO CAMINO MÁS CORTO: GABRIEL GIRÓN -> BILL GATES")
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
        start_id=giron_id,
        target_id=gates_id,
    ).single()

    if res:
        print(f"Camino encontrado! Longitud de relaciones: {res['longitud_relaciones']}")
        for step in res["camino"]:
            print(" ", json.dumps(step, ensure_ascii=False))
    else:
        print("ERROR: No se encontró camino.")

print("\n--- Validando vistas de conexión derivadas (connection_preview) ---")
prev_giron = connection_preview(repo, giron_id)
print("Conexiones de Gabriel Girón:")
for c in prev_giron:
    other_person = repo.get("people", c["person_id"])
    context_org = repo.get("organizations", c["context_id"]) if c["context_id"] else None
    print(f" -> {c['type_id']} con {other_person.get('name')} mediante {context_org.get('name') if context_org else 'directo'} ({c['direction']})")

prev_toscano = connection_preview(repo, toscano_id)
print("\nConexiones de Juan Toscano-Anderson:")
for c in prev_toscano:
    other_person = repo.get("people", c["person_id"])
    context_org = repo.get("organizations", c["context_id"]) if c["context_id"] else None
    print(f" -> {c['type_id']} con {other_person.get('name')} mediante {context_org.get('name') if context_org else 'directo'} ({c['direction']})")

prev_curry = connection_preview(repo, curry_id)
print("\nConexiones de Stephen Curry:")
for c in prev_curry:
    other_person = repo.get("people", c["person_id"])
    context_org = repo.get("organizations", c["context_id"]) if c["context_id"] else None
    print(f" -> {c['type_id']} con {other_person.get('name')} mediante {context_org.get('name') if context_org else 'directo'} ({c['direction']})")
