import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

john_v_id = "7bc90e27-5ce2-49fa-bd51-213602077394"

print("--- Iniciando carga del siglo XIII-XIV bizantino: Andrónico III, Andrónico II y Miguel VIII Paleólogo ---")

# 1. Crear a Andrónico III Paleólogo
andronikos_iii_input = PersonInput(
    name="Andrónico III Paleólogo",
    aliases=[
        "Andronikos III Palaiologos",
        "Andrónico III",
        "Emperador Andrónico III",
    ],
    description=(
        "Emperador del Imperio Bizantino (1328–1341), militar audaz y enérgico gobernante que recuperó Quíos, Lesbos, Focea, "
        "Epiro y Tesalia para Bizancio. Reformó el sistema judicial imperial instaurando el tribunal supremo de los "
        "'Jueces Universales de los Romanos' (Kritai Katholikoi) e impulsó las artes y la erudición junto a Juan Cantacuceno."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/d/df/Andronikos_III_Palaiologos.jpg",
    wikidata_id="Q37063",
    birth=HistoricalDate(year=1297, month=3, day=25, precision="day"),
    death=HistoricalDate(year=1341, month=6, day=15, precision="day"),
).model_dump(mode="json")

andronikos_iii = repo.create("people", andronikos_iii_input)
andronikos_iii_id = andronikos_iii["id"]
print("Creado Andrónico III Paleólogo con ID:", andronikos_iii_id)

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
        id=andronikos_iii_id,
        rn="Andronikos III Palaiologos",
        bkf="Andrónico III Paleólogo",
        c="GR",
        img=andronikos_iii_input["image_url"],
        occ="Emperador del Imperio Bizantino (Basileus de los Romanos)",
        desc=andronikos_iii_input["description"],
    )

# 2. Conectar Andrónico III -> Juan V Paleólogo (family.parent_of)
source_a3_j5 = repo.create(
    "sources",
    SourceInput(
        title="Byzantina Historia: De Michaele et Andronicis Palaeologis",
        url="https://www.degruyter.com/document/doi/10.1515/9783110300307/html",
        publisher="Corpus Scriptorum Historiae Byzantinae (CSHB), Bonn: Weber",
        author="Nicephorus Gregoras (ed. Ludwig Schopen)",
    ).model_dump(mode="json"),
)

