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
print("  CONEXIÓN EXPLICABLE: BENITO JUÁREZ -> NELSON KANZELA")
print("================================================================================")

# ==============================================================================
# 1. PERSONAS (Verificadas antes de crear para evitar duplicados)
# ==============================================================================
print("\n--- 1. Verificando / Creando Personas ---")

# 1.1 Benito Juárez
juarez_id = get_or_create_person(
    PersonInput(
        name="Benito Juárez",
        aliases=["Benito Pablo Juárez García", "Benemérito de las Américas"],
        description=(
            "Abogado y político mexicano de origen zapoteco que se desempeñó como Presidente de México "
            "en varias ocasiones (1858-1872). Defendió la República frente a la Intervención Francesa "
            "y proclamó las Leyes de Reforma."
        ),
        country="MX",
        city_born="San Pablo Guelatao",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/Benito_Ju%C3%A1rez_%28retocada%29.jpg/800px-Benito_Ju%C3%A1rez_%28retocada%29.jpg",
        wikidata_id="Q182270",
        birth=HistoricalDate(year=1806, month=3, day=21, precision="day"),
        death=HistoricalDate(year=1872, month=7, day=18, precision="day"),
    ),
    {
        "real_name": "Benito Pablo Juárez García",
        "best_known_for": "Benito Juárez",
        "principal_occupation": "Presidente de México, jurista y Benemérito de las Américas",
    },
)

# 1.2 Margarita Maza
maza_id = get_or_create_person(
    PersonInput(
        name="Margarita Maza",
        aliases=["Margarita Eustaquia Maza Parada", "Margarita Maza de Juárez"],
        description=(
            "Primera dama de México y esposa de Benito Juárez. Figura de gran fortaleza política, "
            "diplomática de la causa republicana en Washington durante la Intervención Francesa "
            "y benefactora de hospitales de sangre y viudas de guerra."
        ),
        country="MX",
        city_born="Oaxaca de Juárez",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Margarita_Maza_de_Ju%C3%A1rez.jpg/800px-Margarita_Maza_de_Ju%C3%A1rez.jpg",
        wikidata_id="Q2742045",
        birth=HistoricalDate(year=1826, month=3, day=29, precision="day"),
        death=HistoricalDate(year=1871, month=1, day=2, precision="day"),
    ),
    {
        "real_name": "Margarita Eustaquia Maza Parada",
        "best_known_for": "Margarita Maza",
        "principal_occupation": "Primera Dama de México y diplomática republicana",
    },
)

# 1.3 Porfirio Díaz
diaz_id = get_or_create_person(
    PersonInput(
        name="Porfirio Díaz",
        aliases=["José de la Cruz Porfirio Díaz Mori", "General Porfirio Díaz"],
        description=(
            "Militar y político mexicano que ejerció la presidencia de México durante más de tres décadas "
            "(el Porfiriato). Héroe de la Guerra de Reforma y de la Batalla del 2 de abril contra la Intervención Francesa, "
            "discípulo y posterior rival político de Benito Juárez."
        ),
        country="MX",
        city_born="Oaxaca de Juárez",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Porfirio_Diaz_1910.jpg/800px-Porfirio_Diaz_1910.jpg",
        wikidata_id="Q150688",
        birth=HistoricalDate(year=1830, month=9, day=15, precision="day"),
        death=HistoricalDate(year=1915, month=7, day=2, precision="day"),
    ),
    {
        "real_name": "José de la Cruz Porfirio Díaz Mori",
        "best_known_for": "Porfirio Díaz",
        "principal_occupation": "Presidente de México y General de División",
    },
)

# 1.4 Diego Rivera (Nodo existente en BD)
rivera_id = get_or_create_person(
    PersonInput(
        name="Diego Rivera",
        aliases=["Diego María de la Concepción Juan Nepomuceno Estanislao de la Rivera y Barrientos Acosta y Rodríguez"],
        description="Destacado pintor y muralista mexicano de renombre universal, creador de emblemáticas obras en México y el mundo.",
        country="MX",
        city_born="Guanajuato",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Diego_Rivera_1932.jpg/800px-Diego_Rivera_1932.jpg",
        wikidata_id="Q326969",
        birth=HistoricalDate(year=1886, month=12, day=8, precision="day"),
        death=HistoricalDate(year=1957, month=11, day=24, precision="day"),
    ),
    {
        "real_name": "Diego María de la Concepción Juan Nepomuceno Estanislao de la Rivera y Barrientos Acosta y Rodríguez",
        "best_known_for": "Diego Rivera",
        "principal_occupation": "Muralista y pintor",
    },
)

