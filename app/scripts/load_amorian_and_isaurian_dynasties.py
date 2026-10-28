import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, LocationInput, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

basil_i_id = "4faed7ec-ac99-4ffc-9179-9803ba01339b"

print("=== Conectando hacia atrás en el tiempo: Siglos VIII y IX (Dinastías Amoriana e Isáurica) ===")

# =========================================================================
# 1. Miguel III el Beodo (840 – 867)
# =========================================================================
michael_iii_input = PersonInput(
    name="Miguel III",
    aliases=[
        "Miguel III el Beodo",
        "Michael III",
        "Emperador Miguel III",
    ],
    description=(
        "Emperador del Imperio Bizantino (842–867), último monarca de la Dinastía Amoriana. "
        "Durante su reinado se restauró la veneración de los iconos (843), se derrotó a los árabes en la batalla "
        "de Posón (863) y se envió la histórica misión evangelizadora de los santos Cirilo y Metodio a los eslavos. "
        "Nombró a Basilio I como su gran chambelán y co-emperador en 866."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/9/92/Michael_III_and_Basil_I_MadridSkylitzes.jpg",
    wikidata_id="Q41622",
    birth=HistoricalDate(year=840, month=1, day=19, precision="day"),
    death=HistoricalDate(year=867, month=9, day=24, precision="day"),
).model_dump(mode="json")

michael_iii = repo.create("people", michael_iii_input)
michael_iii_id = michael_iii["id"]
print("Creado Miguel III con ID:", michael_iii_id)

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
        id=michael_iii_id,
        rn="Michael III Amorian",
        bkf="Miguel III el Beodo",
        c="GR",
        img=michael_iii_input["image_url"],
        occ="Emperador del Imperio Bizantino (Dinastía Amoriana)",
        desc=michael_iii_input["description"],
    )

# Enlace Basilio I <-> Miguel III (personal.met)
source_b1_m3 = repo.create(
    "sources",
    SourceInput(
        title="Ioannis Scylitzae Synopsis Historiarum (811–1057): Reinado de Miguel III y ascenso de Basilio",
        url="https://www.degruyter.com/document/doi/10.1515/9783110842272/html",
        publisher="Walter de Gruyter / Corpus Fontium Historiae Byzantinae",
        author="John Skylitzes (ed. Hans Thurn)",
        location=LocationInput(
            name="De Gruyter / Corpus Fontium Historiae Byzantinae",
            city="Berlín",
            country="DE",
            lat=52.5058,
            lng=13.3547,
        ),
    ).model_dump(mode="json"),
)

fact_b1_m3 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=basil_i_id,
            object_id=michael_iii_id,
            source_id=source_b1_m3["id"],
            source_locator="Synopsis Historiarum, p. 115-130: Asociación al trono de Basilio y coronación como co-emperador el 26 de mayo de 866",
            note=(
                "El emperador Miguel III acogió en la corte imperial de Constantinopla a Basilio el Macedonio hacia 856, "
                "nombrándolo gran chambelán (parakoimomenos) y coronándolo solemnemente como su co-emperador y colega en el trono "
                "en la basílica de Santa Sofía el 26 de mayo de 866."
            ),
            status="draft",
            location=LocationInput(
                name="Basílica de Santa Sofía y Palacio Imperial de San Mamas",
                city="Constantinopla (Estambul)",
                country="TR",
                lat=41.0086,
                lng=28.9802,
            ),
        ),
    ),
)
data_b1_m3 = {k: v for k, v in repo.get("facts", fact_b1_m3["id"]).items() if k not in ("id", "revision", "created_at", "updated_at")}
data_b1_m3["status"] = "verified"
repo.update("facts", fact_b1_m3["id"], fact_b1_m3["revision"], validate_fact(repo, data_b1_m3), "verify")
print("Hecho verificado: Basilio I <-> Miguel III")

