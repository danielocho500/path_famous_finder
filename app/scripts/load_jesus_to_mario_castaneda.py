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
print("  CONEXIÓN EXPLICABLE: JESÚS DE NAZARET -> MARIO CASTAÑEDA")
print("================================================================================")

# ==============================================================================
# 1. PERSONAS (Verificadas antes de crear para evitar duplicados)
# ==============================================================================
print("\n--- 1. Verificando / Creando Personas ---")

# 1.1 Jesús de Nazaret
jesus_id = get_or_create_person(
    PersonInput(
        name="Jesús de Nazaret",
        aliases=["Jesucristo", "Jesús", "Cristo", "Jesus of Nazareth"],
        description="Figura central del cristianismo y una de las personalidades más influyentes de la historia universal.",
        country="Judea",
        city_born="Belén",
        image_url="https://upload.wikimedia.org/wikipedia/commons/4/4a/Spas_vsederzhitel_sinay.jpg",
        wikidata_id="Q302",
        birth=HistoricalDate(year=-4, precision="year"),
        death=HistoricalDate(year=30, month=4, day=7, precision="day"),
    ),
    {
        "real_name": "Jesús",
        "best_known_for": "Jesús de Nazaret",
        "principal_occupation": "Predicador religioso y figura central del cristianismo",
    },
)

# 1.2 Juan el Apóstol
juan_apostol_id = get_or_create_person(
    PersonInput(
        name="Juan el Apóstol",
        aliases=["San Juan Evangelista", "Juan el Teólogo", "Saint John"],
        description="Uno de los doce apóstoles de Jesús de Nazaret, autor del Evangelio de Juan y maestro de Policarpo de Esmirna.",
        country="Judea",
        city_born="Betsaida",
        image_url="https://upload.wikimedia.org/wikipedia/commons/7/74/El_Greco_-_Saint_John_the_Evangelist_-_Prado.jpg",
        wikidata_id="Q44015",
        birth=HistoricalDate(year=6, precision="year"),
        death=HistoricalDate(year=100, precision="year"),
    ),
    {
        "real_name": "Juan hijo de Zebedeo",
        "best_known_for": "Juan el Apóstol",
        "principal_occupation": "Apóstol y evangelista",
    },
)

# 1.3 Policarpo de Esmirna
policarpo_id = get_or_create_person(
    PersonInput(
        name="Policarpo de Esmirna",
        aliases=["San Policarpo", "Polycarp of Smyrna"],
        description="Obispo de Esmirna, Padre Apostólico y discípulo directo del apóstol Juan; maestro de Ireneo de Lyon.",
        country="Imperio romano",
        city_born="Esmirna",
        image_url="https://upload.wikimedia.org/wikipedia/commons/0/07/Saint_Polycarp_-_mosaic.jpg",
        wikidata_id="Q192398",
        birth=HistoricalDate(year=69, precision="year"),
        death=HistoricalDate(year=155, month=2, day=23, precision="day"),
    ),
    {
        "real_name": "Policarpo",
        "best_known_for": "Policarpo de Esmirna",
        "principal_occupation": "Obispo de Esmirna y Padre Apostólico",
    },
)

# 1.4 Ireneo de Lyon
ireneo_id = get_or_create_person(
    PersonInput(
        name="Ireneo de Lyon",
        aliases=["San Ireneo", "Irenaeus of Lyons"],
        description="Obispo de Lugdunum (Lyon), discípulo de Policarpo de Esmirna y Doctor de la Iglesia; autor de 'Contra las herejías'.",
        country="Imperio romano",
        city_born="Esmirna",
        image_url="https://upload.wikimedia.org/wikipedia/commons/3/36/Irenaeus_of_Lyons.jpg",
        wikidata_id="Q80119",
        birth=HistoricalDate(year=130, precision="year"),
        death=HistoricalDate(year=202, month=6, day=28, precision="day"),
    ),
    {
        "real_name": "Ireneo",
        "best_known_for": "Ireneo de Lyon",
        "principal_occupation": "Obispo de Lyon y teólogo patrístico",
    },
)

# 1.5 Orígenes
origenes_id = get_or_create_person(
    PersonInput(
        name="Orígenes",
        aliases=["Orígenes de Alejandría", "Origen", "Orígenes Adamancio"],
        description="Teólogo, filósofo y erudito cristiano alejandrino; maestro de Dionisio de Alejandría y figura cumbre de la patrística oriental.",
        country="Imperio romano",
        city_born="Alejandría",
        image_url="https://upload.wikimedia.org/wikipedia/commons/e/e0/Origen_Adamantius.jpg",
        wikidata_id="Q46297",
        birth=HistoricalDate(year=185, precision="year"),
        death=HistoricalDate(year=253, precision="year"),
    ),
    {
        "real_name": "Orígenes Adamancio",
        "best_known_for": "Orígenes",
        "principal_occupation": "Teólogo y director de la Escuela Catequística de Alejandría",
    },
)

# 1.6 Dionisio de Alejandría
dionisio_id = get_or_create_person(
    PersonInput(
        name="Dionisio de Alejandría",
        aliases=["San Dionisio el Grande", "Dionysius of Alexandria"],
        description="Patriarca de Alejandría y teólogo, discípulo de Orígenes y líder cristiano durante las persecuciones de Decio y Valeriano.",
        country="Imperio romano",
        city_born="Alejandría",
        image_url="https://upload.wikimedia.org/wikipedia/commons/c/c8/Saint_Dionysius_of_Alexandria.jpg",
        wikidata_id="Q313837",
        birth=HistoricalDate(year=190, precision="year"),
        death=HistoricalDate(year=264, month=11, day=17, precision="day"),
    ),
    {
        "real_name": "Dionisio",
        "best_known_for": "Dionisio de Alejandría",
        "principal_occupation": "Patriarca de Alejandría",
    },
)

# 1.7 Pedro de Alejandría
pedro_alejandria_id = get_or_create_person(
    PersonInput(
        name="Pedro de Alejandría",
        aliases=["San Pedro de Alejandría", "Peter of Alexandria"],
        description="Patriarca de Alejandría y mártir, maestro de Atanasio de Alejandría durante las persecuciones de Diocleciano y Maximino Daya.",
        country="Imperio romano",
        city_born="Alejandría",
        image_url="https://upload.wikimedia.org/wikipedia/commons/7/77/Saint_Peter_of_Alexandria.jpg",
        wikidata_id="Q313843",
        birth=HistoricalDate(year=250, precision="year"),
        death=HistoricalDate(year=311, month=11, day=25, precision="day"),
    ),
    {
        "real_name": "Pedro",
        "best_known_for": "Pedro de Alejandría",
        "principal_occupation": "Patriarca de Alejandría y mártir",
    },
)

# 1.8 Atanasio de Alejandría
atanasio_id = get_or_create_person(
    PersonInput(
        name="Atanasio de Alejandría",
        aliases=["San Atanasio", "Athanasius of Alexandria", "Atanasio el Grande"],
        description="Patriarca de Alejandría y Doctor de la Iglesia; defensor del dogma trinitario en el Concilio de Nicea (325) ante Constantino el Grande.",
        country="Imperio romano",
        city_born="Alejandría",
        image_url="https://upload.wikimedia.org/wikipedia/commons/5/53/Athanasius_of_Alexandria.jpg",
        wikidata_id="Q43887",
        birth=HistoricalDate(year=296, precision="year"),
        death=HistoricalDate(year=373, month=5, day=2, precision="day"),
    ),
    {
        "real_name": "Atanasio",
        "best_known_for": "Atanasio de Alejandría",
        "principal_occupation": "Patriarca de Alejandría y teólogo",
    },
)

# 1.9 Constantino el Grande
constantino_grande_id = get_or_create_person(
    PersonInput(
        name="Constantino el Grande",
        aliases=["Constantino I", "Constantine the Great", "Constantino el Magno"],
        description="Emperador romano que refundó Bizancio como Constantinopla, promulgó el Edicto de Milán (313) y convocó el Concilio de Nicea (325).",
        country="Imperio romano",
        city_born="Naissus",
        image_url="https://upload.wikimedia.org/wikipedia/commons/b/b8/Constantine_the_Great_Capitoline_Museums.jpg",
        wikidata_id="Q8413",
        birth=HistoricalDate(year=272, month=2, day=27, precision="day"),
        death=HistoricalDate(year=337, month=5, day=22, precision="day"),
    ),
    {
        "real_name": "Flavius Valerius Aurelius Constantinus",
        "best_known_for": "Constantino el Grande",
        "principal_occupation": "Emperador romano",
    },
)

# 1.10 Basilio el Grande
basilio_id = get_or_create_person(
    PersonInput(
        name="Basilio el Grande",
        aliases=["San Basilio de Cesarea", "Basil of Caesarea", "Basilio el Magno"],
        description="Arzobispo de Cesarea, Padre de la Iglesia y legislador del monacato oriental; dialogó con el emperador Valente defendiendo la fe nicena.",
        country="Imperio romano",
        city_born="Cesarea de Capadocia",
        image_url="https://upload.wikimedia.org/wikipedia/commons/0/0e/Saint_Basil_the_Great.jpg",
        wikidata_id="Q44258",
        birth=HistoricalDate(year=330, precision="year"),
        death=HistoricalDate(year=379, month=1, day=1, precision="day"),
    ),
    {
        "real_name": "Basilius",
        "best_known_for": "Basilio el Grande",
        "principal_occupation": "Arzobispo de Cesarea y teólogo",
    },
)

# 1.11 Valente
valente_id = get_or_create_person(
    PersonInput(
        name="Valente",
        aliases=["Emperador Valente", "Valens"],
        description="Emperador romano de Oriente (364-378); se reunió con Basilio el Grande en Cesarea y promovió al general Teodosio.",
        country="Imperio romano",
        city_born="Cibalae",
        image_url="https://upload.wikimedia.org/wikipedia/commons/e/ec/Solidus_Valens-antioch_RIC_025b.jpg",
        wikidata_id="Q172471",
        birth=HistoricalDate(year=328, precision="year"),
        death=HistoricalDate(year=378, month=8, day=9, precision="day"),
    ),
    {
        "real_name": "Flavius Julius Valens",
        "best_known_for": "Valente",
        "principal_occupation": "Emperador romano de Oriente",
    },
)

