import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

basil_ii_id = "390a0e0f-b298-4171-b8a9-92397cc5721c"

print("--- Iniciando carga del siglo IX–X: Romano II, Constantino VII, León VI, Focio y Basilio I ---")

# 1. Crear a Romano II
romanos_ii_input = PersonInput(
    name="Romano II",
    aliases=[
        "Romanos II",
        "Emperador Romano II",
    ],
    description=(
        "Emperador del Imperio Bizantino (959–963) de la Dinastía Macedonia, hijo de Constantino VII Porfirogéneta. "
        "Padre de Basilio II y de la princesa Ana Porfirogéneta; durante su reinado el general Nicéforo Focas "
        "reconquistó la estratégica isla de Creta a los árabes en 961."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/1/1c/Romanos_et_Eudoxie_%28cropped2%29.JPG",
    wikidata_id="Q41604",
    birth=HistoricalDate(year=938, precision="year"),
    death=HistoricalDate(year=963, month=3, day=15, precision="day"),
).model_dump(mode="json")

romanos_ii = repo.create("people", romanos_ii_input)
romanos_ii_id = romanos_ii["id"]
print("Creado Romano II con ID:", romanos_ii_id)

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
        id=romanos_ii_id,
        rn="Romanos II",
        bkf="Romano II",
        c="GR",
        img=romanos_ii_input["image_url"],
        occ="Emperador del Imperio Bizantino (Dinastía Macedonia)",
        desc=romanos_ii_input["description"],
    )

# 2. Conectar Romano II -> Basilio II (family.parent_of)
source_r2_b2 = repo.create(
    "sources",
    SourceInput(
        title="Theophanes Continuatus: Chronographia (Libro VI: De Romano et Basilio)",
        url="https://www.degruyter.com/document/doi/10.1515/9783110294439/html",
        publisher="Corpus Scriptorum Historiae Byzantinae (CSHB), Bonn: Weber",
        author="Theophanes Continuatus (ed. Immanuel Bekker)",
    ).model_dump(mode="json"),
)