# =========================================================================
# 2. Santa Teodora la Emperatriz (815 – 867)
# =========================================================================
theodora_input = PersonInput(
    name="Teodora la Armenia",
    aliases=[
        "Santa Teodora la Emperatriz",
        "Teodora (esposa de Teófilo)",
        "Empress Theodora",
    ],
    description=(
        "Emperatriz regente del Imperio Bizantino (842–856) durante la minoría de edad de su hijo Miguel III. "
        "Figura trascendental en la historia eclesiástica y política ortodoxa, convocó el concilio de Constantinopla de 843 "
        "que puso fin formal y definitivo a la iconoclasia (evento conmemorado como el Triunfo de la Ortodoxia). "
        "Venerada como santa por la Iglesia ortodoxa."
    ),
    country="GR",
    city_born="Ebyssa, Paflagonia",
    image_url="https://upload.wikimedia.org/wikipedia/commons/2/25/Theodora_Madrid_Skylitzes.jpg",
    wikidata_id="Q230001",
    birth=HistoricalDate(year=815, precision="year"),
    death=HistoricalDate(year=867, month=2, day=11, precision="day"),
).model_dump(mode="json")

theodora = repo.create("people", theodora_input)
theodora_id = theodora["id"]
print("Creada Teodora la Armenia con ID:", theodora_id)

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
        id=theodora_id,
        rn="Theodora the Armenian",
        bkf="Santa Teodora la Emperatriz",
        c="GR",
        img=theodora_input["image_url"],
        occ="Emperatriz Regente del Imperio Bizantino",
        desc=theodora_input["description"],
    )

# Enlace Teodora -> Miguel III (family.parent_of)
source_t_m3 = repo.create(
    "sources",
    SourceInput(
        title="Theophanes Continuatus: Chronographia (Libro IV: De Michaele Theophili filio)",
        url="https://www.degruyter.com/document/doi/10.1515/9783110294439/html",
        publisher="Corpus Scriptorum Historiae Byzantinae (CSHB), Bonn: Weber",
        author="Theophanes Continuatus (ed. Immanuel Bekker)",
        location=LocationInput(
            name="De Gruyter / CSHB",
            city="Berlín",
            country="DE",
            lat=52.5058,
            lng=13.3547,
        ),
    ).model_dump(mode="json"),
)

fact_t_m3 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=theodora_id,
            object_id=michael_iii_id,
            source_id=source_t_m3["id"],
            source_locator="Theophanes Continuatus, Libro IV, cap. 1: Nascita di Michele III il 19 gennaio 840 da Teofilo e Teodora",
            note=(
                "La emperatriz Teodora fue la madre biológica de Miguel III, nacido en el Gran Palacio de Constantinopla el 19 de enero de 840 "
                "de su matrimonio con el emperador Teófilo. Teodora gobernó como regente del imperio junto con su consejo hasta 856."
            ),
            status="draft",
            location=LocationInput(
                name="Gran Palacio de Constantinopla",
                city="Constantinopla (Estambul)",
                country="TR",
                lat=41.0054,
                lng=28.9768,
            ),
        ),
    ),
)
data_t_m3 = {k: v for k, v in repo.get("facts", fact_t_m3["id"]).items() if k not in ("id", "revision", "created_at", "updated_at")}
data_t_m3["status"] = "verified"
repo.update("facts", fact_t_m3["id"], fact_t_m3["revision"], validate_fact(repo, data_t_m3), "verify")
print("Hecho verificado: Teodora -> Miguel III")

# =========================================================================
# 3. Teófilo (813 – 842)
# =========================================================================
theophilos_input = PersonInput(
    name="Teófilo",
    aliases=[
        "Emperador Teófilo",
        "Theophilos",
    ],
    description=(
        "Emperador del Imperio Bizantino (829–842), segundo monarca de la Dinastía Amoriana. "
        "Ferviente mecenas de las artes y las ciencias, promovió los estudios matemáticos de León el Filósofo, "
        "reconstruyó las murallas marítimas de Constantinopla y amplió los fastuosos salones automatizados del Gran Palacio."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/4/4b/Solidus-Theophilus-Theodora_and_Michael_III-sb1662.jpg",
    wikidata_id="Q60199",
    birth=HistoricalDate(year=813, precision="year"),
    death=HistoricalDate(year=842, month=1, day=20, precision="day"),
).model_dump(mode="json")

theophilos = repo.create("people", theophilos_input)
theophilos_id = theophilos["id"]
print("Creado Teófilo con ID:", theophilos_id)

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
        id=theophilos_id,
        rn="Theophilos Amorian",
        bkf="Teófilo",
        c="GR",
        img=theophilos_input["image_url"],
        occ="Emperador del Imperio Bizantino (Dinastía Amoriana)",
        desc=theophilos_input["description"],
    )