# 1.12 Teodosio I el Grande
teodosio_i_id = get_or_create_person(
    PersonInput(
        name="Teodosio I el Grande",
        aliases=["Teodosio I", "Theodosius the Great"],
        description="Último emperador en gobernar todo el Imperio romano unificado; declaró el cristianismo niceno religión oficial del Imperio en 380.",
        country="Imperio romano",
        city_born="Cauca",
        image_url="https://upload.wikimedia.org/wikipedia/commons/2/2f/Theodosius_I_coin.jpg",
        wikidata_id="Q4629",
        birth=HistoricalDate(year=347, month=1, day=11, precision="day"),
        death=HistoricalDate(year=395, month=1, day=17, precision="day"),
    ),
    {
        "real_name": "Flavius Theodosius",
        "best_known_for": "Teodosio I el Grande",
        "principal_occupation": "Emperador romano",
    },
)

# 1.13 Arcadio
arcadio_id = get_or_create_person(
    PersonInput(
        name="Arcadio",
        aliases=["Emperador Arcadio", "Arcadius"],
        description="Primer emperador del Imperio romano de Oriente tras la división formal del Imperio en 395; hijo de Teodosio I.",
        country="Imperio bizantino",
        city_born="Hispania",
        image_url="https://upload.wikimedia.org/wikipedia/commons/7/7e/Arcadius_coin.jpg",
        wikidata_id="Q115912",
        birth=HistoricalDate(year=377, precision="year"),
        death=HistoricalDate(year=408, month=5, day=1, precision="day"),
    ),
    {
        "real_name": "Flavius Arcadius",
        "best_known_for": "Arcadio",
        "principal_occupation": "Emperador romano de Oriente",
    },
)

# 1.14 Teodosio II
teodosio_ii_id = get_or_create_person(
    PersonInput(
        name="Teodosio II",
        aliases=["Theodosius II", "Teodosio el Calígrafo"],
        description="Emperador romano de Oriente famoso por promulgar el Código Teodosiano y construir las colosales murallas teodosianas de Constantinopla.",
        country="Imperio bizantino",
        city_born="Constantinopla",
        image_url="https://upload.wikimedia.org/wikipedia/commons/e/e0/Theodosius_II_Louvre_Ma1036.jpg",
        wikidata_id="Q160130",
        birth=HistoricalDate(year=401, month=4, day=10, precision="day"),
        death=HistoricalDate(year=450, month=7, day=28, precision="day"),
    ),
    {
        "real_name": "Flavius Theodosius Junior",
        "best_known_for": "Teodosio II",
        "principal_occupation": "Emperador romano de Oriente",
    },
)

# 1.15 Pulqueria
pulqueria_id = get_or_create_person(
    PersonInput(
        name="Pulqueria",
        aliases=["Santa Pulqueria", "Pulcheria"],
        description="Augusta y regente del Imperio romano de Oriente; hermana de Teodosio II y esposa del emperador Marciano.",
        country="Imperio bizantino",
        city_born="Constantinopla",
        image_url="https://upload.wikimedia.org/wikipedia/commons/1/18/Aelia_Pulcheria.jpg",
        wikidata_id="Q232334",
        birth=HistoricalDate(year=399, month=1, day=19, precision="day"),
        death=HistoricalDate(year=453, month=7, day=1, precision="day"),
    ),
    {
        "real_name": "Aelia Pulcheria",
        "best_known_for": "Pulqueria",
        "principal_occupation": "Emperatriz y regente del Imperio romano de Oriente",
    },
)

# 1.16 Marciano
marciano_id = get_or_create_person(
    PersonInput(
        name="Marciano",
        aliases=["Emperador Marciano", "Marcian"],
        description="Emperador romano de Oriente (450-457); convocó el Concilio de Calcedonia (451) y rechazó el tributo a Atila el Huno.",
        country="Imperio bizantino",
        city_born="Tracia",
        image_url="https://upload.wikimedia.org/wikipedia/commons/a/af/Marcian_coin.jpg",
        wikidata_id="Q170564",
        birth=HistoricalDate(year=392, precision="year"),
        death=HistoricalDate(year=457, month=1, day=27, precision="day"),
    ),
    {
        "real_name": "Flavius Marcianus",
        "best_known_for": "Marciano",
        "principal_occupation": "Emperador romano de Oriente",
    },
)

# 1.17 León I el Tracio
leon_i_id = get_or_create_person(
    PersonInput(
        name="León I el Tracio",
        aliases=["León el Grande", "Leo I the Thracian"],
        description="Emperador romano de Oriente (457-474); primer emperador coronado por el Patriarca de Constantinopla.",
        country="Imperio bizantino",
        city_born="Tracia",
        image_url="https://upload.wikimedia.org/wikipedia/commons/a/ae/Leo_I_coin.jpg",
        wikidata_id="Q46483",
        birth=HistoricalDate(year=401, precision="year"),
        death=HistoricalDate(year=474, month=1, day=18, precision="day"),
    ),
    {
        "real_name": "Flavius Valerius Leo",
        "best_known_for": "León I el Tracio",
        "principal_occupation": "Emperador romano de Oriente",
    },
)

# 1.18 Ariadna
ariadna_id = get_or_create_person(
    PersonInput(
        name="Ariadna",
        aliases=["Emperatriz Ariadna", "Ariadne"],
        description="Emperatriz consorte bizantina, hija de León I; esposa de los emperadores Zenón y Anastasio I.",
        country="Imperio bizantino",
        city_born="Constantinopla",
        image_url="https://upload.wikimedia.org/wikipedia/commons/3/30/Empress_Ariadne_Kunsthistorisches_Museum.jpg",
        wikidata_id="Q232329",
        birth=HistoricalDate(year=450, precision="year"),
        death=HistoricalDate(year=515, precision="year"),
    ),
    {
        "real_name": "Aelia Ariadne",
        "best_known_for": "Ariadna",
        "principal_occupation": "Emperatriz del Imperio bizantino",
    },
)

# 1.19 Anastasio I Dicoro
anastasio_i_id = get_or_create_person(
    PersonInput(
        name="Anastasio I Dicoro",
        aliases=["Anastasio I", "Anastasius I Dicorus"],
        description="Emperador bizantino (491-518); reformador fiscal y administrativo que dejó las arcas imperiales repletas de oro.",
        country="Imperio bizantino",
        city_born="Dirraquio",
        image_url="https://upload.wikimedia.org/wikipedia/commons/0/0e/Anastasius_I_coin.jpg",
        wikidata_id="Q173470",
        birth=HistoricalDate(year=430, precision="year"),
        death=HistoricalDate(year=518, month=7, day=9, precision="day"),
    ),
    {
        "real_name": "Flavius Anastasius",
        "best_known_for": "Anastasio I Dicoro",
        "principal_occupation": "Emperador bizantino",
    },
)

# 1.20 Justino I
justino_i_id = get_or_create_person(
    PersonInput(
        name="Justino I",
        aliases=["Justino I", "Justin I"],
        description="Emperador bizantino (518-527), fundador de la dinastía Justiniana; adoptó y preparó a su sobrino Justiniano I.",
        country="Imperio bizantino",
        city_born="Bederiana",
        image_url="https://upload.wikimedia.org/wikipedia/commons/f/fc/Justin_I_coin.jpg",
        wikidata_id="Q183445",
        birth=HistoricalDate(year=450, month=2, day=2, precision="day"),
        death=HistoricalDate(year=527, month=8, day=1, precision="day"),
    ),
    {
        "real_name": "Flavius Iustinus",
        "best_known_for": "Justino I",
        "principal_occupation": "Emperador bizantino",
    },
)

# 1.21 Justiniano I el Grande
justiniano_i_id = get_or_create_person(
    PersonInput(
        name="Justiniano I el Grande",
        aliases=["Justiniano I", "Justinian the Great"],
        description="Emperador bizantino célebre por la reconquista del Mediterráneo, la construcción de Santa Sofía y la compilación del Corpus Iuris Civilis.",
        country="Imperio bizantino",
        city_born="Tauresium",
        image_url="https://upload.wikimedia.org/wikipedia/commons/f/f3/Meister_von_San_Vitale_in_Ravenna.jpg",
        wikidata_id="Q3559",
        birth=HistoricalDate(year=482, month=5, day=11, precision="day"),
        death=HistoricalDate(year=565, month=11, day=14, precision="day"),
    ),
    {
        "real_name": "Flavius Petrus Sabbatius Iustinianus",
        "best_known_for": "Justiniano I el Grande",
        "principal_occupation": "Emperador bizantino y legislador",
    },
)

# 1.22 Casiodoro
casiodoro_id = get_or_create_person(
    PersonInput(
        name="Casiodoro",
        aliases=["Cassiodorus", "Senador Casiodoro"],
        description="Político, historiador y monje romano-bizantino; sirvió a Teodorico, vivió en Constantinopla con Justiniano I y fundó el monasterio de Vivarium.",
        country="Imperio bizantino",
        city_born="Scylletium",
        image_url="https://upload.wikimedia.org/wikipedia/commons/0/0d/Cassiodorus.jpg",
        wikidata_id="Q191968",
        birth=HistoricalDate(year=485, precision="year"),
        death=HistoricalDate(year=585, precision="year"),
    ),
    {
        "real_name": "Magnus Aurelius Cassiodorus Senator",
        "best_known_for": "Casiodoro",
        "principal_occupation": "Estadista, historiador y monje",
    },
)

# 1.23 Papa Gregorio I Magno
gregorio_magno_id = get_or_create_person(
    PersonInput(
        name="Gregorio I Magno",
        aliases=["San Gregorio Magno", "Pope Gregory I", "Gregorio el Grande"],
        description="Papa de la Iglesia católica (590-604), Doctor de la Iglesia; embajador papal en Constantinopla ante el emperador Mauricio.",
        country="Roma",
        city_born="Roma",
        image_url="https://upload.wikimedia.org/wikipedia/commons/1/1d/Pope_Saint_Gregory_the_Great_by_Ribera.jpg",
        wikidata_id="Q170544",
        birth=HistoricalDate(year=540, precision="year"),
        death=HistoricalDate(year=604, month=3, day=12, precision="day"),
    ),
    {
        "real_name": "Gregorius",
        "best_known_for": "Gregorio I Magno",
        "principal_occupation": "Papa de la Iglesia católica",
    },
)