fact_r2_b2 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=romanos_ii_id,
            object_id=basil_ii_id,
            source_id=source_r2_b2["id"],
            source_locator="Theophanes Continuatus, Libro VI: Nascita dell'erede porfirogenito Basilio nel 958 a Costantinopoli da Romano II e Teofano",
            note=(
                "Romano II fue el padre de Basilio II, nacido en la cámara púrpura del Gran Palacio de Constantinopla en 958 "
                "de su matrimonio con la emperatriz Teófano. Romano II coronó a Basilio como co-emperador el 22 de abril de 960 en Santa Sofía."
            ),
            status="draft",
        ),
    ),
)
data_r2_b2 = {
    k: v
    for k, v in repo.get("facts", fact_r2_b2["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_r2_b2["status"] = "verified"
repo.update(
    "facts",
    fact_r2_b2["id"],
    fact_r2_b2["revision"],
    validate_fact(repo, data_r2_b2),
    "verify",
)
print("Hecho Romano II -> Basilio II verificado.")

# 3. Crear a Constantino VII Porfirogéneta
constantine_vii_input = PersonInput(
    name="Constantino VII Porfirogéneta",
    aliases=[
        "Constantine VII Porphyrogenitus",
        "Constantino Porfirogénito",
        "Constantino VII",
    ],
    description=(
        "Emperador del Imperio Bizantino (913–959), célebre erudito, diplomático y tratadista bizantino de la Dinastía Macedonia. "
        "Autor de obras inmortales sobre la geopolítica y el protocolo imperial como 'De Administrando Imperio' y 'De Ceremoniis', "
        "padre de Romano II y promotor de la enciclopedia y el arte bizantino clásico."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/7/7f/Constantine_VII_Porphyrogenitus_%282%29.jpeg",
    wikidata_id="Q41608",
    birth=HistoricalDate(year=905, month=5, day=18, precision="day"),
    death=HistoricalDate(year=959, month=11, day=9, precision="day"),
).model_dump(mode="json")

constantine_vii = repo.create("people", constantine_vii_input)
constantine_vii_id = constantine_vii["id"]
print("Creado Constantino VII con ID:", constantine_vii_id)

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
        id=constantine_vii_id,
        rn="Constantine VII Porphyrogenitus",
        bkf="Constantino VII Porfirogéneta",
        c="GR",
        img=constantine_vii_input["image_url"],
        occ="Emperador del Imperio Bizantino y erudito (autor de De Administrando Imperio)",
        desc=constantine_vii_input["description"],
    )

# 4. Conectar Constantino VII -> Romano II (family.parent_of)
source_c7_r2 = repo.create(
    "sources",
    SourceInput(
        title="Constantine Porphyrogenitus: De Administrando Imperio",
        url="https://www.doaks.org/research/publications/books/de-administrando-imperio",
        publisher="Dumbarton Oaks Center for Byzantine Studies / Harvard University",
        author="Constantine VII Porphyrogenitus (ed. Gy. Moravcsik & R.J.H. Jenkins)",
    ).model_dump(mode="json"),
)

fact_c7_r2 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=constantine_vii_id,
            object_id=romanos_ii_id,
            source_id=source_c7_r2["id"],
            source_locator="De Administrando Imperio, Proemio: Dedicatoria de Constantino VII a su amado hijo y heredero imperial Romano II (nacido en 938)",
            note=(
                "Constantino VII Porfirogéneta fue el padre de Romano II, nacido en 938 de su matrimonio con la emperatriz Helena Lecapena. "
                "Constantino escribió especialmente para la instrucción política de Romano su célebre tratado 'De Administrando Imperio'."
            ),
            status="draft",
        ),
    ),
)
data_c7_r2 = {
    k: v
    for k, v in repo.get("facts", fact_c7_r2["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_c7_r2["status"] = "verified"
repo.update(
    "facts",
    fact_c7_r2["id"],
    fact_c7_r2["revision"],
    validate_fact(repo, data_c7_r2),
    "verify",
)
print("Hecho Constantino VII -> Romano II verificado.")

# 5. Crear a León VI el Sabio
leo_vi_input = PersonInput(
    name="León VI el Sabio",
    aliases=[
        "Leo VI the Wise",
        "León VI el Filósofo",
        "Leo VI",
    ],
    description=(
        "Emperador del Imperio Bizantino (886–912) de la Dinastía Macedonia, conocido como 'el Sabio' o 'el Filósofo'. "
        "Discípulo del patriarca Focio el Grande; promulgó las 'Basílicas' (Basiliká), la codificación jurídica en griego más extensa "
        "del derecho romano desde Justiniano, retratado en el mosaico de la Puerta Imperial de Santa Sofía."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/f/f5/Emperor_Leo_VI_detail.jpg",
    wikidata_id="Q41614",
    birth=HistoricalDate(year=866, month=9, day=19, precision="day"),
    death=HistoricalDate(year=912, month=5, day=11, precision="day"),
).model_dump(mode="json")

leo_vi = repo.create("people", leo_vi_input)
leo_vi_id = leo_vi["id"]
print("Creado León VI el Sabio con ID:", leo_vi_id)

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
        id=leo_vi_id,
        rn="Leo VI the Wise",
        bkf="León VI el Sabio",
        c="GR",
        img=leo_vi_input["image_url"],
        occ="Emperador del Imperio Bizantino y legislador (autor de las Basílicas)",
        desc=leo_vi_input["description"],
    )

# 6. Conectar León VI -> Constantino VII (family.parent_of)
source_l6_c7 = repo.create(
    "sources",
    SourceInput(
        title="The Reign of Leo VI (866–912): Politics and People",
        url="https://brill.com/display/title/788",
        publisher="Brill / The Medieval Mediterranean",
        author="Shaun Tougher",
    ).model_dump(mode="json"),
)

fact_l6_c7 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=leo_vi_id,
            object_id=constantine_vii_id,
            source_id=source_l6_c7["id"],
            source_locator="Shaun Tougher, The Reign of Leo VI, cap. 6: Nascita nella porpora di Costantino VII il 18 maggio 905 da Leone VI e Zoe Carbonopsina",
            note=(
                "León VI el Sabio fue el padre de Constantino VII Porfirogéneta, nacido en la cámara púrpura el 18 de mayo de 905 "
                "de su matrimonio con Zoe Carbonopsina. León VI desafió la oposición eclesiástica a su cuarta boda para legitimar "
                "y asegurar la corona imperial a su único hijo varón."
            ),
            status="draft",
        ),
    ),
)
data_l6_c7 = {
    k: v
    for k, v in repo.get("facts", fact_l6_c7["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_l6_c7["status"] = "verified"
repo.update(
    "facts",
    fact_l6_c7["id"],
    fact_l6_c7["revision"],
    validate_fact(repo, data_l6_c7),
    "verify",
)
print("Hecho León VI -> Constantino VII verificado.")

# 7. Crear a Focio el Grande (Patriarca Photius)
photius_input = PersonInput(
    name="Focio el Grande",
    aliases=[
        "Photios I of Constantinople",
        "Patriarca Focio",
        "San Focio",
    ],
    description=(
        "Patriarca de Constantinopla (858–867, 877–886), estadista, diplomático y el mayor polímata y erudito del renacimiento bizantino del siglo IX. "
        "Maestro formativo de León VI el Sabio; autor de la 'Biblioteca' (Myriobiblos), recopilación enciclopédica fundamental "
        "que rescató y comentó cientos de obras perdidas de la filosofía, historia y literatura de la Antigüedad griega y romana."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/5/54/The_interrogation_of_Patriarch_Photios.jpg",
    wikidata_id="Q243144",
    birth=HistoricalDate(year=810, precision="year"),
    death=HistoricalDate(year=893, month=2, day=6, precision="day"),
).model_dump(mode="json")

photius = repo.create("people", photius_input)
photius_id = photius["id"]
print("Creado Focio el Grande con ID:", photius_id)

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
        id=photius_id,
        rn="Photios I of Constantinople",
        bkf="Focio el Grande",
        c="GR",
        img=photius_input["image_url"],
        occ="Patriarca de Constantinopla, filósofo y enciclopedista (autor de la Biblioteca/Myriobiblos)",
        desc=photius_input["description"],
    )

# 8. Conectar Focio el Grande -> León VI el Sabio (professional.mentor_of)
source_ph_l6 = repo.create(
    "sources",
    SourceInput(
        title="The Photian Schism: History and Legend",
        url="https://www.cambridge.org/core/books/photian-schism/01B52B7C83023BA1409C6381C4BA1F45",
        publisher="Cambridge University Press",
        author="Francis Dvornik",
    ).model_dump(mode="json"),
)

fact_ph_l6 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="professional.mentor_of",
            subject_id=photius_id,
            object_id=leo_vi_id,
            source_id=source_ph_l6["id"],
            source_locator="Francis Dvornik, The Photian Schism, cap. 8: Educazione del giovane principe Leone sotto il patriarca Fozio a Costantinopoli (875–886)",
            note=(
                "El patriarca Focio el Grande fue el tutor intelectual y maestro de retórica, filosofía clásica y dialéctica de León VI el Sabio "
                "en la corte de Constantinopla. La exhaustiva formación helenística impartida por Focio forjó la vocación de estadista, "
                "poeta y legislador que caracterizó el reinado de León VI."
            ),
            status="draft",
        ),
    ),
)
data_ph_l6 = {
    k: v
    for k, v in repo.get("facts", fact_ph_l6["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_ph_l6["status"] = "verified"
repo.update(
    "facts",
    fact_ph_l6["id"],
    fact_ph_l6["revision"],
    validate_fact(repo, data_ph_l6),
    "verify",
)
print("Hecho Focio el Grande -> León VI el Sabio verificado.")

# 9. Crear a Basilio I el Macedonio
basil_i_input = PersonInput(
    name="Basilio I el Macedonio",
    aliases=[
        "Basil I",
        "Basilio I",
        "El Fundador de la Dinastía Macedonia",
    ],
    description=(
        "Emperador del Imperio Bizantino (867–886) y fundador de la Dinastía Macedonia, la edad de oro medieval del Imperio. "
        "Inició la gran compilación legislativa griega (Prochiron y Epanagoge) culminada en las Basílicas, "
        "reorganizó la flota imperial y la administración militar, y fue padre del emperador León VI el Sabio."
    ),
    country="GR",
    city_born="Adrianópolis",
    image_url="https://upload.wikimedia.org/wikipedia/commons/3/37/MadridSkylitzesFol100vDetail.jpg",
    wikidata_id="Q41621",
    birth=HistoricalDate(year=811, precision="year"),
    death=HistoricalDate(year=886, month=8, day=29, precision="day"),
).model_dump(mode="json")

basil_i = repo.create("people", basil_i_input)
basil_i_id = basil_i["id"]
print("Creado Basilio I el Macedonio con ID:", basil_i_id)

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
        id=basil_i_id,
        rn="Basileios I Makedon",
        bkf="Basilio I el Macedonio",
        c="GR",
        img=basil_i_input["image_url"],
        occ="Emperador del Imperio Bizantino (Fundador de la Dinastía Macedonia)",
        desc=basil_i_input["description"],
    )

# 10. Conectar Basilio I -> León VI el Sabio (family.parent_of)
source_b1_l6 = repo.create(
    "sources",
    SourceInput(
        title="Vita Basilii: Theophanes Continuatus (Libro V)",
        url="https://www.degruyter.com/document/doi/10.1515/9783110294439/html",
        publisher="Corpus Scriptorum Historiae Byzantinae (CSHB), Bonn: Weber",
        author="Theophanes Continuatus (ed. Immanuel Bekker)",
    ).model_dump(mode="json"),
)

fact_b1_l6 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=basil_i_id,
            object_id=leo_vi_id,
            source_id=source_b1_l6["id"],
            source_locator="Vita Basilii, Libro V, cap. 38: Incoronazione del figlio Leone come co-imperatore a Santa Sofia il 6 gennaio 870",
            note=(
                "Basilio I el Macedonio fue el padre legal y dinástico de León VI el Sabio, nacido el 19 de septiembre de 866 "
                "de su matrimonio con la emperatriz Eudoxia Ingerina. Basilio I coronó solemnemente a León como su co-emperador y sucesor "
                "en la basílica de Santa Sofía el 6 de enero de 870."
            ),
            status="draft",
        ),
    ),
)
data_b1_l6 = {
    k: v
    for k, v in repo.get("facts", fact_b1_l6["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_b1_l6["status"] = "verified"
repo.update(
    "facts",
    fact_b1_l6["id"],
    fact_b1_l6["revision"],
    validate_fact(repo, data_b1_l6),
    "verify",
)
print("Hecho Basilio I -> León VI verificado.")

# Resumen de conexiones
print("\n--- Conexiones de Constantino VII ---")
print(json.dumps(connection_preview(repo, constantine_vii_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Basilio I ---")
print(json.dumps(connection_preview(repo, basil_i_id), indent=2, ensure_ascii=False))
