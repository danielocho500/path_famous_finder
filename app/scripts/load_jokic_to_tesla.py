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
)
from modules.graph.repository import GraphRepository
from modules.graph.service import validate_event, validate_fact

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
            MATCH (p:Person)-[:SUBJECT_OF]->(f:Fact)-[:OBJECT]->(o)
            WHERE ((p.id = $sub AND o.id = $obj) OR (p.id = $obj AND o.id = $sub))
              AND f.type_id = $type_id
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
print("  CONEXIÓN EXPLICABLE: NIKOLA JOKIĆ -> NIKOLA TESLA")
print("================================================================================")

# ==============================================================================
# 1. PERSONAS (Verificadas antes de crear para evitar duplicados)
# ==============================================================================
print("\n--- 1. Verificando / Creando Personas ---")

# 1.1 Nikola Jokić
jokic_id = get_or_create_person(
    PersonInput(
        name="Nikola Jokić",
        aliases=["Nikola Jokic", "The Joker", "Никола Јокић"],
        description=(
            "Baloncestista profesional serbio, pívot estrella de los Denver Nuggets de la NBA y de la selección "
            "nacional de Serbia. Tres veces Jugador Más Valioso (MVP) de la NBA (2021, 2022, 2024), Campeón de la NBA "
            "y MVP de las Finales en 2023, y medallista olímpico."
        ),
        country="RS",
        city_born="Sombor",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Nikola_Joki%C4%87_free_throw_%28cropped%29.jpg/800px-Nikola_Joki%C4%87_free_throw_%28cropped%29.jpg",
        wikidata_id="Q17182740",
        birth=HistoricalDate(year=1995, month=2, day=19, precision="day"),
    ),
    {
        "real_name": "Nikola Jokić",
        "best_known_for": "Nikola Jokić",
        "principal_occupation": "Baloncestista profesional de la NBA",
    },
)

# 1.2 Novak Djokovic (Ícono serbio de conexión cruzada)
djokovic_id = get_or_create_person(
    PersonInput(
        name="Novak Djokovic",
        aliases=["Novak Đoković", "Nole", "Новак Ђоковић"],
        description=(
            "Tenista profesional serbio, ampliamente considerado como el mejor tenista de la historia. "
            "Poseedor del récord de 24 títulos individuales de Grand Slam, medallista de oro en los Juegos Olímpicos "
            "de París 2024 y fervoroso promotor del legado cultural y científico de Nikola Tesla."
        ),
        country="RS",
        city_born="Belgrado",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/b/b8/Novak_Djokovic_Wimbledon_2023.jpg/800px-Novak_Djokovic_Wimbledon_2023.jpg",
        wikidata_id="Q856",
        birth=HistoricalDate(year=1987, month=5, day=22, precision="day"),
    ),
    {
        "real_name": "Novak Đoković",
        "best_known_for": "Novak Djokovic",
        "principal_occupation": "Tenista profesional y campeón de Grand Slam",
    },
)

# 1.3 Stephen Curry (Preexistente en BD)
with driver.session() as session:
    res_sc = session.run("MATCH (p:Person {wikidata_id: 'Q352159'}) RETURN p.id AS id").single()
    curry_id = res_sc["id"]
    print(f"[EXISTE PERSONA] Stephen Curry (ID: {curry_id})")

# 1.4 Juan Toscano-Anderson (Preexistente en BD)
with driver.session() as session:
    res_jta = session.run("MATCH (p:Person {wikidata_id: 'Q36777259'}) RETURN p.id AS id").single()
    if not res_jta:
        res_jta = session.run("MATCH (p:Person) WHERE toLower(coalesce(p.search_name, '')) CONTAINS 'toscano' RETURN p.id AS id").single()
    toscano_id = res_jta["id"]
    print(f"[EXISTE PERSONA] Juan Toscano-Anderson (ID: {toscano_id})")

# 1.5 Nikola Tesla (Preexistente en BD)
with driver.session() as session:
    res_tesla = session.run("MATCH (p:Person {wikidata_id: 'Q9036'}) RETURN p.id AS id").single()
    tesla_id = res_tesla["id"]
    print(f"[EXISTE PERSONA] Nikola Tesla (ID: {tesla_id})")


# ==============================================================================
# 2. FUENTES DOCUMENTALES
# ==============================================================================
print("\n--- 2. Verificando / Creando Fuentes Documentales ---")