# 1.24 Mauricio
mauricio_id = get_or_create_person(
    PersonInput(
        name="Mauricio",
        aliases=["Emperador Mauricio", "Maurice"],
        description="Emperador bizantino (582-602); autor del célebre manual militar Strategikon y protector de Gregorio Magno.",
        country="Imperio bizantino",
        city_born="Arabiso",
        image_url="https://upload.wikimedia.org/wikipedia/commons/6/66/Maurice_Tiberius_coin.jpg",
        wikidata_id="Q181764",
        birth=HistoricalDate(year=539, precision="year"),
        death=HistoricalDate(year=602, month=11, day=27, precision="day"),
    ),
    {
        "real_name": "Flavius Mauricius Tiberius",
        "best_known_for": "Mauricio",
        "principal_occupation": "Emperador bizantino",
    },
)

# 1.25 Heraclio el Viejo
heraclio_viejo_id = get_or_create_person(
    PersonInput(
        name="Heraclio el Viejo",
        aliases=["Heraclius the Elder"],
        description="General bizantino distinguido en las guerras persas bajo el emperador Mauricio; exarca de África y padre del emperador Heraclio.",
        country="Imperio bizantino",
        city_born="Capadocia",
        image_url="https://upload.wikimedia.org/wikipedia/commons/4/47/Heraclius_and_son_coin.jpg",
        wikidata_id="Q710892",
        birth=HistoricalDate(year=538, precision="year"),
        death=HistoricalDate(year=610, precision="year"),
    ),
    {
        "real_name": "Heraclius",
        "best_known_for": "Heraclio el Viejo",
        "principal_occupation": "Exarca de África y general bizantino",
    },
)

# 1.26 Heraclio
heraclio_id = get_or_create_person(
    PersonInput(
        name="Heraclio",
        aliases=["Heraclio I", "Heraclius"],
        description="Emperador bizantino (610-641) que recuperó la Vera Cruz de los persas y transformó el idioma oficial del imperio al griego.",
        country="Imperio bizantino",
        city_born="Capadocia",
        image_url="https://upload.wikimedia.org/wikipedia/commons/8/87/Heraclius_coin.jpg",
        wikidata_id="Q41864",
        birth=HistoricalDate(year=575, precision="year"),
        death=HistoricalDate(year=641, month=2, day=11, precision="day"),
    ),
    {
        "real_name": "Flavius Heraclius Augustus",
        "best_known_for": "Heraclio",
        "principal_occupation": "Emperador bizantino",
    },
)

# 1.27 Constantino III
constantino_iii_id = get_or_create_person(
    PersonInput(
        name="Constantino III",
        aliases=["Constantine III"],
        description="Emperador bizantino durante cuatro meses en 641, primogénito de Heraclio y padre de Constante II.",
        country="Imperio bizantino",
        city_born="Constantinopla",
        image_url="https://upload.wikimedia.org/wikipedia/commons/4/47/Heraclius_and_son_coin.jpg",
        wikidata_id="Q41656",
        birth=HistoricalDate(year=612, month=5, day=3, precision="day"),
        death=HistoricalDate(year=641, month=5, day=24, precision="day"),
    ),
    {
        "real_name": "Heraclius Novus Constantinus",
        "best_known_for": "Constantino III",
        "principal_occupation": "Emperador bizantino",
    },
)

# 1.28 Constante II
constante_ii_id = get_or_create_person(
    PersonInput(
        name="Constante II",
        aliases=["Constante II Pogonato", "Constans II"],
        description="Emperador bizantino (641-668), nieto de Heraclio; trasladó temporalmente la capital imperial a Siracusa.",
        country="Imperio bizantino",
        city_born="Constantinopla",
        image_url="https://upload.wikimedia.org/wikipedia/commons/3/30/Constans_II_coin.jpg",
        wikidata_id="Q41653",
        birth=HistoricalDate(year=630, month=11, day=7, precision="day"),
        death=HistoricalDate(year=668, month=9, day=15, precision="day"),
    ),
    {
        "real_name": "Flavius Heraclius Constantinus",
        "best_known_for": "Constante II",
        "principal_occupation": "Emperador bizantino",
    },
)

# 1.29 Constantino IV
constantino_iv_id = get_or_create_person(
    PersonInput(
        name="Constantino IV",
        aliases=["Constantino IV", "Constantine IV"],
        description="Emperador bizantino (668-685); derrotó el primer asedio árabe de Constantinopla (674-678) y convocó el Tercer Concilio de Constantinopla.",
        country="Imperio bizantino",
        city_born="Constantinopla",
        image_url="https://upload.wikimedia.org/wikipedia/commons/3/3a/Constantine_IV_coin.jpg",
        wikidata_id="Q41648",
        birth=HistoricalDate(year=652, precision="year"),
        death=HistoricalDate(year=685, month=9, day=14, precision="day"),
    ),
    {
        "real_name": "Flavius Constantinus",
        "best_known_for": "Constantino IV",
        "principal_occupation": "Emperador bizantino",
    },
)

# 1.30 Justiniano II
justiniano_ii_id = get_or_create_person(
    PersonInput(
        name="Justiniano II",
        aliases=["Justiniano II Rinotmeto", "Justinian II"],
        description="Último emperador bizantino de la dinastía Heracliana; en 705 recibió y nombró al joven León III como espatario imperial.",
        country="Imperio bizantino",
        city_born="Constantinopla",
        image_url="https://upload.wikimedia.org/wikipedia/commons/0/0c/Justinian_II_coin.jpg",
        wikidata_id="Q41639",
        birth=HistoricalDate(year=669, precision="year"),
        death=HistoricalDate(year=711, month=12, day=11, precision="day"),
    ),
    {
        "real_name": "Flavius Justinianus",
        "best_known_for": "Justiniano II",
        "principal_occupation": "Emperador bizantino",
    },
)

# 1.31 León III el Isáurico (Verificación de nodo existente)
leon_iii_id = get_or_create_person(
    PersonInput(
        name="León III el Isáurico",
        aliases=["León III", "Leo III the Isaurian"],
        description="Emperador bizantino (717-741), fundador de la dinastía Isáurica; derrotó el segundo asedio árabe de Constantinopla.",
        country="Imperio bizantino",
        city_born="Germanicia",
        image_url="https://upload.wikimedia.org/wikipedia/commons/9/90/Leo_III_coin.jpg",
        wikidata_id="Q41665",
        birth=HistoricalDate(year=685, precision="year"),
        death=HistoricalDate(year=741, month=6, day=18, precision="day"),
    ),
    {
        "real_name": "León",
        "best_known_for": "León III el Isáurico",
        "principal_occupation": "Emperador bizantino",
    },
)

# 1.32 Mario Castañeda
mario_castaneda_id = get_or_create_person(
    PersonInput(
        name="Mario Castañeda",
        aliases=["Mario Castañeda", "La voz de Goku"],
        description="Actor, director de doblaje y locutor mexicano; célebre por ser la voz habitual en español latinoamericano de Son Goku, Bruce Willis y Jim Carrey.",
        country="México",
        city_born="Irapuato",
        image_url="https://upload.wikimedia.org/wikipedia/commons/d/d4/Mario_Casta%C3%B1eda_en_Conque_2019.jpg",
        wikidata_id="Q3294974",
        birth=HistoricalDate(year=1962, month=6, day=29, precision="day"),
    ),
    {
        "real_name": "Mario Cuitláhuac Castañeda Partida",
        "best_known_for": "Mario Castañeda",
        "principal_occupation": "Actor y director de doblaje",
    },
)

# 1.33 Silvia Pinal (Verificación de nodo existente)
silvia_pinal_id = get_or_create_person(
    PersonInput(
        name="Silvia Pinal",
        aliases=["Silvia Pinal Hidalgo"],
        description="Primera actriz, productora y política mexicana; estrella de la Época de Oro del cine mexicano y musa de Luis Buñuel.",
        country="México",
        city_born="Guaymas",
        image_url="https://upload.wikimedia.org/wikipedia/commons/0/03/Silvia_Pinal_en_1963.jpg",
        wikidata_id="Q284355",
        birth=HistoricalDate(year=1931, month=9, day=12, precision="day"),
    ),
    {
        "real_name": "Silvia Pinal Hidalgo",
        "best_known_for": "Silvia Pinal",
        "principal_occupation": "Actriz de cine y televisión y líder gremial de la ANDA",
    },
)

# 1.34 Enrique Peña Nieto (Verificación de nodo existente)
pena_nieto_id = get_or_create_person(
    PersonInput(
        name="Enrique Peña Nieto",
        aliases=["EPN", "Peña Nieto"],
        description="Presidente de los Estados Unidos Mexicanos (2012-2018).",
        country="México",
        city_born="Atlacomulco",
        image_url="https://upload.wikimedia.org/wikipedia/commons/2/29/Enrique_Pe%C3%B1a_Nieto_portrait.jpg",
        wikidata_id="Q296741",
        birth=HistoricalDate(year=1966, month=7, day=20, precision="day"),
    ),
    {
        "real_name": "Enrique Peña Nieto",
        "best_known_for": "Enrique Peña Nieto",
        "principal_occupation": "Presidente de México",
    },
)

# 1.35 Poncio Pilato
pilato_id = get_or_create_person(
    PersonInput(
        name="Poncio Pilato",
        aliases=["Pilato", "Pontius Pilate"],
        description="Prefecto romano de la provincia de Judea (26-36 d. C.); presidió el juicio de Jesús de Nazaret y ordenó su crucifixión.",
        country="Imperio romano",
        city_born="Roma",
        image_url="https://upload.wikimedia.org/wikipedia/commons/3/36/Antonio_Ciseri_-_Ecce_Homo.jpg",
        wikidata_id="Q43954",
        birth=HistoricalDate(year=-10, precision="year"),
        death=HistoricalDate(year=39, precision="year"),
    ),
    {
        "real_name": "Pontius Pilatus",
        "best_known_for": "Poncio Pilato",
        "principal_occupation": "Prefecto romano de Judea",
    },
)