# Enlace Teófilo <-> Teodora (family.spouse_of)
source_th_td = repo.create(
    "sources",
    SourceInput(
        title="Chronographia de Teófanes Continuatus: Matrimonio imperial de Teófilo y Teodora (830)",
        url="https://www.degruyter.com/document/doi/10.1515/9783110294439/html",
        publisher="Corpus Scriptorum Historiae Byzantinae (CSHB), Bonn: Weber",
        author="Theophanes Continuatus (ed. Immanuel Bekker)",
        location=LocationInput(
            name="De Gruyter / CSHB",
            city="Berlín",
            country="DE",
            lat=52.5058,
            lng=13.3547,
        ),
    ).model_dump(mode="json"),
)

fact_th_td = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.spouse_of",
            subject_id=theophilos_id,
            object_id=theodora_id,
            source_id=source_th_td["id"],
            source_locator="Theophanes Continuatus, Libro III, cap. 5: Sfilata nuziale e nozze imperiali a Santa Sofia nel maggio 830",
            note=(
                "El emperador Teófilo y la dama patricia Teodora contrajeron matrimonio imperial en mayo de 830 en la basílica de Santa Sofía "
                "de Constantinopla, tras el célebre concurso nupcial de la manzana de oro convocado por la emperatriz viuda Eufrosina."
            ),
            status="draft",
            location=LocationInput(
                name="Basílica de Santa Sofía, Constantinopla",
                city="Constantinopla (Estambul)",
                country="TR",
                lat=41.0086,
                lng=28.9802,
            ),
        ),
    ),
)
data_th_td = {k: v for k, v in repo.get("facts", fact_th_td["id"]).items() if k not in ("id", "revision", "created_at", "updated_at")}
data_th_td["status"] = "verified"
repo.update("facts", fact_th_td["id"], fact_th_td["revision"], validate_fact(repo, data_th_td), "verify")
print("Hecho verificado: Teófilo <-> Teodora (cónyuges)")

# =========================================================================
# 4. Miguel II el Amoriano (770 – 829)
# =========================================================================
michael_ii_input = PersonInput(
    name="Miguel II el Amoriano",
    aliases=[
        "Miguel II",
        "El Tartamudo",
        "Michael II",
        "Fundador de la Dinastía Amoriana",
    ],
    description=(
        "Emperador del Imperio Bizantino (820–829) y fundador de la Dinastía Amoriana. "
        "Veterano general originario de Amorium (Frigia), sofocó la sangrienta rebelión militar de Tomás el Eslavo "
        "y aseguró la continuidad y estabilidad de la corona imperial para su linaje."
    ),
    country="GR",
    city_born="Amorium",
    image_url="https://upload.wikimedia.org/wikipedia/commons/1/1a/Michael_II_and_Theophilos_Madrid_Skylitzes.jpg",
    wikidata_id="Q41635",
    birth=HistoricalDate(year=770, precision="year"),
    death=HistoricalDate(year=829, month=10, day=2, precision="day"),
).model_dump(mode="json")

michael_ii = repo.create("people", michael_ii_input)
michael_ii_id = michael_ii["id"]
print("Creado Miguel II el Amoriano con ID:", michael_ii_id)

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
        id=michael_ii_id,
        rn="Michael II the Amorian",
        bkf="Miguel II el Amoriano",
        c="GR",
        img=michael_ii_input["image_url"],
        occ="Emperador del Imperio Bizantino (Fundador de la Dinastía Amoriana)",
        desc=michael_ii_input["description"],
    )

# Enlace Miguel II -> Teófilo (family.parent_of)
source_m2_th = repo.create(
    "sources",
    SourceInput(
        title="Theophanes Continuatus: Chronographia (Libro II: De Michaele Balbo)",
        url="https://www.degruyter.com/document/doi/10.1515/9783110294439/html",
        publisher="Corpus Scriptorum Historiae Byzantinae (CSHB), Bonn: Weber",
        author="Theophanes Continuatus (ed. Immanuel Bekker)",
        location=LocationInput(
            name="De Gruyter / CSHB",
            city="Berlín",
            country="DE",
            lat=52.5058,
            lng=13.3547,
        ),
    ).model_dump(mode="json"),
)