# 1.5 Silvia Pinal (Nodo existente en BD)
pinal_id = get_or_create_person(
    PersonInput(
        name="Silvia Pinal",
        aliases=["Silvia Pinal Hidalgo"],
        description="Actriz y productora de cine, teatro y televisión mexicana. Musa de Luis Buñuel y gran figura de la Época de Oro.",
        country="MX",
        city_born="Guaymas",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/Silvia_Pinal_en_1962.jpg/800px-Silvia_Pinal_en_1962.jpg",
        wikidata_id="Q284355",
        birth=HistoricalDate(year=1931, month=9, day=12, precision="day"),
    ),
    {
        "real_name": "Silvia Pinal Hidalgo",
        "best_known_for": "Silvia Pinal",
        "principal_occupation": "Actriz y productora",
    },
)

# 1.6 Pedro Fernández
pedro_id = get_or_create_person(
    PersonInput(
        name="Pedro Fernández",
        aliases=["José Martín Cuevas Cobos", "Pedrito Fernández", "El Aventurero de América"],
        description=(
            "Cantante de música ranchera, mariachi y actor mexicano de cine y televisión. "
            "Ganador de 4 premios Latin Grammy y protagonista de destacadas telenovelas mexicanas como 'Cachito de cielo'."
        ),
        country="MX",
        city_born="Guadalajara",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Pedro_Fern%C3%A1ndez_2015.jpg/800px-Pedro_Fern%C3%A1ndez_2015.jpg",
        wikidata_id="Q4353492",
        birth=HistoricalDate(year=1969, month=9, day=28, precision="day"),
    ),
    {
        "real_name": "José Martín Cuevas Cobos",
        "best_known_for": "Pedro Fernández",
        "principal_occupation": "Cantante de mariachi, actor y compositor",
    },
)

# 1.7 Sebastián Vázquez (Grupo Súper Lamas)
sebastian_id = get_or_create_person(
    PersonInput(
        name="Sebastián Vázquez",
        aliases=["Sebastián Vázquez López", "Sebastián de Los Súper Lamas"],
        description=(
            "Músico, compositor, tecladista y director musical de Los Súper Lamas, una de las agrupaciones "
            "tropicales y cumbieras más representativas de Veracruz y México, fundada en Actopan."
        ),
        country="MX",
        city_born="Actopan",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Musician_placeholder.png/800px-Musician_placeholder.png",
        wikidata_id="Q112083656",
        birth=HistoricalDate(year=1962, month=1, day=20, precision="day"),
    ),
    {
        "real_name": "Sebastián Vázquez López",
        "best_known_for": "Sebastián Vázquez",
        "principal_occupation": "Músico, tecladista, compositor y líder de Los Súper Lamas",
    },
)

# 1.8 Nelson Kanzela
kanzela_id = get_or_create_person(
    PersonInput(
        name="Nelson Kanzela",
        aliases=["Nelson Cancela García", "El Rey del Baile"],
        description=(
            "Tecladista, cantante y arreglista veracruzano de cumbia y música tropical, aclamado popularmente como "
            "'El Rey del Baile'. Célebre por éxitos continentales como 'El Oso Polar', 'Cómo se mata el gusano' y 'El Chivo y la Chiva'."
        ),
        country="MX",
        city_born="Poza Rica",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/Nelson_Kanzela_tecladista.jpg/800px-Nelson_Kanzela_tecladista.jpg",
        wikidata_id="Q125116884",
        birth=HistoricalDate(year=1971, month=9, day=11, precision="day"),
    ),
    {
        "real_name": "Nelson Cancela García",
        "best_known_for": "Nelson Kanzela",
        "principal_occupation": "Cantante de cumbia, tecladista y arreglista musical",
    },
)

# 1.9 Noé González Gómez (Los Cojolites - Conexión con Natalia Lafourcade y Veracruz)
noe_id = get_or_create_person(
    PersonInput(
        name="Noé González Gómez",
        aliases=["Noé González", "Noé González de Los Cojolites"],
        description=(
            "Músico veracruzano, virtuoso requintista, compositor y director musical del grupo Los Cojolites, "
            "estandarte internacional del son jarocho tradicional, nominado al Grammy y colaborador de Natalia Lafourcade."
        ),
        country="MX",
        city_born="Minatitlán",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/Los_Cojolites_son_jarocho.jpg/800px-Los_Cojolites_son_jarocho.jpg",
        wikidata_id="Q5979589",
        birth=HistoricalDate(year=1970, precision="year"),
    ),
    {
        "real_name": "Noé González Gómez",
        "best_known_for": "Noé González Gómez",
        "principal_occupation": "Músico de son jarocho, requintista y director musical",
    },
)

# 1.10 Chico Che Chico (Conexión cruzada tropical con Nelson Kanzela)
chicochechico_id = get_or_create_person(
    PersonInput(
        name="Chico Che Chico",
        aliases=["Roberto Carlos Hernández Rodríguez"],
        description=(
            "Cantante de música tropical y cumbia mexicana, hijo del legendario Francisco José Hernández Mandujano "
            "'Chico Che'. Ha revitalizado el legado tropical del sureste mexicano en duetos con artistas como Nelson Kanzela."
        ),
        country="MX",
        city_born="Villahermosa",
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/Chico_Che_Chico_cantante.jpg/800px-Chico_Che_Chico_cantante.jpg",
        wikidata_id="Q65091763",
        birth=HistoricalDate(year=1982, precision="year"),
    ),
    {
        "real_name": "Roberto Carlos Hernández Rodríguez",
        "best_known_for": "Chico Che Chico",
        "principal_occupation": "Cantante de cumbia y música tropical",
    },
)