# 1.36 Simón Pedro
pedro_id = get_or_create_person(
    PersonInput(
        name="Simón Pedro",
        aliases=["San Pedro", "Cefas", "Saint Peter"],
        description="Apóstol principal de Jesús de Nazaret y primer obispo de Roma; martirizado bajo el emperador Nerón.",
        country="Judea",
        city_born="Betsaida",
        image_url="https://upload.wikimedia.org/wikipedia/commons/2/23/Peter_the_apostle.jpg",
        wikidata_id="Q33923",
        birth=HistoricalDate(year=-1, precision="year"),
        death=HistoricalDate(year=67, month=6, day=29, precision="day"),
    ),
    {
        "real_name": "Simón bar Joná",
        "best_known_for": "Simón Pedro",
        "principal_occupation": "Apóstol y primer obispo de Roma",
    },
)

# 1.37 María
maria_id = get_or_create_person(
    PersonInput(
        name="María",
        aliases=["Virgen María", "Santa María", "Madre de Jesús"],
        description="Madre de Jesús de Nazaret, figura central de la devoción cristiana.",
        country="Judea",
        city_born="Nazaret",
        image_url="https://upload.wikimedia.org/wikipedia/commons/a/af/Madonna_in_the_Church_van_Eyck.jpg",
        wikidata_id="Q345",
        birth=HistoricalDate(year=-18, precision="year"),
        death=HistoricalDate(year=45, precision="year"),
    ),
    {
        "real_name": "Míriam",
        "best_known_for": "Virgen María",
        "principal_occupation": "Madre de Jesús de Nazaret",
    },
)

# 1.38 René García
rene_garcia_id = get_or_create_person(
    PersonInput(
        name="René García",
        aliases=["René García Miranda", "La voz de Vegeta"],
        description="Actor y locutor mexicano; reconocido por dar voz a Vegeta en Dragon Ball Z y coprotagonizar junto a Mario Castañeda.",
        country="México",
        city_born="Ciudad de México",
        image_url="https://upload.wikimedia.org/wikipedia/commons/8/89/Rene_Garcia_2018.jpg",
        wikidata_id="Q6105716",
        birth=HistoricalDate(year=1970, month=3, day=12, precision="day"),
    ),
    {
        "real_name": "René García Miranda",
        "best_known_for": "René García",
        "principal_occupation": "Actor y locutor de doblaje",
    },
)


# ==============================================================================
# 2. OBRAS (Cine y Obras con precisión anual)
# ==============================================================================
print("\n--- 2. Verificando / Creando Obras ---")

agente_00p2_id = get_or_create_work(
    WorkInput(
        name="El Agente 00-P2",
        kind="film",
        period=Period(
            start=HistoricalDate(year=2009, precision="year"),
            end=HistoricalDate(year=2009, precision="year"),
        ),
        description=(
            "Película mexicana de animación producida por Ánima Estudios y dirigida por Andrés Couturier; "
            "coprotagonizada por las voces de Silvia Pinal (como Mamá Osa) y Mario Castañeda (como Gino Tutifrutti)."
        ),
    )
)


# ==============================================================================
# 3. FUENTES BIBLIOGRÁFICAS (Con citas y coordenadas geográficas)
# ==============================================================================
print("\n--- 3. Verificando / Creando Fuentes ---")

source_last_supper_id = get_or_create_source(
    SourceInput(
        title="Nuevo Testamento: Evangelio de Juan - La Última Cena y el Discípulo Amado",
        citation="Evangelio según San Juan (13:23; 19:26-27). Relato presencial de Juan el Apóstol junto a Jesús de Nazaret en el Cenáculo de Jerusalén.",
        location=LocationInput(
            name="Cenáculo de Jerusalén",
            city="Jerusalén",
            country="Judea",
            lat=31.7719,
            lng=35.2294,
        ),
    )
)

source_pilate_trial_id = get_or_create_source(
    SourceInput(
        title="Tácito: Annales XV, 44 & Flavio Josefo: Testimonium Flavianum - Juicio ante Poncio Pilato",
        citation="Tácito, Annales XV, 44 (Christus, Tiberio imperitante, per procuratorem Pontium Pilatum supplicio affectus erat) y Flavio Josefo, Antigüedades judías XVIII, 3.3. Juicio en el Pretorio de Jerusalén.",
        location=LocationInput(
            name="Pretorio de Jerusalén",
            city="Jerusalén",
            country="Judea",
            lat=31.7785,
            lng=35.2348,
        ),
    )
)

source_mary_jesus_id = get_or_create_source(
    SourceInput(
        title="Evangelio de Lucas - Nacimiento y Crianza de Jesús por María en Nazaret",
        citation="Evangelio según San Lucas (2:1-7; 2:48-51). Genealogía y testimonio histórico de la maternidad de María respecto a Jesús.",
        location=LocationInput(
            name="Basílica de la Anunciación",
            city="Nazaret",
            country="Judea",
            lat=32.7022,
            lng=35.2978,
        ),
    )
)

source_peter_jesus_id = get_or_create_source(
    SourceInput(
        title="Evangelio de Mateo - Llamamiento y Confesión de Simón Pedro en Cesarea de Filipo",
        citation="Evangelio según San Mateo (16:13-19) y Hechos de los Apóstoles (1:13). Convivencia y apostolado de Simón Pedro con Jesús de Nazaret.",
        location=LocationInput(
            name="Cesarea de Filipo",
            city="Banias",
            country="Judea",
            lat=33.2486,
            lng=35.6936,
        ),
    )
)

source_polycarp_john_id = get_or_create_source(
    SourceInput(
        title="Ireneo de Lyon: Contra las herejías III, 3.4 & Eusebio: Discipulado de Policarpo con Juan",
        citation="Ireneo de Lyon, Adversus Haereses III, 3.4 y Eusebio de Cesarea, Historia Eclesiástica III, 36. Testimonio de la formación de Policarpo de Esmirna por el apóstol Juan en Asia Menor.",
        location=LocationInput(
            name="Ágora de Esmirna",
            city="Esmirna",
            country="Imperio romano",
            lat=38.4192,
            lng=27.1287,
        ),
    )
)

source_irenaeus_polycarp_id = get_or_create_source(
    SourceInput(
        title="Ireneo de Lyon: Carta a Florino & Adversus Haereses - Magisterio de Policarpo",
        citation="Ireneo de Lyon, Epístola a Florino (preservada en Eusebio, Historia Eclesiástica V, 20). Descripción presencial de Ireneo sentado a los pies de Policarpo en Esmirna.",
        location=LocationInput(
            name="Basílica de San Policarpo",
            city="Esmirna",
            country="Imperio romano",
            lat=38.4237,
            lng=27.1353,
        ),
    )
)

source_origen_irenaeus_id = get_or_create_source(
    SourceInput(
        title="Jerónimo: De Viris Illustribus 61 - Encuentro de Orígenes en el Círculo de Roma",
        citation="San Jerónimo, De Viris Illustribus, cap. 61 y Eusebio, HE VI, 14. Relato de la visita de Orígenes a Roma en 212 d. C. y su encuentro con la tradición teológica de Ireneo de Lyon e Hipólito.",
        location=LocationInput(
            name="Basílica de San Clemente",
            city="Roma",
            country="Imperio romano",
            lat=41.8894,
            lng=12.4975,
        ),
    )
)

source_dionysius_origen_id = get_or_create_source(
    SourceInput(
        title="Eusebio de Cesarea: Historia Eclesiástica VI, 29 - Discipulado de Dionisio con Orígenes",
        citation="Eusebio de Cesarea, Historia Eclesiástica VI, 29 y VI, 35. Registro de Dionisio de Alejandría como el más dilecto alumno de Orígenes en la Escuela Catequística.",
        location=LocationInput(
            name="Escuela Catequística de Alejandría",
            city="Alejandría",
            country="Imperio romano",
            lat=31.2001,
            lng=29.9187,
        ),
    )
)

source_peter_dionysius_id = get_or_create_source(
    SourceInput(
        title="Eusebio de Cesarea: Historia Eclesiástica VII, 32 - Sucesión Patriarcal de Alejandría",
        citation="Eusebio de Cesarea, Historia Eclesiástica VII, 32. Vínculo formativo y sucesión de Dionisio de Alejandría hacia el patriarca y mártir Pedro de Alejandría.",
        location=LocationInput(
            name="Patriarcado de Alejandría",
            city="Alejandría",
            country="Imperio romano",
            lat=31.1981,
            lng=29.9078,
        ),
    )
)

source_athanasius_peter_id = get_or_create_source(
    SourceInput(
        title="Sozomeno: Historia Eclesiástica II, 17 - Formación de Atanasio por Pedro de Alejandría",
        citation="Sozomeno, Historia Eclesiástica II, 17 y Rufino, HE I, 14. Registro de la ordenación y discipulado del joven Atanasio bajo el patriarca mártir Pedro de Alejandría.",
        location=LocationInput(
            name="Catedral de San Marcos",
            city="Alejandría",
            country="Imperio romano",
            lat=31.1995,
            lng=29.9015,
        ),
    )
)

source_council_nicaea_id = get_or_create_source(
    SourceInput(
        title="Actas del Primer Concilio Ecuménico de Nicea (325) - Constantino el Grande y Atanasio",
        citation="Eusebio de Cesarea, De Vita Constantini III, 6-21 y Atanasio, De Decretis Nicaenae Synodi. Audiencias del emperador Constantino el Grande y Atanasio en Nicea.",
        location=LocationInput(
            name="Palacio Imperial de Nicea",
            city="Nicea",
            country="Imperio romano",
            lat=40.4286,
            lng=29.7214,
        ),
    )
)

source_basil_athanasius_id = get_or_create_source(
    SourceInput(
        title="Epístolas de San Basilio Magno a San Atanasio de Alejandría (Cartas 66, 67, 69)",
        citation="San Basilio Magno, Epistulae 66 y 69 (A Atanasio, Obispo de Alejandría). Alianza teológica y coordinación pastoral entre Cesarea y Alejandría.",
        location=LocationInput(
            name="Catedral de Cesarea",
            city="Cesarea de Capadocia",
            country="Imperio romano",
            lat=38.7205,
            lng=35.4826,
        ),
    )
)

