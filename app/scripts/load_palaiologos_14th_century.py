import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

john_viii_id = "ac03b33b-6f0e-4fc1-a01c-c1064a72eccd"

print("--- Iniciando carga de la Dinastía Paleólogo del siglo XIV y corte bizantina ---")

# 1. Crear a Manuel II Paleólogo
manuel_ii_input = PersonInput(
    name="Manuel II Paleólogo",
    aliases=[
        "Manuel II Palaiologos",
        "Emperador Manuel II",
        "Manuel Paleólogo",
    ],
    description=(
        "Emperador del Imperio Bizantino (1391–1425), distinguido estadista, filósofo, teólogo y escritor bizantino. "
        "Padre de Juan VIII y de Constantino XI (el último basileus); emprendió una histórica gira diplomática por Europa "
        "(1399–1402) siendo agasajado en París por Carlos VI y en Londres por Enrique IV, y fortificó el istmo de Corinto con el Hexamilion."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/9/92/Manuel_II_Palaiologos_%28cropped%29.jpg",
    wikidata_id="Q183808",
    birth=HistoricalDate(year=1350, month=6, day=27, precision="day"),
    death=HistoricalDate(year=1425, month=7, day=21, precision="day"),
).model_dump(mode="json")

manuel_ii = repo.create("people", manuel_ii_input)
manuel_ii_id = manuel_ii["id"]
print("Creado Manuel II Paleólogo con ID:", manuel_ii_id)

with driver.session() as s:
    s.run(
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
        id=manuel_ii_id,
        rn="Manuel II Palaiologos",
        bkf="Manuel II Paleólogo",
        c="GR",
        img=manuel_ii_input["image_url"],
        occ="Emperador del Imperio Bizantino (Basileus de los Romanos) y filósofo",
        desc=manuel_ii_input["description"],
    )

# 2. Conectar Manuel II -> Juan VIII Paleólogo (family.parent_of)
source_m2_j8 = repo.create(
    "sources",
    SourceInput(
        title="Manuel II Palaeologus (1391–1425): A Study in Late Byzantine Statesmanship",
        url="https://www.cambridge.org/core/books/last-centuries-of-byzantium-12611453/956DE9ACBFCCDA4A42C12BC16E49FEF2",
        publisher="Rutgers University Press / Cambridge University Press",
        author="John W. Barker & Donald M. Nicol",
    ).model_dump(mode="json"),
)

fact_m2_j8 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=manuel_ii_id,
            object_id=john_viii_id,
            source_id=source_m2_j8["id"],
            source_locator="John W. Barker, Manuel II Palaeologus, cap. 1: Nascita e incoronazione a Costantinopoli del co-imperatore Giovanni VIII (1392)",
            note=(
                "Manuel II Paleólogo fue el padre de Juan VIII Paleólogo, nacido de su matrimonio con la emperatriz Helena Dragaš "
                "el 18 de diciembre de 1392 en Constantinopla. Manuel asoció a Juan al trono imperial en 1416 y le confió la regencia durante sus viajes."
            ),
            status="draft",
        ),
    ),
)
data_m2_j8 = {
    k: v
    for k, v in repo.get("facts", fact_m2_j8["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_m2_j8["status"] = "verified"
repo.update(
    "facts",
    fact_m2_j8["id"],
    fact_m2_j8["revision"],
    validate_fact(repo, data_m2_j8),
    "verify",
)
print("Hecho Manuel II -> Juan VIII verificado.")

# 3. Crear a Helena Dragaš (Santa Hipomoni)
helena_input = PersonInput(
    name="Helena Dragaš",
    aliases=[
        "Helena Palaiologina",
        "Santa Hipomoni",
        "Jelena Dragaš",
    ],
    description=(
        "Emperatriz consorte del Imperio Bizantino (1392–1425) y madre de los dos últimos emperadores de Bizancio: Juan VIII y Constantino XI Paleólogo. "
        "Hija del príncipe serbio Constantino Dragaš de Dejanović, venerada en la Iglesia ortodoxa como Santa Hipomoni por su sabiduría y santidad."
    ),
    country="GR",
    city_born="Serres",
    image_url="https://upload.wikimedia.org/wikipedia/commons/b/bb/Saint_Hipomini_icon.jpg",
    wikidata_id="Q237645",
    birth=HistoricalDate(year=1372, precision="year"),
    death=HistoricalDate(year=1450, month=3, day=23, precision="day"),
).model_dump(mode="json")

helena = repo.create("people", helena_input)
helena_id = helena["id"]
print("Creada Helena Dragaš con ID:", helena_id)

with driver.session() as s:
    s.run(
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
        id=helena_id,
        rn="Helena Dragaš",
        bkf="Helena Dragaš",
        c="GR",
        img=helena_input["image_url"],
        occ="Emperatriz consorte del Imperio Bizantino (Santa Hipomoni)",
        desc=helena_input["description"],
    )

# 4. Conectar Helena Dragaš -> Juan VIII Paleólogo (family.parent_of)
source_hd_j8 = repo.create(
    "sources",
    SourceInput(
        title="The Byzantine Lady: Ten Portraits, 1250–1500",
        url="https://www.cambridge.org/core/books/byzantine-lady/49080A48154EC30F7517A7DAA3DCFBEF",
        publisher="Cambridge University Press",
        author="Donald M. Nicol",
    ).model_dump(mode="json"),
)

fact_hd_j8 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=helena_id,
            object_id=john_viii_id,
            source_id=source_hd_j8["id"],
            source_locator="Donald M. Nicol, The Byzantine Lady, cap. 5: Helena Dragaš, Empress of Byzantium, p. 82-89",
            note=(
                "Helena Dragaš fue la madre biológica de Juan VIII Paleólogo, primogénito de sus ocho hijos concebidos con el emperador Manuel II Paleólogo. "
                "Ejerció una profunda influencia pacificadora en la corte de Constantinopla hasta su muerte en 1450."
            ),
            status="draft",
        ),
    ),
)
data_hd_j8 = {
    k: v
    for k, v in repo.get("facts", fact_hd_j8["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_hd_j8["status"] = "verified"
repo.update(
    "facts",
    fact_hd_j8["id"],
    fact_hd_j8["revision"],
    validate_fact(repo, data_hd_j8),
    "verify",
)
print("Hecho Helena Dragaš -> Juan VIII verificado.")

# 5. Conectar Manuel II <-> Helena Dragaš (family.spouse_of)
source_m2_hd = repo.create(
    "sources",
    SourceInput(
        title="Memorias imperiales de Georgios Sphrantzes (Chronicon Minus)",
        url="https://www.jstor.org/stable/4137812",
        publisher="University of Massachusetts Press / Dumbarton Oaks",
        author="Georgios Sphrantzes",
    ).model_dump(mode="json"),
)

fact_m2_hd = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.spouse_of",
            subject_id=manuel_ii_id,
            object_id=helena_id,
            source_id=source_m2_hd["id"],
            source_locator="Boda imperial solemne celebrada en la Basílica de Santa Sofía de Constantinopla el 10 de febrero de 1392",
            note=(
                "Manuel II Paleólogo y Helena Dragaš contrajeron nupcias imperiales el 10 de febrero de 1392 en Santa Sofía, "
                "siendo coronada Helena como Augustas y consorte del Imperio."
            ),
            status="draft",
        ),
    ),
)
data_m2_hd = {
    k: v
    for k, v in repo.get("facts", fact_m2_hd["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_m2_hd["status"] = "verified"
repo.update(
    "facts",
    fact_m2_hd["id"],
    fact_m2_hd["revision"],
    validate_fact(repo, data_m2_hd),
    "verify",
)
print("Hecho Manuel II <-> Helena Dragaš verificado.")

# 6. Crear a Juan V Paleólogo
john_v_input = PersonInput(
    name="Juan V Paleólogo",
    aliases=[
        "John V Palaiologos",
        "Ioannes V Palaiologos",
        "Emperador Juan V",
    ],
    description=(
        "Emperador del Imperio Bizantino durante medio siglo (1341–1391), hijo de Andrónico III Paleólogo y Ana de Saboya. "
        "Su prolongado reinado marcó las guerras civiles del siglo XIV, la expansión otomana y un histórico viaje a Roma en 1369 "
        "donde profesó la fe católica ante el Papa Urbano V en la Basílica de San Pedro."
    ),
    country="GR",
    city_born="Didimóteico",
    image_url="https://upload.wikimedia.org/wikipedia/commons/3/37/Restored_mosaic_of_John_V_Palaiologos_%28head%29.jpg",
    wikidata_id="Q37068",
    birth=HistoricalDate(year=1332, month=6, day=18, precision="day"),
    death=HistoricalDate(year=1391, month=2, day=16, precision="day"),
).model_dump(mode="json")

john_v = repo.create("people", john_v_input)
john_v_id = john_v["id"]
print("Creado Juan V Paleólogo con ID:", john_v_id)

with driver.session() as s:
    s.run(
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
        id=john_v_id,
        rn="Ioannes V Palaiologos",
        bkf="Juan V Paleólogo",
        c="GR",
        img=john_v_input["image_url"],
        occ="Emperador del Imperio Bizantino (Basileus de los Romanos)",
        desc=john_v_input["description"],
    )

# 7. Conectar Juan V -> Manuel II Paleólogo (family.parent_of)
source_j5_m2 = repo.create(
    "sources",
    SourceInput(
        title="The Reluctant Emperor: A Biography of John Cantacuzene, Byzantine Emperor and Monk",
        url="https://www.cambridge.org/core/books/reluctant-emperor/5297A494EC969C893264F34A999602AA",
        publisher="Cambridge University Press",
        author="Donald M. Nicol",
    ).model_dump(mode="json"),
)

fact_j5_m2 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=john_v_id,
            object_id=manuel_ii_id,
            source_id=source_j5_m2["id"],
            source_locator="Nascita di Manuele II Paleologo il 27 giugno 1350 a Costantinopoli da Giovanni V ed Elena Cantacuzena",
            note=(
                "Juan V Paleólogo fue el padre de Manuel II Paleólogo, nacido de su matrimonio con Helena Cantacucena. "
                "Manuel fue su colaborador más leal frente a las sublevaciones de su hermano Andrónico IV, sucediéndolo como emperador en 1391."
            ),
            status="draft",
        ),
    ),
)
data_j5_m2 = {
    k: v
    for k, v in repo.get("facts", fact_j5_m2["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_j5_m2["status"] = "verified"
repo.update(
    "facts",
    fact_j5_m2["id"],
    fact_j5_m2["revision"],
    validate_fact(repo, data_j5_m2),
    "verify",
)
print("Hecho Juan V -> Manuel II verificado.")

# 8. Crear a Juan VI Cantacuceno
cantacuzene_input = PersonInput(
    name="Juan VI Cantacuceno",
    aliases=[
        "John VI Kantakouzenos",
        "Johannes Cantacuzenus",
        "Monje Josafat",
    ],
    description=(
        "Emperador del Imperio Bizantino (1347–1354), estadista, comandante militar, teólogo y célebre historiador bizantino. "
        "Suegro de Juan V Paleólogo; tras abdicar al trono se retiró como monje Josafat y escribió sus célebres 'Historias' "
        "(Historiarum Libri IV), obra fundamental de la historiografía medieval griega conservada en la BnF."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/2/22/John_VI_Kantakouzenos.jpg",
    wikidata_id="Q37070",
    birth=HistoricalDate(year=1292, precision="year"),
    death=HistoricalDate(year=1383, month=6, day=15, precision="day"),
).model_dump(mode="json")

cantacuzene = repo.create("people", cantacuzene_input)
cantacuzene_id = cantacuzene["id"]
print("Creado Juan VI Cantacuceno con ID:", cantacuzene_id)

with driver.session() as s:
    s.run(
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
        id=cantacuzene_id,
        rn="Ioannes VI Kantakouzenos",
        bkf="Juan VI Cantacuceno",
        c="GR",
        img=cantacuzene_input["image_url"],
        occ="Emperador bizantino e historiador (autor de Historiarum Libri IV)",
        desc=cantacuzene_input["description"],
    )

# 9. Conectar Juan VI Cantacuceno <-> Juan V Paleólogo (personal.met / cogobierno y paz de 1347)
source_c6_j5 = repo.create(
    "sources",
    SourceInput(
        title="Historiarum Libri IV: Edición crítica del Corpus Scriptorum Historiae Byzantinae (CSHB)",
        url="https://www.degruyter.com/document/doi/10.1515/9783110300307/html",
        publisher="Bonn: Weber / De Gruyter",
        author="Johannes Cantacuzenus (ed. Ludwig Schopen)",
    ).model_dump(mode="json"),
)

fact_c6_j5 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=cantacuzene_id,
            object_id=john_v_id,
            source_id=source_c6_j5["id"],
            source_locator="Historiarum, Libro IV: Entrada en Constantinopla en febrero de 1347, acuerdo de cogobierno y boda de Helena con Juan V en mayo de 1347",
            note=(
                "Juan VI Cantacuceno entró pacíficamente en Constantinopla en febrero de 1347 y selló la reconciliación del Imperio "
                "asociando al trono a Juan V Paleólogo como co-emperador y entregándole en matrimonio a su hija Helena Cantacucena, "
                "gobernando juntos la corte imperial hasta la abdicación monástica de Cantacuceno en 1354."
            ),
            status="draft",
        ),
    ),
)
data_c6_j5 = {
    k: v
    for k, v in repo.get("facts", fact_c6_j5["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_c6_j5["status"] = "verified"
repo.update(
    "facts",
    fact_c6_j5["id"],
    fact_c6_j5["revision"],
    validate_fact(repo, data_c6_j5),
    "verify",
)
print("Hecho Juan VI Cantacuceno <-> Juan V Paleólogo verificado.")

# 10. Crear a Carlos VI de Francia («el Bienamado»)
charles_vi_input = PersonInput(
    name="Carlos VI de Francia",
    aliases=[
        "Charles VI de France",
        "Carlos el Bienamado",
        "Carlos el Loco",
    ],
    description=(
        "Rey de Francia (1380–1422) de la dinastía Valois, monarca durante la turbulenta Guerra de los Cien Años. "
        "Acogió solemnemente al emperador bizantino Manuel II Paleólogo en el Palacio del Louvre de París durante más de dos años "
        "(1400–1402) asignándole una generosa pensión y escolta regia."
    ),
    country="FR",
    city_born="París",
    image_url="https://upload.wikimedia.org/wikipedia/commons/0/0a/Charles_VI_de_France_-_Dialogues_de_Pierre_Salmon_-_Bib_de_Gen%C3%A8ve_MsFr165f4.jpg",
    wikidata_id="Q160341",
    birth=HistoricalDate(year=1368, month=12, day=3, precision="day"),
    death=HistoricalDate(year=1422, month=10, day=21, precision="day"),
).model_dump(mode="json")

charles_vi = repo.create("people", charles_vi_input)
charles_vi_id = charles_vi["id"]
print("Creado Carlos VI de Francia con ID:", charles_vi_id)

with driver.session() as s:
    s.run(
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
        id=charles_vi_id,
        rn="Charles VI de France",
        bkf="Carlos VI de Francia",
        c="FR",
        img=charles_vi_input["image_url"],
        occ="Rey de Francia (Casa de Valois)",
        desc=charles_vi_input["description"],
    )

# 11. Conectar Carlos VI <-> Manuel II Paleólogo (personal.met / estancia imperial en el Louvre)
source_c6_m2 = repo.create(
    "sources",
    SourceInput(
        title="Chronique du Religieux de Saint-Denys, contenant le règne de Charles VI de 1380 à 1422",
        url="https://gallica.bnf.fr/ark:/12148/bpt6k208152j",
        publisher="Bibliothèque Nationale de France (BnF) / Crapelet",
        author="Michel Pintoin (Chantre de Saint-Denis)",
    ).model_dump(mode="json"),
)

fact_c6_m2 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=charles_vi_id,
            object_id=manuel_ii_id,
            source_id=source_c6_m2["id"],
            source_locator="Chronique du Religieux de Saint-Denys, Libro XXI, cap. 1: Entrada triunfal en París y residencia en el Louvre (3 de junio de 1400)",
            note=(
                "El 3 de junio de 1400, el rey Carlos VI de Francia recibió a las puertas de París (Charenton) con pompa imperial "
                "al emperador bizantino Manuel II Paleólogo. Manuel II residió en el Palacio del Louvre de París hasta noviembre de 1402 "
                "como huésped de honor de la corona francesa, recibiendo fondos y promesas de tropas para levantar el asedio otomano a Constantinopla."
            ),
            status="draft",
        ),
    ),
)
data_c6_m2 = {
    k: v
    for k, v in repo.get("facts", fact_c6_m2["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_c6_m2["status"] = "verified"
repo.update(
    "facts",
    fact_c6_m2["id"],
    fact_c6_m2["revision"],
    validate_fact(repo, data_c6_m2),
    "verify",
)
print("Hecho Carlos VI <-> Manuel II verificado.")

# Resumen de conexiones
print("\n--- Conexiones de Manuel II Paleólogo ---")
print(json.dumps(connection_preview(repo, manuel_ii_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Juan V Paleólogo ---")
print(json.dumps(connection_preview(repo, john_v_id), indent=2, ensure_ascii=False))