# 2.1 Fuente: NBA All-Star Game 2021 (Team LeBron: Stephen Curry y Nikola Jokić)
source_allstar_id = get_or_create_source(
    SourceInput(
        title="NBA Official Box Score: 70th NBA All-Star Game - Team LeBron vs Team Durant (2021)",
        url="https://www.nba.com/game/lbn-vs-dur-0032000001/box-score",
        citation="National Basketball Association (NBA) Official Archives, 70th All-Star Game, State Farm Arena, Atlanta, GA, March 7, 2021.",
        author="NBA Statistics and Information Group",
        publisher="National Basketball Association",
        accessed_at="2026-10-26",
        location=LocationInput(
            name="State Farm Arena",
            city="Atlanta",
            country="Estados Unidos",
            lat=33.7573,
            lng=-84.3963,
        ),
    )
)

# 2.2 Fuente: Semifinal Olímpica de Baloncesto París 2024 (USA vs. Serbia)
source_olympics_id = get_or_create_source(
    SourceInput(
        title="FIBA Official Match Report: Men's Olympic Basketball Tournament Paris 2024 - Semifinal USA vs Serbia",
        url="https://www.fiba.basketball/en/events/mens-olympic-basketball-tournament-paris-2024/games/122606-USA-SRB",
        citation="Fédération Internationale de Basketball (FIBA), Men's Olympic Basketball Tournament Paris 2024, Semifinal 2 Box Score, Bercy Arena, Paris, August 8, 2024.",
        author="FIBA Olympic Basketball Commission",
        publisher="Fédération Internationale de Basketball",
        accessed_at="2026-10-26",
        location=LocationInput(
            name="Bercy Arena",
            city="París",
            country="Francia",
            lat=48.8386,
            lng=2.3787,
        ),
    )
)

# 2.3 Fuente: NBA Playoffs 2022 Primera Ronda Game 1 (Warriors vs. Nuggets)
source_playoffs_id = get_or_create_source(
    SourceInput(
        title="NBA Official Box Score: 2022 Western Conference First Round Game 1 - Golden State Warriors vs Denver Nuggets",
        url="https://www.nba.com/game/den-vs-gsw-0042100161/box-score",
        citation="National Basketball Association (NBA) Official Archives, Western Conference First Round Game 1, Chase Center, San Francisco, CA, April 16, 2022.",
        author="NBA Official Scorer",
        publisher="National Basketball Association",
        accessed_at="2026-10-26",
        location=LocationInput(
            name="Chase Center",
            city="San Francisco",
            country="Estados Unidos",
            lat=37.7680,
            lng=-122.3877,
        ),
    )
)

# 2.4 Fuente: Encuentro entre Nikola Jokić y Novak Djokovic en Los Ángeles (2024)
source_jokic_djokovic_id = get_or_create_source(
    SourceInput(
        title="ATP Tour & NBA: Novak Djokovic and Nikola Jokic meet in Los Angeles after Nuggets win",
        url="https://www.atptour.com/en/news/djokovic-jokic-los-angeles-nba-march-2024",
        citation="ATP Tour News & NBA Entertainment, Courtside Coverage and Locker Room Meeting at Crypto.com Arena, Los Angeles, March 2, 2024.",
        author="ATP Tour & NBA Communications",
        publisher="ATP Tour Inc.",
        accessed_at="2026-10-26",
        location=LocationInput(
            name="Crypto.com Arena",
            city="Los Ángeles",
            country="Estados Unidos",
            lat=34.0430,
            lng=-118.2673,
        ),
    )
)


# ==============================================================================
# 3. EVENTOS DEPORTIVOS Y PARTIDOS
# ==============================================================================
print("\n--- 3. Verificando / Creando Eventos Deportivos Oficiales ---")