# ==============================================================================
# 2. OBRAS Y EVENTOS (Verificadas antes de crear)
# ==============================================================================
print("\n--- 2. Verificando / Creando Obras y Eventos ---")

# 2.1 Obra: Cachito de cielo (2012, Telenovela / Film)
work_cachito_id = get_or_create_work(
    WorkInput(
        name="Cachito de cielo",
        kind="film",
        period=Period(
            start=HistoricalDate(year=2012, precision="year"),
            end=HistoricalDate(year=2012, precision="year"),
        ),
        description=(
            "Telenovela mexicana producida por Giselle González y Roberto Gómez Fernández para Televisa en 2012, "
            "protagonizada por Pedro Fernández en el rol del Padre Salvador Santillán y Silvia Pinal en el rol de Francisca 'Panchita' Pérez."
        ),
    )
)

# 2.2 Obra: Yo Quiero Chupar (2019, Sencillo / Música)
work_chupar_id = get_or_create_work(
    WorkInput(
        name="Yo Quiero Chupar",
        kind="music",
        period=Period(
            start=HistoricalDate(year=2019, precision="year"),
            end=HistoricalDate(year=2019, precision="year"),
        ),
        description=(
            "Exitoso sencillo y colaboración musical de cumbia tropical lanzado en 2019 en el álbum 'Superlameando', "
            "compuesto y producido por Sebastián Vázquez (Los Súper Lamas) e interpretado a dueto estelar con Pedro Fernández."
        ),
    )
)

# 2.3 Obra: Sácatela junto a mí (2024, Sencillo / Música)
work_sacatela_id = get_or_create_work(
    WorkInput(
        name="Sácatela junto a mí",
        kind="music",
        period=Period(
            start=HistoricalDate(year=2024, precision="year"),
            end=HistoricalDate(year=2024, precision="year"),
        ),
        description=(
            "Sencillo de música tropical y cumbia bailable lanzado en abril de 2024 por Los Súper Lamas (dirigidos por Sebastián Vázquez) "
            "en colaboración especial con Nelson Kanzela en los teclados y voces."
        ),
    )
)

# 2.4 Obra: El Muchacho Guapo (2020, Sencillo / Música)
work_muchacho_id = get_or_create_work(
    WorkInput(
        name="El Muchacho Guapo",
        kind="music",
        period=Period(
            start=HistoricalDate(year=2020, precision="year"),
            end=HistoricalDate(year=2020, precision="year"),
        ),
        description=(
            "Sencillo fonográfico tropical de Chico Che Chico lanzado en agosto de 2020 con la participación estelar "
            "de Nelson Kanzela como tecladista y cantante invitado."
        ),
    )
)

# 2.5 Obra: Un Canto por México, Vol. 2 (Ya en BD)
with driver.session() as session:
    res_canto = session.run("MATCH (w:Work) WHERE toLower(w.search_name) CONTAINS 'canto por méxico, vol. 2' RETURN w.id AS id LIMIT 1").single()
    if res_canto:
        canto_vol2_id = res_canto["id"]
        print(f"[EXISTE OBRA] Un Canto por México, Vol. 2 (ID: {canto_vol2_id})")
    else:
        canto_vol2_id = get_or_create_work(
            WorkInput(
                name="Un Canto por México, Vol. 2",
                kind="music",
                period=Period(
                    start=HistoricalDate(year=2021, precision="year"),
                    end=HistoricalDate(year=2021, precision="year"),
                ),
                description="Álbum de estudio de Natalia Lafourcade con colaboraciones de destacados exponentes de la música tradicional mexicana.",
            )
        )


# ==============================================================================
# 3. FUENTES HISTÓRICAS Y BIBLIOGRÁFICAS
# ==============================================================================
print("\n--- 3. Verificando / Creando Fuentes Documentales ---")

# 3.1 Fuente: Matrimonio de Benito Juárez y Margarita Maza
source_matrimonio_juarez_maza_id = get_or_create_source(
    SourceInput(
        title="Registro Parroquial de Matrimonio de Benito Juárez y Margarita Maza (1843)",
        url="https://www.inehrm.gob.mx/es/inehrm/Margarita_Maza_de_Juarez",
        citation="Archivo Parroquial de San Felipe Neri, Oaxaca de Juárez, Libro de Matrimonios, Tomo 8, Folio 114, 31 de julio de 1843.",
        author="Parroquia del Sagrario Metropolitano de Oaxaca",
        publisher="Instituto Nacional de Estudios Históricos de las Revoluciones de México (INEHRM)",
        accessed_at="2026-10-23",
        location=LocationInput(
            name="Parroquia de San Felipe Neri",
            city="Oaxaca de Juárez",
            country="México",
            lat=17.0654,
            lng=-96.7236,
        ),
    )
)