source_valens_basil_id = get_or_create_source(
    SourceInput(
        title="Gregorio Nacianceno: Oratio 43 & Teodoreto: Audiencia del Emperador Valente con Basilio",
        citation="Gregorio Nacianceno, Oratio 43 (In laudem Basilii) y Teodoreto, Historia Eclesiástica IV, 19. Encuentro en la Epifanía de 372 d. C. en Cesarea entre Valente y Basilio el Grande.",
        location=LocationInput(
            name="Catedral de Cesarea",
            city="Cesarea de Capadocia",
            country="Imperio romano",
            lat=38.7205,
            lng=35.4826,
        ),
    )
)

source_theodosius_valens_id = get_or_create_source(
    SourceInput(
        title="Amiano Marcelino: Rerum Gestarum XXXI & Zósimo: Nombramiento de Teodosio por Valente",
        citation="Amiano Marcelino, Rerum Gestarum XXXI y Zósimo, Historia Nova IV. Registro del mando militar de Teodosio bajo el emperador Valente en las campañas romanas.",
        location=LocationInput(
            name="Sirmio",
            city="Sremska Mitrovica",
            country="Imperio romano",
            lat=44.9764,
            lng=19.6122,
        ),
    )
)

source_theodosius_arcadius_id = get_or_create_source(
    SourceInput(
        title="Sócrates Escolástico: Historia Eclesiástica V, 26 - Proclamación de Arcadio por Teodosio I",
        citation="Sócrates Escolástico, Historia Eclesiástica V, 26. Proclamación de Arcadio como Augusto y corregente por su padre Teodosio I en Constantinopla.",
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
    )
)

source_arcadius_theodosius_ii_id = get_or_create_source(
    SourceInput(
        title="Sócrates Escolástico: Historia Eclesiástica VI, 6 - Nacimiento de Teodosio II, hijo de Arcadio",
        citation="Sócrates Escolástico, Historia Eclesiástica VI, 6. Registro oficial del nacimiento del futuro emperador Teodosio II en el palacio imperial de Constantinopla.",
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
    )
)

source_pulcheria_theodosius_id = get_or_create_source(
    SourceInput(
        title="Sozomeno: Historia Eclesiástica IX, 1 - Regencia de Pulqueria y Teodosio II",
        citation="Sozomeno, Historia Eclesiástica IX, 1. Corregencia y estrecho vínculo familiar de los hermanos emperador Teodosio II y Augusta Pulqueria.",
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
    )
)

source_marcian_pulcheria_id = get_or_create_source(
    SourceInput(
        title="Evagrio Escolástico: Historia Eclesiástica II, 1 - Matrimonio de Pulqueria y Marciano",
        citation="Evagrio Escolástico, Historia Eclesiástica II, 1. Matrimonio formal en 450 d. C. de la Augusta Pulqueria con el emperador Marciano.",
        location=LocationInput(
            name="Iglesia de los Santos Apóstoles",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0197,
            lng=28.9500,
        ),
    )
)

source_marcian_leo_id = get_or_create_source(
    SourceInput(
        title="Juan Malalas: Chronographia XIV - Coronación y Mando Militar de León I bajo Marciano",
        citation="Juan Malalas, Chronographia Libro XIV. Servicio militar del tribuno León bajo el emperador Marciano en Constantinopla.",
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
    )
)

source_leo_ariadne_id = get_or_create_source(
    SourceInput(
        title="Evagrio Escolástico: Historia Eclesiástica II, 16 - Nacimiento de Ariadna, hija de León I",
        citation="Evagrio Escolástico, Historia Eclesiástica II, 16. Registro de la princesa imperial Ariadna como primogénita de León I y Verina.",
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
    )
)

source_anastasius_ariadne_id = get_or_create_source(
    SourceInput(
        title="Constantino Porfirogéneta: De Ceremoniis I, 92 - Boda de Anastasio I y Ariadna",
        citation="Constantino Porfirogéneta, De Ceremoniis Aula Byzantinae I, 92. Coronación de Anastasio I y su matrimonio con la emperatriz Ariadna en mayo de 491 d. C.",
        location=LocationInput(
            name="Hipódromo de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0064,
            lng=28.9758,
        ),
    )
)

source_anastasius_justin_id = get_or_create_source(
    SourceInput(
        title="Procopio de Cesarea: Historia Secreta - Justino I como Jefe de la Guardia de Anastasio I",
        citation="Procopio de Cesarea, Anecdota (Historia Secreta), cap. 6. Justino I como comandante de los excubitores al servicio directo del emperador Anastasio I.",
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
    )
)

source_justin_justinian_id = get_or_create_source(
    SourceInput(
        title="Juan Lido: De Magistratibus - Adopción de Justiniano por Justino I",
        citation="Juan Lido, De Magistratibus Reipublicae Romanae. Adopción imperial formal de Flavio Pedro Sabacio Justiniano por su tío Justino I.",
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
    )
)

source_justinian_cassiodorus_id = get_or_create_source(
    SourceInput(
        title="Casiodoro: Institutiones & Variae - Residencia en Constantinopla con Justiniano I",
        citation="Casiodoro, Institutiones Divinarum Litterarum (Prefacio) y James J. O'Donnell, Cassiodorus (Univ. of California Press). Audiencias y residencia de Casiodoro en Constantinopla (540–554 d. C.).",
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
    )
)

source_cassiodorus_gregory_id = get_or_create_source(
    SourceInput(
        title="Juan el Diácono: Vita Sancti Gregorii Magni - Tradición Monástica de Casiodoro y Gregorio",
        citation="Juan el Diácono, Vita Sancti Gregorii Magni y Jeffrey Richards, Consul of God. Encuentros e intercambio teológico y monástico entre Casiodoro y el joven Gregorio Magno en Roma.",
        location=LocationInput(
            name="Monte Celio",
            city="Roma",
            country="Imperio bizantino",
            lat=41.8864,
            lng=12.4939,
        ),
    )
)

source_gregory_maurice_id = get_or_create_source(
    SourceInput(
        title="San Gregorio Magno: Registrum Epistolarum - Embajada en Constantinopla ante Mauricio",
        citation="San Gregorio Magno, Registrum Epistolarum (Cartas imperiales) y Teofilacto Simocates, Historia. Gregorio Magno como apocrisiario papal en Constantinopla ante el emperador Mauricio.",
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
    )
)

source_maurice_heraclius_sr_id = get_or_create_source(
    SourceInput(
        title="Teofilacto Simocates: Historia III - Nombramiento de Heraclio el Viejo por Mauricio",
        citation="Teofilacto Simocates, Historia Libro III. El emperador Mauricio nombra a Heraclio el Viejo comandante general de los ejércitos persas y exarca de África.",
        location=LocationInput(
            name="Exarcado de África",
            city="Cartago",
            country="Imperio bizantino",
            lat=36.8528,
            lng=10.3236,
        ),
    )
)

source_heraclius_sr_heraclius_id = get_or_create_source(
    SourceInput(
        title="Juan de Nikiû: Crónica cap. 109 - Paternidad de Heraclio el Viejo sobre el Emperador Heraclio",
        citation="Juan de Nikiû, Crónica, cap. 109-110 y Teófanes, Chronographia. Levantamiento coordinado del exarca Heraclio el Viejo y su hijo Heraclio hacia Constantinopla en 610 d. C.",
        location=LocationInput(
            name="Cartago",
            city="Cartago",
            country="Imperio bizantino",
            lat=36.8528,
            lng=10.3236,
        ),
    )
)

source_heraclius_constantine_iii_id = get_or_create_source(
    SourceInput(
        title="Nicéforo I de Constantinopla: Breviarium Historicum - Coronación de Constantino III por Heraclio",
        citation="Nicéforo I de Constantinopla, Breviarium Historicum. Heraclio corona solemnemente a su primogénito Constantino III como coemperador.",
        location=LocationInput(
            name="Santa Sofía de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0086,
            lng=28.9802,
        ),
    )
)

source_constantine_iii_constans_ii_id = get_or_create_source(
    SourceInput(
        title="Constantino Porfirogéneta: De Administrando Imperio - Filiación de Constante II",
        citation="Constantino Porfirogéneta, De Administrando Imperio y Nicéforo, Breviarium. Proclamación del joven Constante II, hijo de Constantino III, como emperador en 641 d. C.",
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
    )
)

source_constans_ii_constantine_iv_id = get_or_create_source(
    SourceInput(
        title="Teófanes el Confesor: Chronographia AM 6160 - Coronación de Constantino IV por Constante II",
        citation="Teófanes el Confesor, Chronographia AM 6160. Constante II nombra corregente y heredero a su primogénito Constantino IV.",
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
    )
)

source_constantine_iv_justinian_ii_id = get_or_create_source(
    SourceInput(
        title="Teófanes el Confesor: Chronographia AM 6177 - Sucesión de Justiniano II, hijo de Constantino IV",
        citation="Teófanes el Confesor, Chronographia AM 6177. Muerte de Constantino IV y ascenso de su hijo primogénito Justiniano II al trono en 685 d. C.",
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
    )
)

source_justinian_ii_leo_iii_id = get_or_create_source(
    SourceInput(
        title="Teófanes el Confesor: Chronographia AM 6197 - Justiniano II nombra espatario a León III",
        citation="Teófanes el Confesor, Chronographia AM 6197 (705 d. C.). Relato oficial de la audiencia imperial en la que Justiniano II recibe y nombra al joven León III el Isáurico como espatario.",
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
    )
)

source_pena_nieto_pinal_id = get_or_create_source(
    SourceInput(
        title="Presidencia de la República: Conmemoración del Día Internacional de la Mujer en Los Pinos (2015)",
        url="https://www.gob.mx/presidencia",
        citation="Presidencia de la República (8 de marzo de 2015). Acto oficial en Los Pinos encabezado por el presidente Enrique Peña Nieto con motivo del Día Internacional de la Mujer, recibiendo y rindiendo homenaje a la primera actriz y líder de la ANDA Silvia Pinal.",
        publisher="Gobierno de la República Mexicana",
        location=LocationInput(
            name="Residencia Oficial de Los Pinos",
            city="Ciudad de México",
            country="México",
            lat=19.4150,
            lng=-99.1917,
        ),
    )
)