# 3.1 Evento: NBA All-Star Game 2021 (Curry y Jokić como titulares en Team LeBron)
event_allstar_id = get_or_create_event_with_facts(
    EventInput(
        name="70th NBA All-Star Game 2021",
        kind="sports.match",
        period=Period(
            start=HistoricalDate(year=2021, month=3, day=7, precision="day"),
            end=HistoricalDate(year=2021, month=3, day=7, precision="day"),
        ),
        place="State Farm Arena",
        location=LocationInput(
            name="State Farm Arena",
            city="Atlanta",
            country="Estados Unidos",
            lat=33.7573,
            lng=-84.3963,
        ),
        source_id=source_allstar_id,
        source_locator="NBA All-Star Game 2021 Official Lineup: Team LeBron Starters",
        participants=[
            EventParticipantInput(
                type_id="sports.same_side_match",
                subject_id=curry_id,
                role="player",
                side="team_lebron",
                source_id=source_allstar_id,
                source_locator="NBA All-Star Box Score: Stephen Curry (28 pts, Team LeBron)",
                period=Period(
                    start=HistoricalDate(year=2021, month=3, day=7, precision="day"),
                    end=HistoricalDate(year=2021, month=3, day=7, precision="day"),
                ),
                location=LocationInput(
                    name="State Farm Arena",
                    city="Atlanta",
                    country="Estados Unidos",
                    lat=33.7573,
                    lng=-84.3963,
                ),
                note="Stephen Curry fue titular del Team LeBron, anotando 28 puntos y conectando tiros de media cancha junto a Nikola Jokić.",
            ),
            EventParticipantInput(
                type_id="sports.same_side_match",
                subject_id=jokic_id,
                role="player",
                side="team_lebron",
                source_id=source_allstar_id,
                source_locator="NBA All-Star Box Score: Nikola Jokić (Team LeBron Starter)",
                period=Period(
                    start=HistoricalDate(year=2021, month=3, day=7, precision="day"),
                    end=HistoricalDate(year=2021, month=3, day=7, precision="day"),
                ),
                location=LocationInput(
                    name="State Farm Arena",
                    city="Atlanta",
                    country="Estados Unidos",
                    lat=33.7573,
                    lng=-84.3963,
                ),
                note="Nikola Jokić fue titular del Team LeBron en el 70.° Juego de Estrellas de la NBA, compartiendo quinteto inicial con Stephen Curry en la victoria 170-150.",
            ),
        ],
    )
)

# 3.2 Evento: Semifinal Olímpica de Baloncesto París 2024 (EE. UU. vs. Serbia)
event_olympics_id = get_or_create_event_with_facts(
    EventInput(
        name="Semifinal Olímpica de Baloncesto París 2024: Estados Unidos vs. Serbia",
        kind="sports.match",
        period=Period(
            start=HistoricalDate(year=2024, month=8, day=8, precision="day"),
            end=HistoricalDate(year=2024, month=8, day=8, precision="day"),
        ),
        place="Bercy Arena",
        location=LocationInput(
            name="Bercy Arena",
            city="París",
            country="Francia",
            lat=48.8386,
            lng=2.3787,
        ),
        source_id=source_olympics_id,
        source_locator="FIBA París 2024 - Acta Oficial Semifinal Masculina USA 95 - 91 Serbia",
        participants=[
            EventParticipantInput(
                type_id="sports.faced_in_match",
                subject_id=curry_id,
                role="player",
                side="usa",
                source_id=source_olympics_id,
                source_locator="FIBA Official Box Score: Stephen Curry (36 puntos, 9 triples)",
                period=Period(
                    start=HistoricalDate(year=2024, month=8, day=8, precision="day"),
                    end=HistoricalDate(year=2024, month=8, day=8, precision="day"),
                ),
                location=LocationInput(
                    name="Bercy Arena",
                    city="París",
                    country="Francia",
                    lat=48.8386,
                    lng=2.3787,
                ),
                note="Stephen Curry lideró la épica remontada de Estados Unidos con 36 puntos y 9 triples en la semifinal olímpica contra Serbia.",
            ),
            EventParticipantInput(
                type_id="sports.faced_in_match",
                subject_id=jokic_id,
                role="player",
                side="serbia",
                source_id=source_olympics_id,
                source_locator="FIBA Official Box Score: Nikola Jokić (17 puntos, 11 asistencias, 5 rebotes)",
                period=Period(
                    start=HistoricalDate(year=2024, month=8, day=8, precision="day"),
                    end=HistoricalDate(year=2024, month=8, day=8, precision="day"),
                ),
                location=LocationInput(
                    name="Bercy Arena",
                    city="París",
                    country="Francia",
                    lat=48.8386,
                    lng=2.3787,
                ),
                note="Nikola Jokić lideró a la selección de Serbia en una batalla épica frente a Stephen Curry y el Team USA en los Juegos Olímpicos de París 2024.",
            ),
        ],
    )
)