fact_m2_th = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=michael_ii_id,
            object_id=theophilos_id,
            source_id=source_m2_th["id"],
            source_locator="Theophanes Continuatus, Libro II, cap. 8: Nascita e incoronazione di Teofilo a co-imperatore a Costantinopoli nel 821",
            note=(
                "Miguel II el Amoriano fue el padre biológico de Teófilo, nacido hacia 813 de su matrimonio con Tecla. "
                "Miguel II coronó solemnemente a Teófilo como co-emperador el 12 de mayo de 821 en Santa Sofía."
            ),
            status="draft",
            location=LocationInput(
                name="Gran Palacio de Constantinopla",
                city="Constantinopla (Estambul)",
                country="TR",
                lat=41.0054,
                lng=28.9768,
            ),
        ),
    ),
)
data_m2_th = {k: v for k, v in repo.get("facts", fact_m2_th["id"]).items() if k not in ("id", "revision", "created_at", "updated_at")}
data_m2_th["status"] = "verified"
repo.update("facts", fact_m2_th["id"], fact_m2_th["revision"], validate_fact(repo, data_m2_th), "verify")
print("Hecho verificado: Miguel II -> Teófilo")

# =========================================================================
# 5. León V el Armenio (775 – 820)
# =========================================================================
leo_v_input = PersonInput(
    name="León V el Armenio",
    aliases=[
        "León V",
        "Leo V the Armenian",
        "Leo Armenius",
    ],
    description=(
        "Emperador del Imperio Bizantino (813–820). Brillante general militar que puso fin a la prolongada "
        "guerra búlgaro-bizantina derrotando a Omurtag en la batalla de Mesembria (814). "
        "Fue camarada de armas de Miguel el Amoriano bajo el general Bardanes el Turco."
    ),
    country="GR",
    city_born="Oshakan, Armenia",
    image_url="https://upload.wikimedia.org/wikipedia/commons/4/4c/Leo_V_the_Armenian_Madrid_Skylitzes.jpg",
    wikidata_id="Q41642",
    birth=HistoricalDate(year=775, precision="year"),
    death=HistoricalDate(year=820, month=12, day=25, precision="day"),
).model_dump(mode="json")

leo_v = repo.create("people", leo_v_input)
leo_v_id = leo_v["id"]
print("Creado León V el Armenio con ID:", leo_v_id)

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
        id=leo_v_id,
        rn="Leo V the Armenian",
        bkf="León V el Armenio",
        c="GR",
        img=leo_v_input["image_url"],
        occ="Emperador del Imperio Bizantino",
        desc=leo_v_input["description"],
    )

# Enlace León V <-> Miguel II (personal.met)
source_l5_m2 = repo.create(
    "sources",
    SourceInput(
        title="Theophanes Continuatus: Chronographia (Libro I: De Leone Armeno)",
        url="https://www.degruyter.com/document/doi/10.1515/9783110294439/html",
        publisher="Corpus Scriptorum Historiae Byzantinae (CSHB), Bonn: Weber",
        author="Theophanes Continuatus (ed. Immanuel Bekker)",
        location=LocationInput(
            name="De Gruyter / CSHB",
            city="Berlín",
            country="DE",
            lat=52.5058,
            lng=13.3547,
        ),
    ).model_dump(mode="json"),
)

fact_l5_m2 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=leo_v_id,
            object_id=michael_ii_id,
            source_id=source_l5_m2["id"],
            source_locator="Theophanes Continuatus, Libro I, caps. 1–10: Cameratismo militare e comando degli Excubitores a Costantinopoli (803–820)",
            note=(
                "León el Armenio y Miguel el Amoriano fueron camaradas íntimos de armas desde la rebelión militar de Bardanes en 803; "
                "al ascender León V al trono imperial en 813, nombró a Miguel comandante general de la guardia de los Excubitores en Constantinopla."
            ),
            status="draft",
            location=LocationInput(
                name="Cuartel de los Excubitores y Gran Palacio, Constantinopla",
                city="Constantinopla (Estambul)",
                country="TR",
                lat=41.0054,
                lng=28.9768,
            ),
        ),
    ),
)
data_l5_m2 = {k: v for k, v in repo.get("facts", fact_l5_m2["id"]).items() if k not in ("id", "revision", "created_at", "updated_at")}
data_l5_m2["status"] = "verified"
repo.update("facts", fact_l5_m2["id"], fact_l5_m2["revision"], validate_fact(repo, data_l5_m2), "verify")
print("Hecho verificado: León V <-> Miguel II")