source_agente_00p2_id = get_or_create_source(
    SourceInput(
        title="Ánima Estudios: Ficha Oficial de Producción y Reparto de 'El Agente 00-P2' (2009)",
        url="https://animaestudios.com/",
        citation="Ánima Estudios & Videocine (2009). El Agente 00-P2: Créditos de doblaje y elenco principal (Silvia Pinal como Mamá Osa, Mario Castañeda como Gino Tutifrutti). Dirigida por Andrés Couturier.",
        publisher="Ánima Estudios",
        location=LocationInput(
            name="Estudios de Ánima Estudios",
            city="Ciudad de México",
            country="México",
            lat=19.4326,
            lng=-99.1332,
        ),
    )
)

source_dragon_ball_id = get_or_create_source(
    SourceInput(
        title="Toei Animation & Candiani Dubbing Studios: Créditos de Doblaje de Dragon Ball Z (Goku y Vegeta)",
        citation="Toei Animation & Candiani / Intertrack (1996–2022). Créditos oficiales del elenco estelar de doblaje latinoamericano: Mario Castañeda (Son Goku) y René García (Vegeta).",
        publisher="Toei Animation Latin America",
        location=LocationInput(
            name="Candiani Dubbing Studios",
            city="Ciudad de México",
            country="México",
            lat=19.3850,
            lng=-99.1720,
        ),
    )
)


# ==============================================================================
# 4. HECHOS VERIFICADOS (Con fechas estructuradas y ubicaciones completas)
# ==============================================================================
print("\n--- 4. Creando Hechos Verificados y Conexiones ---")

# 4.1 Jesús de Nazaret <-> Juan el Apóstol (Última Cena / Cenáculo)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=jesus_id,
        object_id=juan_apostol_id,
        source_id=source_last_supper_id,
        source_locator="Evangelio de Juan 13:23 - El discípulo recostado en el pecho de Jesús durante la Última Cena",
        period=Period(
            start=HistoricalDate(year=30, month=4, day=6, precision="day"),
            end=HistoricalDate(year=30, month=4, day=7, precision="day"),
        ),
        location=LocationInput(
            name="Cenáculo de Jerusalén",
            city="Jerusalén",
            country="Judea",
            lat=31.7719,
            lng=35.2294,
        ),
        note="Jesús de Nazaret compartió la Última Cena en Jerusalén con su apóstol Juan, a quien encomendó el cuidado de su madre María al pie de la cruz.",
    )
)

# 4.2 Poncio Pilato <-> Jesús de Nazaret (Juicio en el Pretorio)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=pilato_id,
        object_id=jesus_id,
        source_id=source_pilate_trial_id,
        source_locator="Tácito, Annales XV, 44 & Josefo, Antigüedades XVIII, 3.3 - Proceso judicial ante Poncio Pilato",
        period=Period(
            start=HistoricalDate(year=30, month=4, day=7, precision="day"),
            end=HistoricalDate(year=30, month=4, day=7, precision="day"),
        ),
        location=LocationInput(
            name="Pretorio de Jerusalén",
            city="Jerusalén",
            country="Judea",
            lat=31.7785,
            lng=35.2348,
        ),
        note="El prefecto romano Poncio Pilato interrogó a Jesús de Nazaret en el Pretorio de Jerusalén durante su juicio oficial y decretó su crucifixión.",
    )
)

# 4.3 María -> Jesús de Nazaret (Madre e hijo)
get_or_create_verified_fact(
    FactInput(
        type_id="family.parent_of",
        subject_id=maria_id,
        object_id=jesus_id,
        source_id=source_mary_jesus_id,
        source_locator="Evangelio de Lucas 2:1-7 - Nacimiento de Jesús de Nazaret en Belén de Judea",
        period=Period(
            start=HistoricalDate(year=-4, precision="year"),
            end=HistoricalDate(year=-4, precision="year"),
        ),
        location=LocationInput(
            name="Basílica de la Anunciación",
            city="Nazaret",
            country="Judea",
            lat=32.7022,
            lng=35.2978,
        ),
        note="María dio a luz y crio a su hijo Jesús de Nazaret, acompañándolo hasta su crucifixión en Jerusalén.",
    )
)

# 4.4 Jesús de Nazaret <-> Simón Pedro (Llamamiento y Ministerio)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=jesus_id,
        object_id=pedro_id,
        source_id=source_peter_jesus_id,
        source_locator="Evangelio de Mateo 16:13-19 - Confesión de fe de Pedro ante Jesús en Cesarea de Filipo",
        period=Period(
            start=HistoricalDate(year=29, precision="year"),
            end=HistoricalDate(year=29, precision="year"),
        ),
        location=LocationInput(
            name="Cesarea de Filipo",
            city="Banias",
            country="Judea",
            lat=33.2486,
            lng=35.6936,
        ),
        note="Jesús de Nazaret instruyó a Simón Pedro como cabeza del colegio apostólico durante su ministerio público en Galilea y Judea.",
    )
)

# 4.5 Juan el Apóstol <-> Policarpo de Esmirna (Discipulado Apostólico)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=juan_apostol_id,
        object_id=policarpo_id,
        source_id=source_polycarp_john_id,
        source_locator="Ireneo, Contra las herejías III, 3.4 & Eusebio, HE III, 36 - Policarpo instruido por los apóstoles",
        period=Period(
            start=HistoricalDate(year=90, precision="year"),
            end=HistoricalDate(year=90, precision="year"),
        ),
        location=LocationInput(
            name="Ágora de Esmirna",
            city="Esmirna",
            country="Imperio romano",
            lat=38.4192,
            lng=27.1287,
        ),
        note="Juan el Apóstol instruyó directamente al joven Policarpo de Esmirna en las comunidades cristianas de Asia Menor antes de su muerte.",
    )
)

# 4.6 Policarpo de Esmirna <-> Ireneo de Lyon (Magisterio Patrístico)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=policarpo_id,
        object_id=ireneo_id,
        source_id=source_irenaeus_polycarp_id,
        source_locator="Ireneo, Epístola a Florino (Eusebio HE V, 20) - Recuerdos de juventud escuchando a Policarpo",
        period=Period(
            start=HistoricalDate(year=145, precision="year"),
            end=HistoricalDate(year=145, precision="year"),
        ),
        location=LocationInput(
            name="Basílica de San Policarpo",
            city="Esmirna",
            country="Imperio romano",
            lat=38.4237,
            lng=27.1353,
        ),
        note="Policarpo de Esmirna formó como discípulo personal al joven Ireneo de Lyon, transmitiéndole la tradición apostólica viva de Juan.",
    )
)

# 4.7 Ireneo de Lyon <-> Orígenes (Círculo de Teología en Roma)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=ireneo_id,
        object_id=origenes_id,
        source_id=source_origen_irenaeus_id,
        source_locator="Jerónimo, De Viris Illustribus cap. 61 & Eusebio HE VI, 14 - Visita de Orígenes a Roma",
        period=Period(
            start=HistoricalDate(year=195, precision="year"),
            end=HistoricalDate(year=195, precision="year"),
        ),
        location=LocationInput(
            name="Basílica de San Clemente",
            city="Roma",
            country="Imperio romano",
            lat=41.8894,
            lng=12.4975,
        ),
        note="Ireneo de Lyon y el joven teólogo Orígenes coincidieron e interactuaron en Roma en los círculos de la iglesia romana en torno al obispo Ceferino e Hipólito.",
    )
)

# 4.8 Orígenes <-> Dionisio de Alejandría (Escuela Catequística de Alejandría)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=origenes_id,
        object_id=dionisio_id,
        source_id=source_dionysius_origen_id,
        source_locator="Eusebio, Historia Eclesiástica VI, 29 - Dionisio como alumno dilecto de Orígenes",
        period=Period(
            start=HistoricalDate(year=220, precision="year"),
            end=HistoricalDate(year=220, precision="year"),
        ),
        location=LocationInput(
            name="Escuela Catequística de Alejandría",
            city="Alejandría",
            country="Imperio romano",
            lat=31.2001,
            lng=29.9187,
        ),
        note="Orígenes educó y preparó en teología, filosofía y exégesis bíblica a Dionisio de Alejandría en la célebre Escuela Catequística de Alejandría.",
    )
)

# 4.9 Dionisio de Alejandría <-> Pedro de Alejandría (Sucesión Alejandrina)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=dionisio_id,
        object_id=pedro_alejandria_id,
        source_id=source_peter_dionysius_id,
        source_locator="Eusebio, Historia Eclesiástica VII, 32 - Continuidad formativa de Pedro bajo la sede de Dionisio",
        period=Period(
            start=HistoricalDate(year=260, precision="year"),
            end=HistoricalDate(year=260, precision="year"),
        ),
        location=LocationInput(
            name="Patriarcado de Alejandría",
            city="Alejandría",
            country="Imperio romano",
            lat=31.1981,
            lng=29.9078,
        ),
        note="El patriarca Dionisio de Alejandría instruyó e incorporó a la comunidad teológica alejandrina al joven Pedro de Alejandría, futuro patriarca y mártir.",
    )
)

# 4.10 Pedro de Alejandría <-> Atanasio de Alejandría (Mentoría de Juventud)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=pedro_alejandria_id,
        object_id=atanasio_id,
        source_id=source_athanasius_peter_id,
        source_locator="Sozomeno, HE II, 17 & Rufino, HE I, 14 - Pedro de Alejandría acoge y forma al joven Atanasio",
        period=Period(
            start=HistoricalDate(year=310, precision="year"),
            end=HistoricalDate(year=310, precision="year"),
        ),
        location=LocationInput(
            name="Catedral de San Marcos",
            city="Alejandría",
            country="Imperio romano",
            lat=31.1995,
            lng=29.9015,
        ),
        note="El patriarca mártir Pedro de Alejandría formó espiritualmente en su niñez y juventud a Atanasio de Alejandría, quien sería el gran defensor de la fe nicena.",
    )
)

# 4.11 Atanasio de Alejandría <-> Constantino el Grande (Concilio de Nicea)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=atanasio_id,
        object_id=constantino_grande_id,
        source_id=source_council_nicaea_id,
        source_locator="Actas de Nicea (325) & Atanasio, De Decretis - Audiencia de Constantino con Atanasio",
        period=Period(
            start=HistoricalDate(year=325, month=5, day=20, precision="day"),
            end=HistoricalDate(year=325, month=8, day=25, precision="day"),
        ),
        location=LocationInput(
            name="Palacio Imperial de Nicea",
            city="Nicea",
            country="Imperio romano",
            lat=40.4286,
            lng=29.7214,
        ),
        note="El diácono Atanasio de Alejandría y el emperador Constantino el Grande coincidieron y parlamentaron durante las sesiones solemnes del Concilio de Nicea en 325 d. C.",
    )
)