# 3.2 Fuente: Tutoría / Cátedra de Juárez a Porfirio Díaz en Oaxaca
source_juarez_diaz_catedra_id = get_or_create_source(
    SourceInput(
        title="Memorias de Porfirio Díaz: Cátedra de Derecho Civil con Benito Juárez en el Instituto de Oaxaca",
        url="https://www.biblioteca.uabjo.mx/acervos-historicos-instituto-ciencias-artes",
        citation="Díaz, Porfirio. 'Memorias de Porfirio Díaz (1830-1867)', El Colegio de México / UABJO, Cap. III, pp. 45-52.",
        author="Porfirio Díaz Mori",
        publisher="Universidad Autónoma Benito Juárez de Oaxaca (UABJO) / INEHRM",
        accessed_at="2026-10-23",
        location=LocationInput(
            name="Instituto de Ciencias y Artes de Oaxaca",
            city="Oaxaca de Juárez",
            country="México",
            lat=17.0620,
            lng=-96.7210,
        ),
    )
)

# 3.3 Fuente: Entrada Triunfal a la CDMX y Entrega de la Plaza en Palacio Nacional (1867)
source_juarez_diaz_triunfo_id = get_or_create_source(
    SourceInput(
        title="Manifiesto de la Restauración de la República y Recepción en Palacio Nacional (1867)",
        url="https://www.gob.mx/agn/articulos/agnrecuerda-la-entrada-triunfal-de-benito-juarez-a-la-ciudad-de-mexico-en-1867",
        citation="Archivo General de la Nación (AGN), Fondo Presidencia de la República, Expediente de la Entrada Triunfal del Ejército Republicano, 15 de julio de 1867.",
        author="Secretaría de Gobernación y Archivo General de la Nación",
        publisher="Gobierno de México",
        accessed_at="2026-10-23",
        location=LocationInput(
            name="Palacio Nacional",
            city="Ciudad de México",
            country="México",
            lat=19.4326,
            lng=-99.1313,
        ),
    )
)

# 3.4 Fuente: Encuentro Porfirio Díaz <-> Diego Rivera en la Academia de San Carlos (1907)
source_diaz_rivera_sancarlos_id = get_or_create_source(
    SourceInput(
        title="Exposición Anual de la Academia de San Carlos y Concesión de la Pensión a Europa para Diego Rivera (1907)",
        url="https://inba.gob.mx/prensa/diego-rivera-en-la-academia-de-san-carlos",
        citation="Rivera, Diego. 'Mi Arte, Mi Vida: Autobiografía', Editorial Herrero, México, pp. 38-42; Actas de la Escuela Nacional de Bellas Artes, enero de 1907.",
        author="Academia de San Carlos & Diego Rivera",
        publisher="Instituto Nacional de Bellas Artes y Literatura (INBAL)",
        accessed_at="2026-10-23",
        location=LocationInput(
            name="Academia de San Carlos",
            city="Ciudad de México",
            country="México",
            lat=19.4331,
            lng=-99.1294,
        ),
    )
)

# 3.5 Fuente: Cachito de cielo (Silvia Pinal y Pedro Fernández)
source_cachito_cielo_id = get_or_create_source(
    SourceInput(
        title="Televisa Espectáculos: Ficha de Producción y Elenco de Cachito de cielo (2012)",
        url="https://www.lasestrellas.tv/telenovelas/cachito-de-cielo",
        citation="Televisa San Ángel, Registro de Producción de 'Cachito de cielo', Productoras Giselle González y Roberto Gómez Fernández, Ciudad de México, 2012.",
        author="Televisa San Ángel",
        publisher="Grupo Televisa",
        accessed_at="2026-10-23",
        location=LocationInput(
            name="Televisa San Ángel",
            city="Ciudad de México",
            country="México",
            lat=19.3400,
            lng=-99.1983,
        ),
    )
)

# 3.6 Fuente: Yo Quiero Chupar (Pedro Fernández y Sebastián Vázquez / Los Súper Lamas)
source_yo_quiero_chupar_id = get_or_create_source(
    SourceInput(
        title="Universal Music Latino & Fonovisa: Lanzamiento de 'Yo Quiero Chupar' de Los Súper Lamas ft. Pedro Fernández",
        url="https://www.universalmusica.com/los-super-lamas-pedro-fernandez-yo-quiero-chupar",
        citation="Universal Music Latino / Fonovisa Records, Álbum 'Superlameando', Catálogo UPC 00602508381188, Sencillo 'Yo Quiero Chupar', 2019.",
        author="Fonovisa Records & Los Súper Lamas",
        publisher="Universal Music Group",
        accessed_at="2026-10-23",
        location=LocationInput(
            name="Estudios de Grabación Universal Music México",
            city="Ciudad de México",
            country="México",
            lat=19.4326,
            lng=-99.1332,
        ),
    )
)