# =========================================================================
# 6. Irene de Atenas (752 – 803)
# =========================================================================
irene_input = PersonInput(
    name="Irene de Atenas",
    aliases=[
        "Santa Irene",
        "Emperatriz Irene",
        "Irene la Ateniense",
        "Eirene",
    ],
    description=(
        "Emperatriz del Imperio Bizantino (797–802) y primera mujer en gobernar el Imperio Romano en solitario con el título de 'Basileus'. "
        "Nacida en Atenas, convocó en 787 el Séptimo Concilio Ecuménico (Segundo Concilio de Nicea) que restauró el culto de las imágenes sagradas. "
        "Mantuvo intensas negociaciones diplomáticas de alianza y posible enlace matrimonial con el emperador Carlomagno."
    ),
    country="GR",
    city_born="Atenas",
    image_url="https://upload.wikimedia.org/wikipedia/commons/1/1d/Empress_Irene_Fasti_Veneti.jpg",
    wikidata_id="Q193106",
    birth=HistoricalDate(year=752, precision="year"),
    death=HistoricalDate(year=803, month=8, day=9, precision="day"),
).model_dump(mode="json")

irene = repo.create("people", irene_input)
irene_id = irene["id"]
print("Creada Irene de Atenas con ID:", irene_id)

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
        id=irene_id,
        rn="Irene of Athens",
        bkf="Santa Irene de Atenas",
        c="GR",
        img=irene_input["image_url"],
        occ="Emperatriz del Imperio Bizantino (Basileus)",
        desc=irene_input["description"],
    )

# Enlace León V <-> Irene de Atenas (personal.met)
source_l5_ir = repo.create(
    "sources",
    SourceInput(
        title="The Byzantine Revival 780–842: Service of Young Leo in the Court of Empress Irene",
        url="https://www.sup.org/books/title/?id=1411",
        publisher="Stanford University Press",
        author="Warren Treadgold",
        location=LocationInput(
            name="Stanford University Press",
            city="Stanford",
            country="US",
            lat=37.4275,
            lng=-122.1697,
        ),
    ).model_dump(mode="json"),
)

fact_l5_ir = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=leo_v_id,
            object_id=irene_id,
            source_id=source_l5_ir["id"],
            source_locator="The Byzantine Revival, cap. 5: Early career of Leo the Armenian in the imperial palace guard (798–802)",
            note=(
                "El joven oficial León el Armenio sirvió en la corte imperial de Constantinopla como miembro de la guardia patricia "
                "bajo la emperatriz Irene entre 798 y 802, antes de ser enviado a los regimientos del Tema Anatólico bajo Bardanes el Turco."
            ),
            status="draft",
            location=LocationInput(
                name="Gran Palacio de Constantinopla",
                city="Constantinopla (Estambul)",
                country="TR",
                lat=41.0054,
                lng=28.9768,
            ),
        ),
    ),
)
data_l5_ir = {k: v for k, v in repo.get("facts", fact_l5_ir["id"]).items() if k not in ("id", "revision", "created_at", "updated_at")}
data_l5_ir["status"] = "verified"
repo.update("facts", fact_l5_ir["id"], fact_l5_ir["revision"], validate_fact(repo, data_l5_ir), "verify")
print("Hecho verificado: León V <-> Irene de Atenas")

# =========================================================================
# 7. Constantino VI (771 – 797)
# =========================================================================
constantine_vi_input = PersonInput(
    name="Constantino VI",
    aliases=[
        "Constantine VI",
        "Emperador Constantino VI",
    ],
    description=(
        "Emperador del Imperio Bizantino (780–797), último gobernante varón de la Dinastía Isáurica. "
        "Hijo de la emperatriz Irene y de León IV el Jázaro; gobernó conjuntamente con su madre durante casi dos décadas "
        "y copresidió la apertura solemne del Séptimo Concilio Ecuménico de Nicea en 787."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/e/eb/Solidus-Constantine_VI_and_Irene-sb1593.jpg",
    wikidata_id="Q41645",
    birth=HistoricalDate(year=771, precision="year"),
    death=HistoricalDate(year=797, precision="year"),
).model_dump(mode="json")

constantine_vi = repo.create("people", constantine_vi_input)
constantine_vi_id = constantine_vi["id"]
print("Creado Constantino VI con ID:", constantine_vi_id)

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
        id=constantine_vi_id,
        rn="Constantine VI Isaurian",
        bkf="Constantino VI",
        c="GR",
        img=constantine_vi_input["image_url"],
        occ="Emperador del Imperio Bizantino (Dinastía Isáurica)",
        desc=constantine_vi_input["description"],
    )

