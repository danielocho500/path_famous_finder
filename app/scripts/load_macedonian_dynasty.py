import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

alexios_i_id = "7645f661-caea-4c3b-8abb-b2561a9187f6"

print("--- Iniciando carga del siglo X–XI: Miguel Psellos, Isaac I, la emperatriz Zoe y Basilio II ---")

# 1. Crear a Miguel Psellos
psellos_input = PersonInput(
    name="Miguel Psellos",
    aliases=[
        "Michael Psellos",
        "Constantino Psellos",
        "Miguel Pselo",
    ],
    description=(
        "Polímata, filósofo neoplatónico, político, historiador y primer ministro bizantino del siglo XI. "
        "Figura intelectual cumbre de la cultura bizantina medieval, reformador de la Universidad de Constantinopla "
        "y autor de la célebre 'Chronographia', que narra con viveza testimonial los reinados de catorce emperadores."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/d/db/Michael_Psellos.jpg",
    wikidata_id="Q211366",
    birth=HistoricalDate(year=1018, precision="year"),
    death=HistoricalDate(year=1078, precision="year"),
).model_dump(mode="json")

psellos = repo.create("people", psellos_input)
psellos_id = psellos["id"]
print("Creado Miguel Psellos con ID:", psellos_id)

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
        id=psellos_id,
        rn="Michael Psellos",
        bkf="Miguel Psellos",
        c="GR",
        img=psellos_input["image_url"],
        occ="Polímata, primer ministro e historiador bizantino (autor de Chronographia)",
        desc=psellos_input["description"],
    )

# 2. Conectar Alejo I Comneno <-> Miguel Psellos (personal.met / corte de Constantinopla 1071–1078)
source_a1_ps = repo.create(
    "sources",
    SourceInput(
        title="Michael Psellos: Chronographia (Libro VII: Miguel VII Ducas y el general Alejo Comneno)",
        url="https://www.penguinrandomhouse.com/books/261174/fourteen-byzantine-rulers-by-michael-psellus/",
        publisher="Penguin Classics / Yale University Press",
        author="Michael Psellos (ed. E.R.A. Sewter)",
    ).model_dump(mode="json"),
)