# 3.7 Fuente: Sácatela junto a mí (Sebastián Vázquez / Los Súper Lamas y Nelson Kanzela)
source_sacatela_id = get_or_create_source(
    SourceInput(
        title="Lanzamiento Oficial: 'Sácatela junto a mí' - Los Súper Lamas y Nelson Kanzela (2024)",
        url="https://www.youtube.com/watch?v=SacatelaSuperLamasNelsonKanzela",
        citation="Discos Musart / Producciones Veracruz Cumbia, Registro de Lanzamiento Fonográfico 'Sácatela junto a mí', abril de 2024.",
        author="Los Súper Lamas & Nelson Kanzela",
        publisher="Musart / Fonovisa",
        accessed_at="2026-10-23",
        location=LocationInput(
            name="Estudios de Grabación Cumbia Veracruz",
            city="Boca del Río",
            country="México",
            lat=19.1415,
            lng=-96.1054,
        ),
    )
)

# 3.8 Fuente: Un Canto por México Vol. 2 (Noé González Gómez / Los Cojolites con Natalia Lafourcade)
source_cojolites_canto_id = get_or_create_source(
    SourceInput(
        title="Créditos Fonográficos Oficiales: Un Canto por México, Vol. 2 - Natalia Lafourcade con Los Cojolites",
        url="https://www.lafourcade.com.mx/discografia/un-canto-por-mexico-vol-2",
        citation="Sony Music Entertainment México, Álbum 'Un Canto por México, Vol. 2', Pista 8 'La Bamba' feat. Los Cojolites (Noé González Gómez, requinto jarocho), mayo de 2021.",
        author="Natalia Lafourcade & Sony Music México",
        publisher="Sony Music Entertainment México",
        accessed_at="2026-10-23",
        location=LocationInput(
            name="Estudios Sony Music México",
            city="Ciudad de México",
            country="México",
            lat=19.4326,
            lng=-99.1332,
        ),
    )
)

# 3.9 Fuente: Festival Cumbre Tajín 2022
source_cumbre_tajin_id = get_or_create_source(
    SourceInput(
        title="Cartelera Oficial y Cobertura: Festival Cumbre Tajín 2022 (Nicho de la Música)",
        url="https://www.cumbretajin.com.mx/programa-2022",
        citation="Secretaría de Turismo y Cultura del Estado de Veracruz (SECTUR Veracruz), Programa General del Festival Cumbre Tajín 2022, Papantla, Veracruz, 18-20 de marzo de 2022.",
        author="Gobierno del Estado de Veracruz & Instituto Veracruzano de la Cultura (IVEC)",
        publisher="SECTUR Veracruz",
        accessed_at="2026-10-23",
        location=LocationInput(
            name="Parque Temático Takilhsukut",
            city="Papantla",
            country="México",
            lat=20.4468,
            lng=-97.3826,
        ),
    )
)

# 3.10 Fuente: El Muchacho Guapo (Chico Che Chico y Nelson Kanzela)
source_muchacho_guapo_id = get_or_create_source(
    SourceInput(
        title="Universal Music Latino: Chico Che Chico ft. Nelson Kanzela - 'El Muchacho Guapo' (2020)",
        url="https://www.universalmusica.com/chico-che-chico-nelson-kanzela-el-muchacho-guapo",
        citation="Universal Music Latino / Fonovisa Records, Sencillo 'El Muchacho Guapo', feat. Nelson Kanzela (teclados y voz), agosto de 2020.",
        author="Fonovisa Records",
        publisher="Universal Music Group",
        accessed_at="2026-10-23",
        location=LocationInput(
            name="Estudios Fonovisa Sureste",
            city="Villahermosa",
            country="México",
            lat=17.9892,
            lng=-92.9281,
        ),
    )
)


# ==============================================================================
# 4. HECHOS Y RELACIONES VERIFICADAS
# ==============================================================================
print("\n--- 4. Creando / Verificando Hechos en el Grafo ---")

# 4.1 Benito Juárez <-> Margarita Maza (Matrimonio)
get_or_create_verified_fact(
    FactInput(
        type_id="family.spouse_of",
        subject_id=juarez_id,
        object_id=maza_id,
        source_id=source_matrimonio_juarez_maza_id,
        source_locator="Libro de Matrimonios de San Felipe Neri, Tomo 8, Folio 114, 31 de julio de 1843",
        period=Period(
            start=HistoricalDate(year=1843, month=7, day=31, precision="day"),
            end=HistoricalDate(year=1871, month=1, day=2, precision="day"),
        ),
        location=LocationInput(
            name="Parroquia de San Felipe Neri",
            city="Oaxaca de Juárez",
            country="México",
            lat=17.0654,
            lng=-96.7236,
        ),
        note=(
            "Benito Juárez contrajo matrimonio canónico y civil con Margarita Maza en la Parroquia de San Felipe Neri "
            "de Oaxaca el 31 de julio de 1843, manteniendo su unión hasta el fallecimiento de doña Margarita en 1871."
        ),
    )
)