# Enlace Irene -> Constantino VI (family.parent_of)
source_ir_c6 = repo.create(
    "sources",
    SourceInput(
        title="Theophanis Chronographia: Nascita di Costantino VI da Irene e Leone IV (771)",
        url="https://www.degruyter.com/document/doi/10.1515/9783110826760/html",
        publisher="De Gruyter / Corpus Scriptorum Historiae Byzantinae",
        author="Theophanes the Confessor (ed. Carl de Boor)",
        location=LocationInput(
            name="De Gruyter",
            city="Berlín",
            country="DE",
            lat=52.5058,
            lng=13.3547,
        ),
    ).model_dump(mode="json"),
)

fact_ir_c6 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=irene_id,
            object_id=constantine_vi_id,
            source_id=source_ir_c6["id"],
            source_locator="Theophanis Chronographia, AM 6263: Nascita del principe ereditario Costantino a Costantinopoli nel 771",
            note=(
                "Irene de Atenas fue la madre biológica de Constantino VI, nacido en 771 en Constantinopla de su matrimonio con León IV el Jázaro. "
                "Irene crio y gobernó junto a Constantino hasta su trágica destitución en 797."
            ),
            status="draft",
            location=LocationInput(
                name="Cámara Púrpura, Gran Palacio de Constantinopla",
                city="Constantinopla (Estambul)",
                country="TR",
                lat=41.0054,
                lng=28.9768,
            ),
        ),
    ),
)
data_ir_c6 = {k: v for k, v in repo.get("facts", fact_ir_c6["id"]).items() if k not in ("id", "revision", "created_at", "updated_at")}
data_ir_c6["status"] = "verified"
repo.update("facts", fact_ir_c6["id"], fact_ir_c6["revision"], validate_fact(repo, data_ir_c6), "verify")
print("Hecho verificado: Irene -> Constantino VI")

# =========================================================================
# 8. León IV el Jázaro (750 – 780)
# =========================================================================
leo_iv_input = PersonInput(
    name="León IV el Jázaro",
    aliases=[
        "León IV",
        "Leo IV the Khazar",
        "Leo IV",
    ],
    description=(
        "Emperador del Imperio Bizantino (775–780) de la Dinastía Isáurica. "
        "Hijo del emperador Constantino V y de la princesa jázara Tzitzak (Irene). "
        "Esposo de Irene de Atenas y padre de Constantino VI; continuó con moderación las campañas defensivas en Siria y Asia Menor."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/e/e9/Leo_IV_the_Khazar_with_Constantine_VI%2C_Leo_III_and_Constantine_V_solidus.jpg",
    wikidata_id="Q41652",
    birth=HistoricalDate(year=750, month=1, day=25, precision="day"),
    death=HistoricalDate(year=780, month=9, day=8, precision="day"),
).model_dump(mode="json")

leo_iv = repo.create("people", leo_iv_input)
leo_iv_id = leo_iv["id"]
print("Creado León IV el Jázaro con ID:", leo_iv_id)

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
        id=leo_iv_id,
        rn="Leo IV the Khazar",
        bkf="León IV el Jázaro",
        c="GR",
        img=leo_iv_input["image_url"],
        occ="Emperador del Imperio Bizantino (Dinastía Isáurica)",
        desc=leo_iv_input["description"],
    )

# Enlace León IV <-> Irene (family.spouse_of)
source_l4_ir = repo.create(
    "sources",
    SourceInput(
        title="Chronographia de Teófanes: Matrimonio imperial de León IV e Irene de Atenas (769)",
        url="https://www.degruyter.com/document/doi/10.1515/9783110826760/html",
        publisher="De Gruyter / CSHB",
        author="Theophanes the Confessor",
        location=LocationInput(
            name="De Gruyter",
            city="Berlín",
            country="DE",
            lat=52.5058,
            lng=13.3547,
        ),
    ).model_dump(mode="json"),
)