# 3.3 Evento: NBA Playoffs 2022 Game 1 (Warriors vs. Nuggets - Toscano, Curry y Jokić)
event_playoffs_id = get_or_create_event_with_facts(
    EventInput(
        name="NBA Playoffs 2022: Golden State Warriors vs. Denver Nuggets - Partido 1",
        kind="sports.match",
        period=Period(
            start=HistoricalDate(year=2022, month=4, day=16, precision="day"),
            end=HistoricalDate(year=2022, month=4, day=16, precision="day"),
        ),
        place="Chase Center",
        location=LocationInput(
            name="Chase Center",
            city="San Francisco",
            country="Estados Unidos",
            lat=37.7680,
            lng=-122.3877,
        ),
        source_id=source_playoffs_id,
        source_locator="NBA Box Score Game 1 Western Conference First Round 2022",
        participants=[
            EventParticipantInput(
                type_id="sports.faced_in_match",
                subject_id=toscano_id,
                role="player",
                side="home",
                source_id=source_playoffs_id,
                source_locator="NBA Official Box Score: Juan Toscano-Anderson (Warriors)",
                period=Period(
                    start=HistoricalDate(year=2022, month=4, day=16, precision="day"),
                    end=HistoricalDate(year=2022, month=4, day=16, precision="day"),
                ),
                location=LocationInput(
                    name="Chase Center",
                    city="San Francisco",
                    country="Estados Unidos",
                    lat=37.7680,
                    lng=-122.3877,
                ),
                note="Juan Toscano-Anderson compitió con los Golden State Warriors en el triunfo 123-107 frente a los Denver Nuggets de Nikola Jokić.",
            ),
            EventParticipantInput(
                type_id="sports.faced_in_match",
                subject_id=jokic_id,
                role="player",
                side="away",
                source_id=source_playoffs_id,
                source_locator="NBA Official Box Score: Nikola Jokić (25 puntos, 10 rebotes)",
                period=Period(
                    start=HistoricalDate(year=2022, month=4, day=16, precision="day"),
                    end=HistoricalDate(year=2022, month=4, day=16, precision="day"),
                ),
                location=LocationInput(
                    name="Chase Center",
                    city="San Francisco",
                    country="Estados Unidos",
                    lat=37.7680,
                    lng=-122.3877,
                ),
                note="Nikola Jokić comandó a los Denver Nuggets con 25 puntos y 10 rebotes enfrentando a los Warriors en San Francisco.",
            ),
        ],
    )
)


# ==============================================================================
# 4. HECHOS Y RELACIONES DIRECTAS VERIFICADAS
# ==============================================================================
print("\n--- 4. Creando / Verificando Hechos Directos en el Grafo ---")

# 4.1 Nikola Jokić <-> Novak Djokovic (Encuentro cumbre del deporte serbio en Los Ángeles)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=jokic_id,
        object_id=djokovic_id,
        source_id=source_jokic_djokovic_id,
        source_locator="ATP Tour News, Novak Djokovic courtside and locker room meeting with Nikola Jokic at Crypto.com Arena, March 2, 2024",
        period=Period(
            start=HistoricalDate(year=2024, month=3, day=2, precision="day"),
            end=HistoricalDate(year=2024, month=3, day=2, precision="day"),
        ),
        location=LocationInput(
            name="Crypto.com Arena",
            city="Los Ángeles",
            country="Estados Unidos",
            lat=34.0430,
            lng=-118.2673,
        ),
        note=(
            "Novak Djokovic asistió a primera fila en el Crypto.com Arena de Los Ángeles para presenciar el duelo "
            "de los Nuggets de Jokić frente a los Lakers, reuniéndose en los vestidores para fundirse en un histórico abrazo "
            "entre las dos máximas leyendas vivientes del deporte serbio."
        ),
    )
)


# ==============================================================================
# 5. VERIFICACIÓN DEL CAMINO MÁS CORTO EN NEO4J
# ==============================================================================
print("\n================================================================================")
print("  CONSULTANDO CAMINO MÁS CORTO: NIKOLA JOKIĆ -> NIKOLA TESLA")
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
                WHEN 'Event' IN labels(n) THEN {
                    tipo: 'Event', 
                    id: n.id, 
                    nombre: n.search_name
                }
                WHEN 'Fact' IN labels(n) THEN {
                    tipo: 'Fact', 
                    id: n.id, 
                    type_id: n.type_id, 
                    role: n.role,
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
        start_id=jokic_id,
        target_id=tesla_id,
    ).single()

    if res:
        print(f"\nCamino encontrado! Longitud de relaciones: {res['longitud_relaciones']}")
        for idx, step in enumerate(res["camino"]):
            print(f" Paso {idx}: {json.dumps(step, ensure_ascii=False)}")
    else:
        print("No se encontró camino entre Nikola Jokić y Nikola Tesla.")

print("\n================================================================================")
print("  CARGA Y VERIFICACIÓN COMPLETADAS")
print("================================================================================")