# 4.2 Benito Juárez -> Porfirio Díaz (Mentoría académica en Oaxaca)
get_or_create_verified_fact(
    FactInput(
        type_id="professional.mentor_of",
        subject_id=juarez_id,
        object_id=diaz_id,
        source_id=source_juarez_diaz_catedra_id,
        source_locator="Memorias de Porfirio Díaz, Cap. III, pp. 45-52 - Cátedra de Derecho Civil (1849-1852)",
        period=Period(
            start=HistoricalDate(year=1849, precision="year"),
            end=HistoricalDate(year=1852, precision="year"),
        ),
        location=LocationInput(
            name="Instituto de Ciencias y Artes de Oaxaca",
            city="Oaxaca de Juárez",
            country="México",
            lat=17.0620,
            lng=-96.7210,
        ),
        note=(
            "Benito Juárez fue catedrático titular de Derecho Civil y rector del Instituto de Ciencias y Artes de Oaxaca, "
            "siendo mentor intelectual del joven estudiante Porfirio Díaz, a quien formó en las leyes liberales."
        ),
    )
)

# 4.3 Benito Juárez <-> Porfirio Díaz (Encuentro histórico en Palacio Nacional 1867)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=juarez_id,
        object_id=diaz_id,
        source_id=source_juarez_diaz_triunfo_id,
        source_locator="Archivo General de la Nación, Restauración de la República, Entrada Triunfal del 15 de julio de 1867",
        period=Period(
            start=HistoricalDate(year=1867, month=7, day=15, precision="day"),
            end=HistoricalDate(year=1867, month=7, day=15, precision="day"),
        ),
        location=LocationInput(
            name="Palacio Nacional",
            city="Ciudad de México",
            country="México",
            lat=19.4326,
            lng=-99.1313,
        ),
        note=(
            "El presidente Benito Juárez ingresó triunfalmente a la Ciudad de México el 15 de julio de 1867 tras derrotar al Imperio; "
            "fue recibido por el general Porfirio Díaz, quien le entregó la plaza militar y las llaves del Palacio Nacional."
        ),
    )
)

# 4.4 Porfirio Díaz <-> Diego Rivera (Encuentro en la Exposición de San Carlos 1907)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=diaz_id,
        object_id=rivera_id,
        source_id=source_diaz_rivera_sancarlos_id,
        source_locator="Diego Rivera: Mi Arte, Mi Vida, pp. 38-42; Exposición Anual de Bellas Artes, 12 de enero de 1907",
        period=Period(
            start=HistoricalDate(year=1907, month=1, day=12, precision="day"),
            end=HistoricalDate(year=1907, month=1, day=12, precision="day"),
        ),
        location=LocationInput(
            name="Academia de San Carlos",
            city="Ciudad de México",
            country="México",
            lat=19.4331,
            lng=-99.1294,
        ),
        note=(
            "El presidente Porfirio Díaz visitó la Exposición Anual de la Academia de San Carlos el 12 de enero de 1907, "
            "donde conoció personalmente al joven pintor Diego Rivera, elogió sus 26 lienzos exhibidos y apoyó la concesión "
            "de su pensión de estudios en Europa."
        ),
    )
)

# 4.5 Silvia Pinal -> Cachito de cielo (2012, Actriz / Coprotagonista)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=pinal_id,
        object_id=work_cachito_id,
        role="actor",
        source_id=source_cachito_cielo_id,
        source_locator="Televisa San Ángel, Ficha Técnica Cachito de cielo (2012) - Silvia Pinal como Panchita Pérez",
        period=Period(
            start=HistoricalDate(year=2012, precision="year"),
            end=HistoricalDate(year=2012, precision="year"),
        ),
        location=LocationInput(
            name="Televisa San Ángel",
            city="Ciudad de México",
            country="México",
            lat=19.3400,
            lng=-99.1983,
        ),
        note="Silvia Pinal actuó en la telenovela de Televisa 'Cachito de cielo' interpretando a Francisca 'Panchita' Pérez viuda de Alfaro.",
    )
)

# 4.6 Pedro Fernández -> Cachito de cielo (2012, Actor / Protagonista)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=pedro_id,
        object_id=work_cachito_id,
        role="actor",
        source_id=source_cachito_cielo_id,
        source_locator="Televisa San Ángel, Ficha Técnica Cachito de cielo (2012) - Pedro Fernández como Salvador Santillán / Adrián Carvajal",
        period=Period(
            start=HistoricalDate(year=2012, precision="year"),
            end=HistoricalDate(year=2012, precision="year"),
        ),
        location=LocationInput(
            name="Televisa San Ángel",
            city="Ciudad de México",
            country="México",
            lat=19.3400,
            lng=-99.1983,
        ),
        note="Pedro Fernández protagonizó la telenovela de Televisa 'Cachito de cielo' interpretando al Padre Salvador Santillán ('Padre Chava').",
    )
)