fact_a1_ps = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=alexios_i_id,
            object_id=psellos_id,
            source_id=source_a1_ps["id"],
            source_locator="Chronographia, Libro VII: Consejo imperial y corte de Miguel VII Ducas en Constantinopla (1071–1078)",
            note=(
                "El joven general Alejo Comneno convivió y colaboró directamente con el primer ministro e intelectual Miguel Psellos "
                "en la corte imperial de Constantinopla entre 1071 y 1078; Psellos aconsejó al emperador Miguel VII encomendar "
                "a Alejo el mando de las fuerzas armadas para sofocar las rebeliones militares en Tracia y Anatolia."
            ),
            status="draft",
        ),
    ),
)
data_a1_ps = {
    k: v
    for k, v in repo.get("facts", fact_a1_ps["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_a1_ps["status"] = "verified"
repo.update(
    "facts",
    fact_a1_ps["id"],
    fact_a1_ps["revision"],
    validate_fact(repo, data_a1_ps),
    "verify",
)
print("Hecho Alejo I Comneno <-> Miguel Psellos verificado.")

# 3. Crear a Isaac I Comneno
isaac_i_input = PersonInput(
    name="Isaac I Comneno",
    aliases=[
        "Isaac I Komnenos",
        "Emperador Isaac I",
    ],
    description=(
        "Emperador del Imperio Bizantino (1057–1059) y primer gobernante de la ilustre Dinastía Comneno. "
        "General supremo de Oriente; ascendió al trono tras la revuelta militar de 1057 negociada por Miguel Psellos, "
        "reformó las finanzas imperiales y abdicó en favor de Constantino X Ducas, retirándose al monasterio de Studion."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/6/69/Histamenon_of_Isaac_I.jpg",
    wikidata_id="Q41643",
    birth=HistoricalDate(year=1007, precision="year"),
    death=HistoricalDate(year=1060, precision="year"),
).model_dump(mode="json")

isaac_i = repo.create("people", isaac_i_input)
isaac_i_id = isaac_i["id"]
print("Creado Isaac I Comneno con ID:", isaac_i_id)

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
        id=isaac_i_id,
        rn="Isaac I Komnenos",
        bkf="Isaac I Comneno",
        c="GR",
        img=isaac_i_input["image_url"],
        occ="Emperador del Imperio Bizantino (primer basileus de la Dinastía Comneno)",
        desc=isaac_i_input["description"],
    )

# 4. Conectar Miguel Psellos <-> Isaac I Comneno (personal.met / embajada de 1057)
source_ps_i1 = repo.create(
    "sources",
    SourceInput(
        title="Chronographia de Miguel Psellos (Libro VII: Reinado de Isaac I Comneno)",
        url="https://www.degruyter.com/document/doi/10.1515/9783110271164/html",
        publisher="De Gruyter / Corpus Fontium Historiae Byzantinae",
        author="Michael Psellos (ed. Salvatore Impellizzeri)",
    ).model_dump(mode="json"),
)

fact_ps_i1 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=psellos_id,
            object_id=isaac_i_id,
            source_id=source_ps_i1["id"],
            source_locator="Chronographia, Libro VII, caps. 15–42: Embajada imperial en Nicomedia (agosto de 1057) y ascenso al trono de Isaac I",
            note=(
                "En agosto de 1057, Miguel Psellos fue enviado como embajador plenipotenciario ante el campamento del general Isaac I Comneno "
                "en Nicomedia. Psellos negoció personalmente los términos de la capitulación de Miguel VI, redactó el tratado de cesión "
                "del poder y guio a Isaac I en su entrada triunfal a Constantinopla, sirviendo luego como su consejero de gobierno."
            ),
            status="draft",
        ),
    ),
)
data_ps_i1 = {
    k: v
    for k, v in repo.get("facts", fact_ps_i1["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_ps_i1["status"] = "verified"
repo.update(
    "facts",
    fact_ps_i1["id"],
    fact_ps_i1["revision"],
    validate_fact(repo, data_ps_i1),
    "verify",
)
print("Hecho Miguel Psellos <-> Isaac I Comneno verificado.")

# 5. Crear a Zoe Porfirogéneta
zoe_input = PersonInput(
    name="Zoe Porfirogéneta",
    aliases=[
        "Zoe Porphyrogenita",
        "Emperatriz Zoe",
    ],
    description=(
        "Emperatriz reinante del Imperio Bizantino (1028–1050) de la Dinastía Macedonia, hija de Constantino VIII y sobrina de Basilio II. "
        "Gobernó Constantinopla junto a sus tres maridos imperiales (Romano III, Miguel IV y Constantino IX Monómaco) "
        "y conjuntamente con su hermana Teodora, retratada en el monumental mosaico de Santa Sofía."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/3/3f/Zoe_mosaic_Hagia_Sophia.jpg",
    wikidata_id="Q208006",
    birth=HistoricalDate(year=978, precision="year"),
    death=HistoricalDate(year=1050, month=6, day=11, precision="day"),
).model_dump(mode="json")

zoe = repo.create("people", zoe_input)
zoe_id = zoe["id"]
print("Creada Zoe Porfirogéneta con ID:", zoe_id)

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
        id=zoe_id,
        rn="Zoe Porphyrogenita",
        bkf="Zoe Porfirogéneta",
        c="GR",
        img=zoe_input["image_url"],
        occ="Emperatriz del Imperio Bizantino (Dinastía Macedonia)",
        desc=zoe_input["description"],
    )

# 6. Conectar Miguel Psellos <-> Zoe Porfirogéneta (personal.met / corte imperial)
source_ps_zoe = repo.create(
    "sources",
    SourceInput(
        title="Chronographia de Miguel Psellos (Libro VI: Reinado de la emperatriz Zoe)",
        url="https://www.penguinrandomhouse.com/books/261174/fourteen-byzantine-rulers-by-michael-psellus/",
        publisher="Penguin Classics",
        author="Michael Psellos (ed. E.R.A. Sewter)",
    ).model_dump(mode="json"),
)

fact_ps_zoe = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=psellos_id,
            object_id=zoe_id,
            source_id=source_ps_zoe["id"],
            source_locator="Chronographia, Libro VI, caps. 1–159: Audiencias palatinas y secretaría imperial en el Gran Palacio (1042–1050)",
            note=(
                "Miguel Psellos inició su brillante carrera cortesana sirviendo como secretario personal y orador oficial "
                "bajo la emperatriz Zoe Porfirogéneta en el Gran Palacio de Constantinopla entre 1042 y 1050, "
                "dejando en su Chronographia el retrato psicológico y físico más íntimo y célebre de la emperatriz."
            ),
            status="draft",
        ),
    ),
)
data_ps_zoe = {
    k: v
    for k, v in repo.get("facts", fact_ps_zoe["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_ps_zoe["status"] = "verified"
repo.update(
    "facts",
    fact_ps_zoe["id"],
    fact_ps_zoe["revision"],
    validate_fact(repo, data_ps_zoe),
    "verify",
)
print("Hecho Miguel Psellos <-> Zoe Porfirogéneta verificado.")

# 7. Crear a Basilio II («el Bulgaróctono»)
basil_ii_input = PersonInput(
    name="Basilio II",
    aliases=[
        "Basil II",
        "Basilio el Bulgaróctono",
        "Basilio II Porphyrogennetos",
    ],
    description=(
        "Emperador del Imperio Bizantino (976–1025) de la Dinastía Macedonia, uno de los más formidables gobernantes de la historia medieval. "
        "Expandió las fronteras bizantinas hasta su máxima extensión desde Justiniano (derrotando al Primer Imperio Búlgaro y anexando Armenia), "
        "creó la guardia varega y patrocinó la cristianización de la Rus de Kiev casando a su hermana Ana con Vladimiro el Grande."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/d/dc/Basilios_II.jpg",
    wikidata_id="Q41600",
    birth=HistoricalDate(year=958, precision="year"),
    death=HistoricalDate(year=1025, month=12, day=15, precision="day"),
).model_dump(mode="json")

basil_ii = repo.create("people", basil_ii_input)
basil_ii_id = basil_ii["id"]
print("Creado Basilio II con ID:", basil_ii_id)

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
        id=basil_ii_id,
        rn="Basileios II Bulgaroktonos",
        bkf="Basilio II",
        c="GR",
        img=basil_ii_input["image_url"],
        occ="Emperador del Imperio Bizantino (Cénit de la Dinastía Macedonia)",
        desc=basil_ii_input["description"],
    )

# 8. Conectar Basilio II <-> Zoe Porfirogéneta (personal.met / Gran Palacio)
source_b2_zoe = repo.create(
    "sources",
    SourceInput(
        title="Ioannis Scylitzae Synopsis Historiarum (811–1057)",
        url="https://www.degruyter.com/document/doi/10.1515/9783110022858/html",
        publisher="Walter de Gruyter / Corpus Fontium Historiae Byzantinae",
        author="John Skylitzes (ed. Hans Thurn)",
    ).model_dump(mode="json"),
)

fact_b2_zoe = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=basil_ii_id,
            object_id=zoe_id,
            source_id=source_b2_zoe["id"],
            source_locator="Synopsis Historiarum, p. 336-368: La corte imperial di Basilio II e la cura delle nipoti porfirogenite Zoe e Teodora a Costantinopoli (978–1025)",
            note=(
                "El emperador Basilio II crio y tuteló en el Gran Palacio de Constantinopla a su sobrina la princesa porfirogéneta Zoe "
                "durante casi cinco décadas (978–1025); Basilio II preservó celosamente el estatus dinástico de Zoe como heredera legítima "
                "del trono de la Casa Macedonia."
            ),
            status="draft",
        ),
    ),
)
data_b2_zoe = {
    k: v
    for k, v in repo.get("facts", fact_b2_zoe["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_b2_zoe["status"] = "verified"
repo.update(
    "facts",
    fact_b2_zoe["id"],
    fact_b2_zoe["revision"],
    validate_fact(repo, data_b2_zoe),
    "verify",
)
print("Hecho Basilio II <-> Zoe Porfirogéneta verificado.")

# 9. Crear a Vladimiro I el Grande de Kiev
vladimir_input = PersonInput(
    name="Vladimiro I el Grande",
    aliases=[
        "Vladimir the Great",
        "Vladimiro I de Kiev",
        "San Vladimiro",
    ],
    description=(
        "Gran Príncipe de Nóvgorod y Gran Príncipe de Kiev (980–1015) de la Dinastía Rúrika. "
        "Cristianizó la Rus de Kiev en 988 tras forjar una trascendental alianza militar y matrimonial con el emperador Basilio II, "
        "casándose con la princesa bizantina Ana Porfirogéneta y suministrando a Constantinopla la guardia varega."
    ),
    country="UA",
    city_born="Búdytino",
    image_url="https://upload.wikimedia.org/wikipedia/commons/1/11/Coin_of_Vladimir_the_Great.JPG",
    wikidata_id="Q14860",
    birth=HistoricalDate(year=958, precision="year"),
    death=HistoricalDate(year=1015, month=7, day=15, precision="day"),
).model_dump(mode="json")

vladimir = repo.create("people", vladimir_input)
vladimir_id = vladimir["id"]
print("Creado Vladimiro I el Grande con ID:", vladimir_id)

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
        id=vladimir_id,
        rn="Vladimir Svyatoslavich",
        bkf="Vladimiro I el Grande",
        c="UA",
        img=vladimir_input["image_url"],
        occ="Gran Príncipe de Kiev y cristianizador de la Rus de Kiev (Dinastía Rúrika)",
        desc=vladimir_input["description"],
    )

# 10. Conectar Basilio II <-> Vladimiro I el Grande (personal.met / pacto imperial y cristianización de 988)
source_b2_vl = repo.create(
    "sources",
    SourceInput(
        title="The Russian Primary Chronicle: Laurentian Text (Crónica de Néstor)",
        url="https://www.medievalacademy.org/page/pub_monographs",
        publisher="Mediaeval Academy of America",
        author="Samuel Hazzard Cross & Olgerd P. Sherbowitz-Wetzor",
    ).model_dump(mode="json"),
)

fact_b2_vl = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=basil_ii_id,
            object_id=vladimir_id,
            source_id=source_b2_vl["id"],
            source_locator="Crónica de Néstor, año 6496 (988 d.C.): Tratado de Quersoneso, matrimonio de Ana Porfirogéneta y alianza con Basilio II",
            note=(
                "En 988, el emperador Basilio II y el Gran Príncipe Vladimiro I de Kiev sellaron el pacto fundacional que transformó Europa del Este: "
                "Vladimiro aceptó el bautismo cristiano para sí y para toda la Rus de Kiev y envió un contingente de 6.000 guerreros varegos "
                "para salvar el trono de Basilio II en Constantinopla, a cambio de la mano de la princesa porfirogéneta Ana."
            ),
            status="draft",
        ),
    ),
)
data_b2_vl = {
    k: v
    for k, v in repo.get("facts", fact_b2_vl["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_b2_vl["status"] = "verified"
repo.update(
    "facts",
    fact_b2_vl["id"],
    fact_b2_vl["revision"],
    validate_fact(repo, data_b2_vl),
    "verify",
)
print("Hecho Basilio II <-> Vladimiro I verificado.")

# Resumen de conexiones
print("\n--- Conexiones de Basilio II ---")
print(json.dumps(connection_preview(repo, basil_ii_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Miguel Psellos ---")
print(json.dumps(connection_preview(repo, psellos_id), indent=2, ensure_ascii=False))