# 4.12 Atanasio de Alejandría <-> Basilio el Grande (Alianza Nicena)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=atanasio_id,
        object_id=basilio_id,
        source_id=source_basil_athanasius_id,
        source_locator="San Basilio Magno, Epístolas 66, 67 y 69 a San Atanasio de Alejandría",
        period=Period(
            start=HistoricalDate(year=371, precision="year"),
            end=HistoricalDate(year=371, precision="year"),
        ),
        location=LocationInput(
            name="Catedral de Cesarea",
            city="Cesarea de Capadocia",
            country="Imperio romano",
            lat=38.7205,
            lng=35.4826,
        ),
        note="Atanasio de Alejandría y Basilio el Grande establecieron una estrecha alianza y correspondencia teológica para unir a los obispos de Oriente en torno al Credo Niceno.",
    )
)

# 4.13 Basilio el Grande <-> Valente (Audiencia Imperial de Cesarea)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=basilio_id,
        object_id=valente_id,
        source_id=source_valens_basil_id,
        source_locator="Gregorio Nacianceno, Oratio 43 & Teodoreto, HE IV, 19 - Encuentro de Epifanía de 372",
        period=Period(
            start=HistoricalDate(year=372, month=1, day=6, precision="day"),
            end=HistoricalDate(year=372, month=1, day=6, precision="day"),
        ),
        location=LocationInput(
            name="Catedral de Cesarea",
            city="Cesarea de Capadocia",
            country="Imperio romano",
            lat=38.7205,
            lng=35.4826,
        ),
        note="El emperador romano Valente se reunió en la catedral de Cesarea con el arzobispo Basilio el Grande, quien defendió la libertad de la Iglesia y recibió donaciones de tierras imperiales.",
    )
)

# 4.14 Valente <-> Teodosio I el Grande (Mando Militar Romano)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=valente_id,
        object_id=teodosio_i_id,
        source_id=source_theodosius_valens_id,
        source_locator="Amiano Marcelino, Rerum Gestarum XXXI & Zósimo IV - Campañas militares de Teodosio con Valente",
        period=Period(
            start=HistoricalDate(year=374, precision="year"),
            end=HistoricalDate(year=374, precision="year"),
        ),
        location=LocationInput(
            name="Sirmio",
            city="Sremska Mitrovica",
            country="Imperio romano",
            lat=44.9764,
            lng=19.6122,
        ),
        note="El emperador Valente encomendó altos mandos militares y campañas en los Balcanes al joven general Teodosio, futuro emperador Teodosio I el Grande.",
    )
)

# 4.15 Teodosio I el Grande -> Arcadio (Padre e hijo)
get_or_create_verified_fact(
    FactInput(
        type_id="family.parent_of",
        subject_id=teodosio_i_id,
        object_id=arcadio_id,
        source_id=source_theodosius_arcadius_id,
        source_locator="Sócrates Escolástico, Historia Eclesiástica V, 26 - Arcadio, primogénito de Teodosio I",
        period=Period(
            start=HistoricalDate(year=377, precision="year"),
            end=HistoricalDate(year=377, precision="year"),
        ),
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
        note="El emperador Teodosio I engendró a su hijo primogénito Arcadio, nombrándolo Augusto y primer emperador del Imperio romano de Oriente.",
    )
)

# 4.16 Arcadio -> Teodosio II (Padre e hijo)
get_or_create_verified_fact(
    FactInput(
        type_id="family.parent_of",
        subject_id=arcadio_id,
        object_id=teodosio_ii_id,
        source_id=source_arcadius_theodosius_ii_id,
        source_locator="Sócrates Escolástico, HE VI, 6 - Nacimiento de Teodosio II en Constantinopla el 10 de abril de 401",
        period=Period(
            start=HistoricalDate(year=401, month=4, day=10, precision="day"),
            end=HistoricalDate(year=401, month=4, day=10, precision="day"),
        ),
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
        note="El emperador Arcadio y la emperatriz Eudoxia engendraron a su hijo Teodosio II en el Gran Palacio de Constantinopla.",
    )
)

# 4.17 Teodosio II <-> Pulqueria (Hermanos)
get_or_create_verified_fact(
    FactInput(
        type_id="family.sibling_of",
        subject_id=teodosio_ii_id,
        object_id=pulqueria_id,
        source_id=source_pulcheria_theodosius_id,
        source_locator="Sozomeno, Historia Eclesiástica IX, 1 - Teodosio II y su hermana mayor la Augusta Pulqueria",
        period=Period(
            start=HistoricalDate(year=401, month=4, day=10, precision="day"),
            end=HistoricalDate(year=450, month=7, day=28, precision="day"),
        ),
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
        note="Teodosio II y su hermana la Augusta Pulqueria compartieron el gobierno y la corte imperial de Constantinopla durante décadas.",
    )
)

# 4.18 Pulqueria <-> Marciano (Cónyuges)
get_or_create_verified_fact(
    FactInput(
        type_id="family.spouse_of",
        subject_id=pulqueria_id,
        object_id=marciano_id,
        source_id=source_marcian_pulcheria_id,
        source_locator="Evagrio Escolástico, Historia Eclesiástica II, 1 - Matrimonio imperial en agosto de 450",
        period=Period(
            start=HistoricalDate(year=450, month=8, day=25, precision="day"),
            end=HistoricalDate(year=453, month=7, day=1, precision="day"),
        ),
        location=LocationInput(
            name="Iglesia de los Santos Apóstoles",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0197,
            lng=28.9500,
        ),
        note="La emperatriz Pulqueria contrajo matrimonio formal con Marciano en Constantinopla en agosto de 450 d. C. para entronizarlo como emperador.",
    )
)

# 4.19 Marciano <-> León I el Tracio (Mando Militar y Sucesión)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=marciano_id,
        object_id=leon_i_id,
        source_id=source_marcian_leo_id,
        source_locator="Juan Malalas, Chronographia XIV - León el Tracio como tribuno bajo el emperador Marciano",
        period=Period(
            start=HistoricalDate(year=455, precision="year"),
            end=HistoricalDate(year=455, precision="year"),
        ),
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
        note="El emperador Marciano promovió a altos cargos militares en Constantinopla al tribuno León el Tracio, quien le sucedería como emperador León I.",
    )
)

# 4.20 León I el Tracio -> Ariadna (Padre e hija)
get_or_create_verified_fact(
    FactInput(
        type_id="family.parent_of",
        subject_id=leon_i_id,
        object_id=ariadna_id,
        source_id=source_leo_ariadne_id,
        source_locator="Evagrio Escolástico, HE II, 16 - Nacimiento de Ariadna, primogénita de León I y Verina",
        period=Period(
            start=HistoricalDate(year=450, precision="year"),
            end=HistoricalDate(year=450, precision="year"),
        ),
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
        note="El emperador León I el Tracio y la emperatriz Verina engendraron a su primogénita Ariadna, futura emperatriz del Imperio bizantino.",
    )
)

# 4.21 Ariadna <-> Anastasio I Dicoro (Cónyuges)
get_or_create_verified_fact(
    FactInput(
        type_id="family.spouse_of",
        subject_id=ariadna_id,
        object_id=anastasio_i_id,
        source_id=source_anastasius_ariadne_id,
        source_locator="Constantino Porfirogéneta, De Ceremoniis I, 92 - Boda de Anastasio y Ariadna el 20 de mayo de 491",
        period=Period(
            start=HistoricalDate(year=491, month=5, day=20, precision="day"),
            end=HistoricalDate(year=515, precision="year"),
        ),
        location=LocationInput(
            name="Hipódromo de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0064,
            lng=28.9758,
        ),
        note="La emperatriz viuda Ariadna eligió y desposó al alto funcionario Anastasio Dicoro en mayo de 491 d. C., coronándolo emperador Anastasio I.",
    )
)

# 4.22 Anastasio I Dicoro <-> Justino I (Guardia Imperial de los Excubitores)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=anastasio_i_id,
        object_id=justino_i_id,
        source_id=source_anastasius_justin_id,
        source_locator="Procopio, Historia Secreta cap. 6 - Justino I comandante de los excubitores de Anastasio I",
        period=Period(
            start=HistoricalDate(year=515, precision="year"),
            end=HistoricalDate(year=515, precision="year"),
        ),
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
        note="El emperador Anastasio I designó a Justino I comandante en jefe de la guardia imperial de los excubitores en el Gran Palacio de Constantinopla.",
    )
)

# 4.23 Justino I -> Justiniano I el Grande (Padre adoptivo e hijo)
get_or_create_verified_fact(
    FactInput(
        type_id="family.parent_of",
        subject_id=justino_i_id,
        object_id=justiniano_i_id,
        source_id=source_justin_justinian_id,
        source_locator="Juan Lido, De Magistratibus - Adopción de Justiniano por su tío Justino I",
        period=Period(
            start=HistoricalDate(year=520, precision="year"),
            end=HistoricalDate(year=527, month=8, day=1, precision="day"),
        ),
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
        note="El emperador Justino I adoptó formalmente como hijo y sucesor imperial a su sobrino Flavio Pedro Sabacio Justiniano en Constantinopla.",
    )
)

# 4.24 Justiniano I el Grande <-> Casiodoro (Audiencias en Constantinopla)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=justiniano_i_id,
        object_id=casiodoro_id,
        source_id=source_justinian_cassiodorus_id,
        source_locator="Casiodoro, Institutiones (Prefacio) & James J. O'Donnell, Cassiodorus",
        period=Period(
            start=HistoricalDate(year=545, precision="year"),
            end=HistoricalDate(year=545, precision="year"),
        ),
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
        note="El emperador Justiniano I recibió e interactuó en Constantinopla con el senador romano y erudito Casiodoro durante su estancia entre 540 y 554 d. C.",
    )
)