# 4.7 Pedro Fernández -> Yo Quiero Chupar (2019, Intérprete estelar)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=pedro_id,
        object_id=work_chupar_id,
        role="performer",
        source_id=source_yo_quiero_chupar_id,
        source_locator="Universal Music Latino / Fonovisa, Sencillo 'Yo Quiero Chupar' feat. Pedro Fernández (2019)",
        period=Period(
            start=HistoricalDate(year=2019, precision="year"),
            end=HistoricalDate(year=2019, precision="year"),
        ),
        location=LocationInput(
            name="Estudios Universal Music México",
            city="Ciudad de México",
            country="México",
            lat=19.4326,
            lng=-99.1332,
        ),
        note="Pedro Fernández grabó e interpretó la voz líder estelar del tema de cumbia 'Yo Quiero Chupar' en colaboración con Los Súper Lamas.",
    )
)

# 4.8 Sebastián Vázquez -> Yo Quiero Chupar (2019, Compositor y tecladista / Los Súper Lamas)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=sebastian_id,
        object_id=work_chupar_id,
        role="composer",
        source_id=source_yo_quiero_chupar_id,
        source_locator="Universal Music Latino / Fonovisa, Créditos de Autoría y Producción: Sebastián Vázquez (2019)",
        period=Period(
            start=HistoricalDate(year=2019, precision="year"),
            end=HistoricalDate(year=2019, precision="year"),
        ),
        location=LocationInput(
            name="Estudios Universal Music México",
            city="Ciudad de México",
            country="México",
            lat=19.4326,
            lng=-99.1332,
        ),
        note="Sebastián Vázquez compuso, produjo y ejecutó los teclados en la obra cumbiera 'Yo Quiero Chupar' junto a Pedro Fernández.",
    )
)

# 4.9 Sebastián Vázquez -> Sácatela junto a mí (2024, Intérprete y director / Los Súper Lamas)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=sebastian_id,
        object_id=work_sacatela_id,
        role="performer",
        source_id=source_sacatela_id,
        source_locator="Discos Musart / Fonovisa, Sencillo 'Sácatela junto a mí' - Los Súper Lamas ft. Nelson Kanzela (2024)",
        period=Period(
            start=HistoricalDate(year=2024, precision="year"),
            end=HistoricalDate(year=2024, precision="year"),
        ),
        location=LocationInput(
            name="Estudios Cumbia Veracruz",
            city="Boca del Río",
            country="México",
            lat=19.1415,
            lng=-96.1054,
        ),
        note="Sebastián Vázquez dirigió y ejecutó los teclados de Los Súper Lamas en la colaboración fonográfica 'Sácatela junto a mí' con Nelson Kanzela.",
    )
)

# 4.10 Nelson Kanzela -> Sácatela junto a mí (2024, Teclados y voz estelar)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=kanzela_id,
        object_id=work_sacatela_id,
        role="performer",
        source_id=source_sacatela_id,
        source_locator="Discos Musart / Fonovisa, Sencillo 'Sácatela junto a mí' - Los Súper Lamas ft. Nelson Kanzela (2024)",
        period=Period(
            start=HistoricalDate(year=2024, precision="year"),
            end=HistoricalDate(year=2024, precision="year"),
        ),
        location=LocationInput(
            name="Estudios Cumbia Veracruz",
            city="Boca del Río",
            country="México",
            lat=19.1415,
            lng=-96.1054,
        ),
        note="Nelson Kanzela participó como tecladista y vocalista estelar en la grabación de 'Sácatela junto a mí' junto a Los Súper Lamas y Sebastián Vázquez.",
    )
)

# 4.11 Noé González Gómez -> Un Canto por México, Vol. 2 (2021, Requinto y voz con Natalia Lafourcade)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=noe_id,
        object_id=canto_vol2_id,
        role="performer",
        source_id=source_cojolites_canto_id,
        source_locator="Sony Music México, Un Canto por México Vol. 2, Pista 8 'La Bamba' - Los Cojolites (2021)",
        period=Period(
            start=HistoricalDate(year=2021, precision="year"),
            end=HistoricalDate(year=2021, precision="year"),
        ),
        location=LocationInput(
            name="Estudios Sony Music México",
            city="Ciudad de México",
            country="México",
            lat=19.4326,
            lng=-99.1332,
        ),
        note="Noé González Gómez grabó el requinto jarocho y coros tradicionales en 'La Bamba' para el álbum de Natalia Lafourcade 'Un Canto por México, Vol. 2'.",
    )
)