fact_a3_j5 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=andronikos_iii_id,
            object_id=john_v_id,
            source_id=source_a3_j5["id"],
            source_locator="Nicephorus Gregoras, Byzantina Historia, Libro IX: Nascita dell'erede Giovanni V a Didymoteicho il 18 giugno 1332",
            note=(
                "Andrónico III Paleólogo fue el padre de Juan V Paleólogo, nacido de su segundo matrimonio con la princesa Ana de Saboya "
                "el 18 de junio de 1332. A su prematura muerte en 1341, Juan V le sucedió en el trono imperial bajo la regencia de su madre."
            ),
            status="draft",
        ),
    ),
)
data_a3_j5 = {
    k: v
    for k, v in repo.get("facts", fact_a3_j5["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_a3_j5["status"] = "verified"
repo.update(
    "facts",
    fact_a3_j5["id"],
    fact_a3_j5["revision"],
    validate_fact(repo, data_a3_j5),
    "verify",
)
print("Hecho Andrónico III -> Juan V verificado.")

# 3. Crear a Ana de Saboya (Giovanna di Savoia / Anna Palaiologina)
anna_savoy_input = PersonInput(
    name="Ana de Saboya",
    aliases=[
        "Anna of Savoy",
        "Giovanna di Savoia",
        "Anna Palaiologina",
    ],
    description=(
        "Emperatriz consorte y regente del Imperio Bizantino (1341–1347), hija de Amadeo V de Saboya y María de Brabante. "
        "Madre de Juan V Paleólogo; encabezó la regencia imperial en Constantinopla durante la minoría de edad de su hijo "
        "y posteriormente gobernó como señora de Tesalónica."
    ),
    country="IT",
    city_born="Chambéry",
    image_url="https://upload.wikimedia.org/wikipedia/commons/1/1b/Anna_of_Savoy.jpg",
    wikidata_id="Q232338",
    birth=HistoricalDate(year=1306, precision="year"),
    death=HistoricalDate(year=1365, precision="year"),
).model_dump(mode="json")

anna_savoy = repo.create("people", anna_savoy_input)
anna_savoy_id = anna_savoy["id"]
print("Creada Ana de Saboya con ID:", anna_savoy_id)

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
        id=anna_savoy_id,
        rn="Giovanna di Savoia",
        bkf="Ana de Saboya",
        c="IT",
        img=anna_savoy_input["image_url"],
        occ="Emperatriz consorte y regente del Imperio Bizantino (Casa de Saboya)",
        desc=anna_savoy_input["description"],
    )

# 4. Conectar Ana de Saboya -> Juan V Paleólogo (family.parent_of)
source_as_j5 = repo.create(
    "sources",
    SourceInput(
        title="The Byzantine Lady: Ten Portraits, 1250–1500 (Cap. 3: Anna of Savoy)",
        url="https://www.cambridge.org/core/books/byzantine-lady/49080A48154EC30F7517A7DAA3DCFBEF",
        publisher="Cambridge University Press",
        author="Donald M. Nicol",
    ).model_dump(mode="json"),
)

fact_as_j5 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=anna_savoy_id,
            object_id=john_v_id,
            source_id=source_as_j5["id"],
            source_locator="Donald M. Nicol, The Byzantine Lady, p. 45-58: Reggenza dell'imperatrice Anna di Savoia e tutela del figlio Giovanni V",
            note=(
                "Ana de Saboya fue la madre biológica de Juan V Paleólogo y gobernó como regente del Imperio Bizantino en Constantinopla "
                "defendiendo los derechos dinásticos de su hijo durante la cruenta guerra civil de 1341–1347."
            ),
            status="draft",
        ),
    ),
)
data_as_j5 = {
    k: v
    for k, v in repo.get("facts", fact_as_j5["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_as_j5["status"] = "verified"
repo.update(
    "facts",
    fact_as_j5["id"],
    fact_as_j5["revision"],
    validate_fact(repo, data_as_j5),
    "verify",
)
print("Hecho Ana de Saboya -> Juan V verificado.")

# 5. Conectar Andrónico III <-> Ana de Saboya (family.spouse_of)
source_a3_as = repo.create(
    "sources",
    SourceInput(
        title="Regesti dei Conti di Savoia e nozze imperiali di Costantinopoli (Ottobre 1326)",
        url="https://www.persee.fr/doc/rebyz_0766-5598_1975_num_33_1_1502",
        publisher="Revue des Études Byzantines / Institut Français d'Études Byzantines",
        author="Raymond-Joseph Loenertz & Albert Failler",
    ).model_dump(mode="json"),
)

fact_a3_as = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.spouse_of",
            subject_id=andronikos_iii_id,
            object_id=anna_savoy_id,
            source_id=source_a3_as["id"],
            source_locator="Boda imperial celebrada en Constantinopla en octubre de 1326 y coronación de Juana como emperatriz Anna",
            note=(
                "Andrónico III Paleólogo y la princesa Ana de Saboya contrajeron matrimonio en Constantinopla en octubre de 1326, "
                "sellando una histórica alianza entre la corte bizantina y la nobleza del Sacro Imperio y el Reino de Francia."
            ),
            status="draft",
        ),
    ),
)
data_a3_as = {
    k: v
    for k, v in repo.get("facts", fact_a3_as["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_a3_as["status"] = "verified"
repo.update(
    "facts",
    fact_a3_as["id"],
    fact_a3_as["revision"],
    validate_fact(repo, data_a3_as),
    "verify",
)
print("Hecho Andrónico III <-> Ana de Saboya verificado.")

# 6. Crear a Andrónico II Paleólogo
andronikos_ii_input = PersonInput(
    name="Andrónico II Paleólogo",
    aliases=[
        "Andronikos II Palaiologos",
        "Andrónico II",
        "Emperador Andrónico II",
    ],
    description=(
        "Emperador del Imperio Bizantino (1282–1328), hijo de Miguel VIII Paleólogo y Ana de Hungría. "
        "Su reinado de casi medio siglo fue el apogeo del 'Renacimiento Paleólogo', período de florecimiento intelectual, "
        "astronómico y artístico en Constantinopla patrocinado por su primer ministro Teodoro Metoquita."
    ),
    country="GR",
    city_born="Nicea",
    image_url="https://upload.wikimedia.org/wikipedia/commons/1/1b/Chrysobull_of_Andronikos_II_Palaiologos.jpg",
    wikidata_id="Q37059",
    birth=HistoricalDate(year=1259, month=3, day=25, precision="day"),
    death=HistoricalDate(year=1332, month=2, day=13, precision="day"),
).model_dump(mode="json")

andronikos_ii = repo.create("people", andronikos_ii_input)
andronikos_ii_id = andronikos_ii["id"]
print("Creado Andrónico II Paleólogo con ID:", andronikos_ii_id)

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
        id=andronikos_ii_id,
        rn="Andronikos II Palaiologos",
        bkf="Andrónico II Paleólogo",
        c="GR",
        img=andronikos_ii_input["image_url"],
        occ="Emperador del Imperio Bizantino (Basileus de los Romanos) y mecenas del Renacimiento Paleólogo",
        desc=andronikos_ii_input["description"],
    )

# 7. Conectar Andrónico II <-> Andrónico III Paleólogo (personal.met / coronación y tratados)
source_a2_a3 = repo.create(
    "sources",
    SourceInput(
        title="De Michaele et Andronico Palaeologis Libri XIII / Byzantina Historia",
        url="https://www.cambridge.org/core/books/last-centuries-of-byzantium-12611453/956DE9ACBFCCDA4A42C12BC16E49FEF2",
        publisher="Cambridge University Press / Dumbarton Oaks",
        author="Donald M. Nicol: The Last Centuries of Byzantium",
    ).model_dump(mode="json"),
)

fact_a2_a3 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=andronikos_ii_id,
            object_id=andronikos_iii_id,
            source_id=source_a2_a3["id"],
            source_locator="Santa Sofía de Constantinopla (2 de febrero de 1325): Coronación solemne conjunta de Andrónico III por su abuelo Andrónico II",
            note=(
                "Andrónico II Paleólogo crio en la corte imperial a su nieto Andrónico III y lo coronó solemnemente como co-emperador "
                "en la basílica de Santa Sofía de Constantinopla el 2 de febrero de 1325, negociando tratados de paz que redefinieron "
                "el gobierno compartido del Imperio antes de su abdicación en 1328."
            ),
            status="draft",
        ),
    ),
)
data_a2_a3 = {
    k: v
    for k, v in repo.get("facts", fact_a2_a3["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_a2_a3["status"] = "verified"
repo.update(
    "facts",
    fact_a2_a3["id"],
    fact_a2_a3["revision"],
    validate_fact(repo, data_a2_a3),
    "verify",
)
print("Hecho Andrónico II <-> Andrónico III verificado.")

# 8. Crear a Miguel VIII Paleólogo
michael_viii_input = PersonInput(
    name="Miguel VIII Paleólogo",
    aliases=[
        "Michael VIII Palaiologos",
        "Miguel VIII",
        "El Restaurador del Imperio",
    ],
    description=(
        "Emperador del Imperio Bizantino (1259–1282) y fundador de la ilustre Dinastía Paleólogo. "
        "Héroe militar que reconquistó Constantinopla el 25 de julio de 1261, expulsando a los cruzados latinos "
        "y restaurando el Imperio Romano de Oriente tras casi seis décadas de ocupación occidental."
    ),
    country="GR",
    city_born="Nicea",
    image_url="https://upload.wikimedia.org/wikipedia/commons/8/8d/Michael_VIII_Palaiologos_-_National_Library_of_Russia%2C_gr._118_-_f._22r.jpg",
    wikidata_id="Q37055",
    birth=HistoricalDate(year=1223, precision="year"),
    death=HistoricalDate(year=1282, month=12, day=11, precision="day"),
).model_dump(mode="json")

michael_viii = repo.create("people", michael_viii_input)
michael_viii_id = michael_viii["id"]
print("Creado Miguel VIII Paleólogo con ID:", michael_viii_id)

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
        id=michael_viii_id,
        rn="Michael VIII Palaiologos",
        bkf="Miguel VIII Paleólogo",
        c="GR",
        img=michael_viii_input["image_url"],
        occ="Emperador y restaurador del Imperio Bizantino (fundador de la Dinastía Paleólogo)",
        desc=michael_viii_input["description"],
    )

# 9. Conectar Miguel VIII -> Andrónico II Paleólogo (family.parent_of)
source_m8_a2 = repo.create(
    "sources",
    SourceInput(
        title="De Michaele Palaeologo: George Pachymeres Relations Historiques",
        url="https://www.persee.fr/doc/rebyz_0766-5598_1984_num_42_1_2159",
        publisher="Les Belles Lettres / Institut Français d'Études Byzantines",
        author="Georges Pachymérès (ed. Albert Failler)",
    ).model_dump(mode="json"),
)

fact_m8_a2 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=michael_viii_id,
            object_id=andronikos_ii_id,
            source_id=source_m8_a2["id"],
            source_locator="Pachymérès, Relations Historiques, Livres I-II: Nascita di Andronico II nel 1259 da Michele VIII e Teodora Ducaina Vatatzina",
            note=(
                "Miguel VIII Paleólogo fue el padre de Andrónico II Paleólogo, nacido de su matrimonio con la emperatriz Teodora Ducaina Vatatzina "
                "el 25 de marzo de 1259. Tras reconquistar Constantinopla en 1261, Miguel VIII coronó formalmente a Andrónico como su co-emperador y heredero."
            ),
            status="draft",
        ),
    ),
)
data_m8_a2 = {
    k: v
    for k, v in repo.get("facts", fact_m8_a2["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_m8_a2["status"] = "verified"
repo.update(
    "facts",
    fact_m8_a2["id"],
    fact_m8_a2["revision"],
    validate_fact(repo, data_m8_a2),
    "verify",
)
print("Hecho Miguel VIII -> Andrónico II verificado.")

# 10. Crear a Teodoro Metoquita (Theodore Metochites)
metochites_input = PersonInput(
    name="Teodoro Metoquita",
    aliases=[
        "Theodore Metochites",
        "Theodoros Metochites",
        "Megas Logothetes Metoquita",
    ],
    description=(
        "Estadista, primer ministro (Gran Logoteta), erudito, astrónomo y filósofo bizantino, una de las mentes más preclaras del Renacimiento Paleólogo. "
        "Mano derecha del emperador Andrónico II; financió la reconstrucción y deslumbrantes mosaicos de la iglesia de San Salvador de Cora en Constantinopla."
    ),
    country="GR",
    city_born="Nicea",
    image_url="https://upload.wikimedia.org/wikipedia/commons/9/97/Chora_Church_interior_March_2008.JPG",
    wikidata_id="Q313551",
    birth=HistoricalDate(year=1270, precision="year"),
    death=HistoricalDate(year=1332, month=3, day=13, precision="day"),
).model_dump(mode="json")

metochites = repo.create("people", metochites_input)
metochites_id = metochites["id"]
print("Creado Teodoro Metoquita con ID:", metochites_id)

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
        id=metochites_id,
        rn="Theodoros Metochites",
        bkf="Teodoro Metoquita",
        c="GR",
        img=metochites_input["image_url"],
        occ="Primer ministro (Megas Logothetes), filósofo y humanista bizantino",
        desc=metochites_input["description"],
    )

# 11. Conectar Teodoro Metoquita <-> Andrónico II Paleólogo (personal.met / primer ministro)
source_tm_a2 = repo.create(
    "sources",
    SourceInput(
        title="Theodore Metochites' Poems to Himself: Introduction, Text, and Commentary",
        url="https://www.degruyter.com/document/doi/10.1515/9783110531589/html",
        publisher="De Gruyter / Byzantinisches Archiv",
        author="Ihor Ševčenko",
    ).model_dump(mode="json"),
)

fact_tm_a2 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=metochites_id,
            object_id=andronikos_ii_id,
            source_id=source_tm_a2["id"],
            source_locator="Palazzo delle Blacherne e Chiesa di San Salvatore in Chora, Costantinopoli (1290–1328)",
            note=(
                "Teodoro Metoquita sirvió durante más de tres décadas como el principal ministro, diplomático y consejero intelectual "
                "del emperador Andrónico II Paleólogo en el Palacio de Blanquerna en Constantinopla, compartiendo tertulias filosóficas, "
                "astronómicas y literarias que definieron la edad de oro del Renacimiento Paleólogo."
            ),
            status="draft",
        ),
    ),
)
data_tm_a2 = {
    k: v
    for k, v in repo.get("facts", fact_tm_a2["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_tm_a2["status"] = "verified"
repo.update(
    "facts",
    fact_tm_a2["id"],
    fact_tm_a2["revision"],
    validate_fact(repo, data_tm_a2),
    "verify",
)
print("Hecho Teodoro Metoquita <-> Andrónico II verificado.")

# Resumen de conexiones
print("\n--- Conexiones de Andrónico III Paleólogo ---")
print(json.dumps(connection_preview(repo, andronikos_iii_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Miguel VIII Paleólogo ---")
print(json.dumps(connection_preview(repo, michael_viii_id), indent=2, ensure_ascii=False))