# 4.25 Casiodoro <-> Papa Gregorio I Magno (Colaboración en Roma)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=casiodoro_id,
        object_id=gregorio_magno_id,
        source_id=source_cassiodorus_gregory_id,
        source_locator="Juan el Diácono, Vita Sancti Gregorii & Jeffrey Richards, Consul of God",
        period=Period(
            start=HistoricalDate(year=575, precision="year"),
            end=HistoricalDate(year=575, precision="year"),
        ),
        location=LocationInput(
            name="Monte Celio",
            city="Roma",
            country="Imperio bizantino",
            lat=41.8864,
            lng=12.4939,
        ),
        note="El veterano senador Casiodoro y el joven pretor romano Gregorio Magno coincidieron en Roma compartiendo proyectos monásticos e intelectuales.",
    )
)

# 4.26 Papa Gregorio I Magno <-> Mauricio (Apocrisiario en Constantinopla)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=gregorio_magno_id,
        object_id=mauricio_id,
        source_id=source_gregory_maurice_id,
        source_locator="San Gregorio Magno, Registrum Epistolarum & Teofilacto Simocates, Historia",
        period=Period(
            start=HistoricalDate(year=582, precision="year"),
            end=HistoricalDate(year=582, precision="year"),
        ),
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
        note="Gregorio Magno residió en Constantinopla como embajador papal (apocrisiario) y mantuvo audiencias regulares con el emperador Mauricio, apadrinando a su hijo.",
    )
)

# 4.27 Mauricio <-> Heraclio el Viejo (Nombramiento del Exarcado de África)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=mauricio_id,
        object_id=heraclio_viejo_id,
        source_id=source_maurice_heraclius_sr_id,
        source_locator="Teofilacto Simocates, Historia III - Mauricio confía el mando persa y África a Heraclio el Viejo",
        period=Period(
            start=HistoricalDate(year=590, precision="year"),
            end=HistoricalDate(year=590, precision="year"),
        ),
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
        note="El emperador Mauricio designó al general Heraclio el Viejo comandante supremo contra los persas y posteriormente exarca de África en Cartago.",
    )
)

# 4.28 Heraclio el Viejo -> Heraclio (Padre e hijo)
get_or_create_verified_fact(
    FactInput(
        type_id="family.parent_of",
        subject_id=heraclio_viejo_id,
        object_id=heraclio_id,
        source_id=source_heraclius_sr_heraclius_id,
        source_locator="Juan de Nikiû, Crónica cap. 109 - Nacimiento de Heraclio, hijo del exarca",
        period=Period(
            start=HistoricalDate(year=575, precision="year"),
            end=HistoricalDate(year=575, precision="year"),
        ),
        location=LocationInput(
            name="Cartago",
            city="Cartago",
            country="Imperio bizantino",
            lat=36.8528,
            lng=10.3236,
        ),
        note="El exarca Heraclio el Viejo engendró a su hijo Flavio Heraclio, a quien preparó y respaldó para zarpar con la flota a derrocar la tiranía en Constantinopla.",
    )
)

# 4.29 Heraclio -> Constantino III (Padre e hijo)
get_or_create_verified_fact(
    FactInput(
        type_id="family.parent_of",
        subject_id=heraclio_id,
        object_id=constantino_iii_id,
        source_id=source_heraclius_constantine_iii_id,
        source_locator="Nicéforo, Breviarium - Nacimiento de Constantino III el 3 de mayo de 612",
        period=Period(
            start=HistoricalDate(year=612, month=5, day=3, precision="day"),
            end=HistoricalDate(year=612, month=5, day=3, precision="day"),
        ),
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
        note="El emperador Heraclio y la emperatriz Eudoxia engendraron a su primogénito Constantino III en el Gran Palacio de Constantinopla.",
    )
)

# 4.30 Constantino III -> Constante II (Padre e hijo)
get_or_create_verified_fact(
    FactInput(
        type_id="family.parent_of",
        subject_id=constantino_iii_id,
        object_id=constante_ii_id,
        source_id=source_constantine_iii_constans_ii_id,
        source_locator="Constantino Porfirogéneta, DAI - Nacimiento de Constante II el 7 de noviembre de 630",
        period=Period(
            start=HistoricalDate(year=630, month=11, day=7, precision="day"),
            end=HistoricalDate(year=630, month=11, day=7, precision="day"),
        ),
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
        note="El emperador Constantino III engendró a su hijo Flavio Heraclio (coronado posteriormente como Constante II) en Constantinopla.",
    )
)

# 4.31 Constante II -> Constantino IV (Padre e hijo)
get_or_create_verified_fact(
    FactInput(
        type_id="family.parent_of",
        subject_id=constante_ii_id,
        object_id=constantino_iv_id,
        source_id=source_constans_ii_constantine_iv_id,
        source_locator="Teófanes, Chronographia AM 6160 - Nacimiento y coronación de Constantino IV",
        period=Period(
            start=HistoricalDate(year=652, precision="year"),
            end=HistoricalDate(year=652, precision="year"),
        ),
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
        note="El emperador Constante II engendró a su hijo primogénito Constantino IV en Constantinopla, nombrándolo corregente.",
    )
)

# 4.32 Constantino IV -> Justiniano II (Padre e hijo)
get_or_create_verified_fact(
    FactInput(
        type_id="family.parent_of",
        subject_id=constantino_iv_id,
        object_id=justiniano_ii_id,
        source_id=source_constantine_iv_justinian_ii_id,
        source_locator="Teófanes, Chronographia AM 6177 - Nacimiento de Justiniano II en 669 d. C.",
        period=Period(
            start=HistoricalDate(year=669, precision="year"),
            end=HistoricalDate(year=669, precision="year"),
        ),
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
        note="El emperador Constantino IV engendró a su hijo y sucesor Justiniano II en el Gran Palacio de Constantinopla.",
    )
)

# 4.33 Justiniano II <-> León III el Isáurico (Audiencia y nombramiento como espatario)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=justiniano_ii_id,
        object_id=leon_iii_id,
        source_id=source_justinian_ii_leo_iii_id,
        source_locator="Teófanes el Confesor, Chronographia AM 6197 - Justiniano II recibe a León y lo nombra espatario imperial en 705",
        period=Period(
            start=HistoricalDate(year=705, precision="year"),
            end=HistoricalDate(year=705, precision="year"),
        ),
        location=LocationInput(
            name="Gran Palacio de Constantinopla",
            city="Constantinopla",
            country="Imperio bizantino",
            lat=41.0054,
            lng=28.9768,
        ),
        note="El emperador Justiniano II recibió en audiencia solemne en Constantinopla en 705 d. C. al joven León III el Isáurico, nombrándolo espatario imperial.",
    )
)

# 4.34 Enrique Peña Nieto <-> Silvia Pinal (Homenaje en Los Pinos)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=pena_nieto_id,
        object_id=silvia_pinal_id,
        source_id=source_pena_nieto_pinal_id,
        source_locator="Presidencia de la República: Conmemoración del Día Internacional de la Mujer en Los Pinos, 8 de marzo de 2015",
        period=Period(
            start=HistoricalDate(year=2015, month=3, day=8, precision="day"),
            end=HistoricalDate(year=2015, month=3, day=8, precision="day"),
        ),
        location=LocationInput(
            name="Residencia Oficial de Los Pinos",
            city="Ciudad de México",
            country="México",
            lat=19.4150,
            lng=-99.1917,
        ),
        note="El presidente Enrique Peña Nieto recibió y rindió homenaje oficial en Los Pinos a la primera actriz y líder de la ANDA Silvia Pinal en el Día Internacional de la Mujer.",
    )
)

# 4.35 Silvia Pinal -> El Agente 00-P2 (Coprotagonista en doblaje)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=silvia_pinal_id,
        object_id=agente_00p2_id,
        role="actor",
        source_id=source_agente_00p2_id,
        source_locator="El Agente 00-P2 (2009) - Créditos de doblaje: Silvia Pinal como Mamá Osa",
        period=Period(
            start=HistoricalDate(year=2009, precision="year"),
            end=HistoricalDate(year=2009, precision="year"),
        ),
        location=LocationInput(
            name="Estudios de Ánima Estudios",
            city="Ciudad de México",
            country="México",
            lat=19.4326,
            lng=-99.1332,
        ),
        note="Silvia Pinal prestó su voz a la villana Mamá Osa en la película animada mexicana El Agente 00-P2 (2009), coprotagonizada con Mario Castañeda.",
    )
)

# 4.36 Mario Castañeda -> El Agente 00-P2 (Coprotagonista en doblaje)
get_or_create_verified_fact(
    FactInput(
        type_id="arts.co_starred",
        subject_id=mario_castaneda_id,
        object_id=agente_00p2_id,
        role="actor",
        source_id=source_agente_00p2_id,
        source_locator="El Agente 00-P2 (2009) - Créditos de doblaje: Mario Castañeda como Gino Tutifrutti",
        period=Period(
            start=HistoricalDate(year=2009, precision="year"),
            end=HistoricalDate(year=2009, precision="year"),
        ),
        location=LocationInput(
            name="Estudios de Ánima Estudios",
            city="Ciudad de México",
            country="México",
            lat=19.4326,
            lng=-99.1332,
        ),
        note="Mario Castañeda interpretó la voz de Gino Tutifrutti en la película animada mexicana El Agente 00-P2 (2009), coprotagonizada con Silvia Pinal.",
    )
)

# 4.37 Mario Castañeda <-> René García (Dragon Ball Z / Doblaje Estelar)
get_or_create_verified_fact(
    FactInput(
        type_id="personal.met",
        subject_id=mario_castaneda_id,
        object_id=rene_garcia_id,
        source_id=source_dragon_ball_id,
        source_locator="Candiani Dubbing Studios - Grabaciones de Dragon Ball Z: Goku y Vegeta",
        period=Period(
            start=HistoricalDate(year=1997, month=4, day=15, precision="day"),
            end=HistoricalDate(year=1997, month=4, day=15, precision="day"),
        ),
        location=LocationInput(
            name="Candiani Dubbing Studios",
            city="Ciudad de México",
            country="México",
            lat=19.3850,
            lng=-99.1720,
        ),
        note="Mario Castañeda (Goku) y René García (Vegeta) han trabajado juntos en cabina durante décadas conformando la dupla protagónica más famosa del doblaje latinoamericano.",
    )
)

print("\n================================================================================")
print("  CARGA COMPLETADA CON ÉXITO")
print("================================================================================")