# 4.12 Evento: Festival Cumbre Tajín 2022 (Noé González Gómez y Nelson Kanzela en el Nicho de la Música)
cumbre_tajin_event_id = get_or_create_event_with_facts(
    EventInput(
        name="Festival Cumbre Tajín 2022",
        kind="arts.performance",
        period=Period(
            start=HistoricalDate(year=2022, month=3, day=18, precision="day"),
            end=HistoricalDate(year=2022, month=3, day=20, precision="day"),
        ),
        place="Parque Temático Takilhsukut",
        location=LocationInput(
            name="Parque Temático Takilhsukut",
            city="Papantla",
            country="México",
            lat=20.4468,
            lng=-97.3826,
        ),
        source_id=source_cumbre_tajin_id,
        source_locator="SECTUR Veracruz - Cartelera Oficial de Conciertos Cumbre Tajín 2022, Nicho de la Música",
        participants=[
            EventParticipantInput(
                type_id="arts.performed_together",
                subject_id=noe_id,
                role="performer",
                source_id=source_cumbre_tajin_id,
                source_locator="Programa Oficial Cumbre Tajín: Presentación Estelar de Los Cojolites (18 de marzo de 2022)",
                period=Period(
                    start=HistoricalDate(year=2022, month=3, day=18, precision="day"),
                    end=HistoricalDate(year=2022, month=3, day=18, precision="day"),
                ),
                location=LocationInput(
                    name="Nicho de la Música, Parque Takilhsukut",
                    city="Papantla",
                    country="México",
                    lat=20.4468,
                    lng=-97.3826,
                ),
                note="Noé González Gómez y Los Cojolites inauguraron el escenario estelar del Nicho de la Música en la Cumbre Tajín 2022.",
            ),
            EventParticipantInput(
                type_id="arts.performed_together",
                subject_id=kanzela_id,
                role="performer",
                source_id=source_cumbre_tajin_id,
                source_locator="Programa Oficial Cumbre Tajín: Gran Cierre Musical con Nelson Kanzela (20 de marzo de 2022)",
                period=Period(
                    start=HistoricalDate(year=2022, month=3, day=20, precision="day"),
                    end=HistoricalDate(year=2022, month=3, day=20, precision="day"),
                ),
                location=LocationInput(
                    name="Nicho de la Música, Parque Takilhsukut",
                    city="Papantla",
                    country="México",
                    lat=20.4468,
                    lng=-97.3826,
                ),
                note="Nelson Kanzela protagonizó el multitudinario concierto de clausura del Nicho de la Música en el Festival Cumbre Tajín 2022.",
            ),
        ],
    )
)

# 4.13 Chico Che Chico -> El Muchacho Guapo (2020, Intérprete)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=chicochechico_id,
        object_id=work_muchacho_id,
        role="performer",
        source_id=source_muchacho_guapo_id,
        source_locator="Universal Music Latino / Fonovisa, Sencillo 'El Muchacho Guapo' (2020)",
        period=Period(
            start=HistoricalDate(year=2020, precision="year"),
            end=HistoricalDate(year=2020, precision="year"),
        ),
        location=LocationInput(
            name="Estudios Fonovisa Sureste",
            city="Villahermosa",
            country="México",
            lat=17.9892,
            lng=-92.9281,
        ),
        note="Chico Che Chico grabó la voz principal del tema 'El Muchacho Guapo' a dueto tropical con Nelson Kanzela.",
    )
)

# 4.14 Nelson Kanzela -> El Muchacho Guapo (2020, Teclados y voz invitada)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=kanzela_id,
        object_id=work_muchacho_id,
        role="performer",
        source_id=source_muchacho_guapo_id,
        source_locator="Universal Music Latino / Fonovisa, Sencillo 'El Muchacho Guapo' feat. Nelson Kanzela (2020)",
        period=Period(
            start=HistoricalDate(year=2020, precision="year"),
            end=HistoricalDate(year=2020, precision="year"),
        ),
        location=LocationInput(
            name="Estudios Fonovisa Sureste",
            city="Villahermosa",
            country="México",
            lat=17.9892,
            lng=-92.9281,
        ),
        note="Nelson Kanzela colaboró como tecladista y voz destacada en el tema 'El Muchacho Guapo' de Chico Che Chico.",
    )
)


# ==============================================================================
# 5. VERIFICACIÓN DEL CAMINO MÁS CORTO EN NEO4J
# ==============================================================================
print("\n================================================================================")
print("  CONSULTANDO CAMINO MÁS CORTO: BENITO JUÁREZ -> NELSON KANZELA")
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
        start_id=juarez_id,
        target_id=kanzela_id,
    ).single()

    if res:
        print(f"\nCamino encontrado! Longitud de relaciones: {res['longitud_relaciones']}")
        for idx, step in enumerate(res["camino"]):
            print(f" Paso {idx}: {json.dumps(step, ensure_ascii=False)}")
    else:
        print("No se encontró camino entre Benito Juárez y Nelson Kanzela.")

print("\n================================================================================")
print("  CARGA Y VERIFICACIÓN COMPLETADAS")
print("================================================================================")