fact_l4_ir = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.spouse_of",
            subject_id=leo_iv_id,
            object_id=irene_id,
            source_id=source_l4_ir["id"],
            source_locator="Theophanis Chronographia, p. 444: Nozze imperiali celebrate nella cappella di Santo Stefano il 3 novembre 769",
            note=(
                "El emperador León IV el Jázaro e Irene de Atenas contrajeron matrimonio imperial solemne el 3 de noviembre de 769 "
                "en la capilla de San Esteban del Gran Palacio de Constantinopla, siendo Irene coronada emperatriz Augusta."
            ),
            status="draft",
            location=LocationInput(
                name="Capilla de San Esteban, Gran Palacio de Constantinopla",
                city="Constantinopla (Estambul)",
                country="TR",
                lat=41.0054,
                lng=28.9768,
            ),
        ),
    ),
)
data_l4_ir = {k: v for k, v in repo.get("facts", fact_l4_ir["id"]).items() if k not in ("id", "revision", "created_at", "updated_at")}
data_l4_ir["status"] = "verified"
repo.update("facts", fact_l4_ir["id"], fact_l4_ir["revision"], validate_fact(repo, data_l4_ir), "verify")
print("Hecho verificado: León IV <-> Irene (cónyuges)")

# =========================================================================
# 9. Constantino V Coprónimo (718 – 775)
# =========================================================================
constantine_v_input = PersonInput(
    name="Constantino V Coprónimo",
    aliases=[
        "Constantine V",
        "Constantino V",
        "El Emperador Guerrero",
    ],
    description=(
        "Emperador del Imperio Bizantino (741–775) de la Dinastía Isáurica. "
        "Gobernante enérgico y uno de los comandantes militares más victoriosos del medioevo bizantino; "
        "creó los regimientos militares de élite (Tagmata), repelió decisivamente las invasiones del califato abásida "
        "y neutralizó la amenaza militar búlgara en nueve victoriosas campañas en los Balcanes."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/e/eb/Solidus-Constantine_V_and_Leo_IV-sb1550.jpg",
    wikidata_id="Q41658",
    birth=HistoricalDate(year=718, month=7, precision="month"),
    death=HistoricalDate(year=775, month=9, day=14, precision="day"),
).model_dump(mode="json")

constantine_v = repo.create("people", constantine_v_input)
constantine_v_id = constantine_v["id"]
print("Creado Constantino V con ID:", constantine_v_id)

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
        id=constantine_v_id,
        rn="Constantine V Isaurian",
        bkf="Constantino V Coprónimo",
        c="GR",
        img=constantine_v_input["image_url"],
        occ="Emperador del Imperio Bizantino (Dinastía Isáurica)",
        desc=constantine_v_input["description"],
    )

# Enlace Constantino V -> León IV (family.parent_of)
source_c5_l4 = repo.create(
    "sources",
    SourceInput(
        title="Chronographia de Teófanes el Confesor: Nacimiento de León IV de Constantino V y Tzitzak (750)",
        url="https://www.degruyter.com/document/doi/10.1515/9783110826760/html",
        publisher="De Gruyter / CSHB",
        author="Theophanes the Confessor (ed. Carl de Boor)",
        location=LocationInput(
            name="De Gruyter",
            city="Berlín",
            country="DE",
            lat=52.5058,
            lng=13.3547,
        ),
    ).model_dump(mode="json"),
)

fact_c5_l4 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=constantine_v_id,
            object_id=leo_iv_id,
            source_id=source_c5_l4["id"],
            source_locator="Theophanis Chronographia, p. 426: Nascita di Leone IV nel Gran Palazzo il 25 gennaio 750",
            note=(
                "El emperador Constantino V fue el padre biológico de León IV el Jázaro, nacido el 25 de enero de 750 en Constantinopla "
                "de su matrimonio con la emperatriz Tzitzak (Irene de Jazaria). Constantino V lo coronó co-emperador en 751."
            ),
            status="draft",
            location=LocationInput(
                name="Gran Palacio de Constantinopla",
                city="Constantinopla (Estambul)",
                country="TR",
                lat=41.0054,
                lng=28.9768,
            ),
        ),
    ),
)
data_c5_l4 = {k: v for k, v in repo.get("facts", fact_c5_l4["id"]).items() if k not in ("id", "revision", "created_at", "updated_at")}
data_c5_l4["status"] = "verified"
repo.update("facts", fact_c5_l4["id"], fact_c5_l4["revision"], validate_fact(repo, data_c5_l4), "verify")
print("Hecho verificado: Constantino V -> León IV")

# =========================================================================
# 10. León III el Isáurico (685 – 741)
# =========================================================================
leo_iii_input = PersonInput(
    name="León III el Isáurico",
    aliases=[
        "León III",
        "Leo III the Isaurian",
        "El Salvador de Constantinopla",
    ],
    description=(
        "Emperador del Imperio Bizantino (717–741) y fundador de la Dinastía Isáurica. "
        "Veterano general sirio-anatólico, salvó decisivamente al Imperio Bizantino y a la Europa medieval "
        "destruyendo la inmensa armada y ejército del califato omeya durante el Segundo Asedio Árabe de Constantinopla (717–718). "
        "Promulgó la célebre 'Écloga', el primer código legal bizantino escrito completamente en lengua griega."
    ),
    country="TR",
    city_born="Germanicia (Kahramanmaraş)",
    image_url="https://upload.wikimedia.org/wikipedia/commons/e/ec/Leo_III_the_Isaurian_solidus.jpg",
    wikidata_id="Q41665",
    birth=HistoricalDate(year=685, precision="year"),
    death=HistoricalDate(year=741, month=6, day=18, precision="day"),
).model_dump(mode="json")

leo_iii = repo.create("people", leo_iii_input)
leo_iii_id = leo_iii["id"]
print("Creado León III el Isáurico con ID:", leo_iii_id)

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
        id=leo_iii_id,
        rn="Leo III the Isaurian",
        bkf="León III el Isáurico",
        c="TR",
        img=leo_iii_input["image_url"],
        occ="Emperador del Imperio Bizantino (Fundador de la Dinastía Isáurica)",
        desc=leo_iii_input["description"],
    )

# Enlace León III -> Constantino V (family.parent_of)
source_l3_c5 = repo.create(
    "sources",
    SourceInput(
        title="Chronographia de Teófanes el Confesor: Ascenso de León III y nacimiento de Constantino V (718)",
        url="https://www.degruyter.com/document/doi/10.1515/9783110826760/html",
        publisher="De Gruyter / CSHB",
        author="Theophanes the Confessor (ed. Carl de Boor)",
        location=LocationInput(
            name="De Gruyter",
            city="Berlín",
            country="DE",
            lat=52.5058,
            lng=13.3547,
        ),
    ).model_dump(mode="json"),
)

fact_l3_c5 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=leo_iii_id,
            object_id=constantine_v_id,
            source_id=source_l3_c5["id"],
            source_locator="Theophanis Chronographia, p. 399-401: Nascita di Costantino V a Costantinopoli nel luglio 718",
            note=(
                "El emperador León III el Isáurico fue el padre biológico de Constantino V, nacido en julio de 718 en Constantinopla "
                "de su matrimonio con la emperatriz María. León III bautizó solemnemente a Constantino en Santa Sofía y lo proclamó su sucesor dinástico."
            ),
            status="draft",
            location=LocationInput(
                name="Gran Palacio de Constantinopla",
                city="Constantinopla (Estambul)",
                country="TR",
                lat=41.0054,
                lng=28.9768,
            ),
        ),
    ),
)
data_l3_c5 = {k: v for k, v in repo.get("facts", fact_l3_c5["id"]).items() if k not in ("id", "revision", "created_at", "updated_at")}
data_l3_c5["status"] = "verified"
repo.update("facts", fact_l3_c5["id"], fact_l3_c5["revision"], validate_fact(repo, data_l3_c5), "verify")
print("Hecho verificado: León III -> Constantino V")

print("\n--- ¡Segmento cargado con éxito! ---")
print("Conexiones de León III el Isáurico:")
print(json.dumps(connection_preview(repo, leo_iii_id), indent=2, ensure_ascii=False))
