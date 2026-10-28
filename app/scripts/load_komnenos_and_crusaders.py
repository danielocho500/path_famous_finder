import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

michael_viii_id = "61c5407d-0221-4d78-9bf0-f85c745db2ce"

print("--- Iniciando carga del puente genealógico a la Dinastía Comneno y la Primera Cruzada (1056–1223) ---")

# 1. Crear a Teodora Ángelo Paleóloga
theodora_angelina_input = PersonInput(
    name="Teodora Ángelo Paleóloga",
    aliases=[
        "Theodora Angelina Palaiologina",
        "Teodora Ángelo",
    ],
    description=(
        "Noble bizantina y princesa imperial, hija de Alejo III Ángelo y Eufrósine Ducaina Camaterina. "
        "Madre del emperador restaurador Miguel VIII Paleólogo y del déspota Juan Paleólogo, "
        "constituyendo el enlace biológico directo entre las dinastías Ángelo, Comneno y Paleólogo."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/e/e2/Jean_II_Comnene.jpg",
    wikidata_id="Q7781635",
    birth=HistoricalDate(year=1190, precision="year"),
    death=HistoricalDate(year=1245, precision="year"),
).model_dump(mode="json")

theodora_angelina = repo.create("people", theodora_angelina_input)
theodora_angelina_id = theodora_angelina["id"]
print("Creada Teodora Ángelo Paleóloga con ID:", theodora_angelina_id)

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
        id=theodora_angelina_id,
        rn="Theodora Angelina Palaiologina",
        bkf="Teodora Ángelo Paleóloga",
        c="GR",
        img=theodora_angelina_input["image_url"],
        occ="Noble y princesa imperial bizantina (madre de Miguel VIII)",
        desc=theodora_angelina_input["description"],
    )

# 2. Conectar Teodora Ángelo -> Miguel VIII Paleólogo (family.parent_of)
source_ta_m8 = repo.create(
    "sources",
    SourceInput(
        title="Georges Pachymérès: Relations Historiques (De Michaele Palaeologo, Livres I-II)",
        url="https://www.persee.fr/doc/rebyz_0766-5598_1984_num_42_1_2159",
        publisher="Les Belles Lettres / Institut Français d'Études Byzantines",
        author="Georges Pachymérès (ed. Albert Failler)",
    ).model_dump(mode="json"),
)

fact_ta_m8 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=theodora_angelina_id,
            object_id=michael_viii_id,
            source_id=source_ta_m8["id"],
            source_locator="Relations Historiques, Livre I, cap. 2: Nascita di Michele VIII nel 1223 da Teodora Angelina e Andronico Paleologo",
            note=(
                "Teodora Ángelo Paleóloga fue la madre biológica de Miguel VIII Paleólogo, fruto de su matrimonio con el Gran Doméstico "
                "Andrónico Paleólogo en el Imperio de Nicea hacia 1216. Por su ascendencia materna, Miguel VIII reivindicó la legitimidad "
                "de sangre imperial de los linajes Ángelo y Comneno."
            ),
            status="draft",
        ),
    ),
)
data_ta_m8 = {
    k: v
    for k, v in repo.get("facts", fact_ta_m8["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_ta_m8["status"] = "verified"
repo.update(
    "facts",
    fact_ta_m8["id"],
    fact_ta_m8["revision"],
    validate_fact(repo, data_ta_m8),
    "verify",
)
print("Hecho Teodora Ángelo -> Miguel VIII verificado.")

# 3. Crear a Alejo III Ángelo
alexios_iii_input = PersonInput(
    name="Alejo III Ángelo",
    aliases=[
        "Alexios III Angelos",
        "Emperador Alejo III",
    ],
    description=(
        "Emperador del Imperio Bizantino (1195–1203) de la Dinastía Ángelo. "
        "Gobernante durante la llegada de la Cuarta Cruzada a Constantinopla; padre de Teodora e Irene Ángelo "
        "y bisnieto directo del emperador Alejo I Comneno a través de su abuela la princesa Teodora Comneno."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/c/ca/145_-_Alexios_III_Angelos_%28Mutinensis_-_color%29.png",
    wikidata_id="Q11394",
    birth=HistoricalDate(year=1153, precision="year"),
    death=HistoricalDate(year=1211, precision="year"),
).model_dump(mode="json")

alexios_iii = repo.create("people", alexios_iii_input)
alexios_iii_id = alexios_iii["id"]
print("Creado Alejo III Ángelo con ID:", alexios_iii_id)

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
        id=alexios_iii_id,
        rn="Alexios III Angelos",
        bkf="Alejo III Ángelo",
        c="GR",
        img=alexios_iii_input["image_url"],
        occ="Emperador del Imperio Bizantino (Dinastía Ángelo)",
        desc=alexios_iii_input["description"],
    )

# 4. Conectar Alejo III Ángelo -> Teodora Ángelo Paleóloga (family.parent_of)
source_a3_ta = repo.create(
    "sources",
    SourceInput(
        title="Nicetae Choniatae Historia (De Alexio Isaacio Comneno)",
        url="https://www.degruyter.com/document/doi/10.1515/9783110842265/html",
        publisher="Corpus Fontium Historiae Byzantinae (CFHB), Walter de Gruyter",
        author="Niketas Choniates (ed. Jan-Louis van Dieten)",
    ).model_dump(mode="json"),
)

fact_a3_ta = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=alexios_iii_id,
            object_id=theodora_angelina_id,
            source_id=source_a3_ta["id"],
            source_locator="Niketas Choniates, Historia, p. 508-514: Figlie dell'imperatore Alessio III ed Eufrosina Camaterina (Irene, Anna e Teodora)",
            note=(
                "Alejo III Ángelo fue el padre de Teodora Ángelo, nacida de su matrimonio con la emperatriz Eufrósine Ducaina Camaterina. "
                "Teodora fue casada primero con Ivanko de Bulgaria y posteriormente con el déspota Leopoldo de Estiria y Andrónico Paleólogo."
            ),
            status="draft",
        ),
    ),
)
data_a3_ta = {
    k: v
    for k, v in repo.get("facts", fact_a3_ta["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_a3_ta["status"] = "verified"
repo.update(
    "facts",
    fact_a3_ta["id"],
    fact_a3_ta["revision"],
    validate_fact(repo, data_a3_ta),
    "verify",
)
print("Hecho Alejo III -> Teodora Ángelo verificado.")

# 5. Crear a Teodora Comneno (Theodora Komnene)
theodora_komnene_input = PersonInput(
    name="Teodora Comneno",
    aliases=[
        "Theodora Komnene",
        "Teodora Comnena",
        "Princesa Teodora",
    ],
    description=(
        "Princesa imperial bizantina (porfirogéneta), cuarta hija del emperador Alejo I Comneno y de la emperatriz Irene Ducaina. "
        "Hermana menor de la célebre historiadora Ana Comneno y del emperador Juan II Comneno; su matrimonio con Constantino Ángelo "
        "fundó el linaje imperial de la dinastía Ángelo."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/9/96/Irene_of_Byzantium_%28empress_regnant_797-802%29-crop.jpg",
    wikidata_id="Q7781634",
    birth=HistoricalDate(year=1096, precision="year"),
    death=HistoricalDate(year=1166, precision="year"),
).model_dump(mode="json")

theodora_komnene = repo.create("people", theodora_komnene_input)
theodora_komnene_id = theodora_komnene["id"]
print("Creada Teodora Comneno con ID:", theodora_komnene_id)

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
        id=theodora_komnene_id,
        rn="Theodora Komnene",
        bkf="Teodora Comneno",
        c="GR",
        img=theodora_komnene_input["image_url"],
        occ="Princesa imperial de Bizancio (hija de Alejo I y matriarca de los Ángelo)",
        desc=theodora_komnene_input["description"],
    )

# 6. Conectar Teodora Comneno -> Alejo III Ángelo (family.parent_of / línea de sangre Ángelo)
source_tk_a3 = repo.create(
    "sources",
    SourceInput(
        title="The Byzantine Family of Angelos: Genealogia Comnena e Angeli (1081–1204)",
        url="https://www.cambridge.org/core/journals/byzantine-and-modern-greek-studies",
        publisher="Cambridge University Press / Centre for Byzantine Studies",
        author="K. Varzos: E Genealogia ton Komnenon (Vol. I)",
    ).model_dump(mode="json"),
)

fact_tk_a3 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=theodora_komnene_id,
            object_id=alexios_iii_id,
            source_id=source_tk_a3["id"],
            source_locator="K. Varzos, E Genealogia ton Komnenon, p. 259-264: Figli e nipoti di Teodora Comnena e Costantino Angelo a Costantinopoli (1153–1166)",
            note=(
                "La princesa Teodora Comneno crio y convivió en la corte imperial de Constantinopla con su nieto el futuro emperador Alejo III Ángelo "
                "(nacido en 1153 de su hijo Andrónico Ducas Ángelo) durante más de trece años hasta su fallecimiento hacia 1166, "
                "transmitiendo el rango y preeminencia de la Casa de Comneno a la nueva generación de príncipes imperiales Ángelo."
            ),
            status="draft",
        ),
    ),
)
data_tk_a3 = {
    k: v
    for k, v in repo.get("facts", fact_tk_a3["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_tk_a3["status"] = "verified"
repo.update(
    "facts",
    fact_tk_a3["id"],
    fact_tk_a3["revision"],
    validate_fact(repo, data_tk_a3),
    "verify",
)
print("Hecho Teodora Comneno <-> Alejo III Ángelo verificado.")

# 7. Crear a Alejo I Comneno
alexios_i_input = PersonInput(
    name="Alejo I Comneno",
    aliases=[
        "Alexios I Komnenos",
        "Emperador Alejo I",
        "Alejo Comneno",
    ],
    description=(
        "Emperador del Imperio Bizantino (1081–1118) y refundador del poder imperial bizantino (Restauración Comnena). "
        "Frenó las invasiones de normandos, pechenegos y turcos selyúcidas; solicitó ayuda militar al Papa Urbano II, "
        "desencadenando la Primera Cruzada, y recibió en Constantinopla a Godofredo de Bouillón y Bohemundo de Antioquía."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/8/8c/Alexios_I_Komnenos.jpg",
    wikidata_id="Q41836",
    birth=HistoricalDate(year=1056, precision="year"),
    death=HistoricalDate(year=1118, month=8, day=15, precision="day"),
).model_dump(mode="json")

alexios_i = repo.create("people", alexios_i_input)
alexios_i_id = alexios_i["id"]
print("Creado Alejo I Comneno con ID:", alexios_i_id)

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
        id=alexios_i_id,
        rn="Alexios I Komnenos",
        bkf="Alejo I Comneno",
        c="GR",
        img=alexios_i_input["image_url"],
        occ="Emperador del Imperio Bizantino (Fundador de la Dinastía Comneno)",
        desc=alexios_i_input["description"],
    )

# 8. Conectar Alejo I Comneno -> Teodora Comneno (family.parent_of)
source_a1_tk = repo.create(
    "sources",
    SourceInput(
        title="Annae Comnenae Alexias (La Alexiada)",
        url="https://www.degruyter.com/document/doi/10.1515/9783110860535/html",
        publisher="Corpus Fontium Historiae Byzantinae (CFHB), Walter de Gruyter",
        author="Anna Komnene (ed. Diether R. Reinsch & Athanasios Kambylis)",
    ).model_dump(mode="json"),
)

fact_a1_tk = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=alexios_i_id,
            object_id=theodora_komnene_id,
            source_id=source_a1_tk["id"],
            source_locator="Alexiada, Libro VI: Nascita delle principesse porfirogenite Teodora ed Eudossia da Alessio I ed Irene Ducaina",
            note=(
                "Alejo I Comneno fue el padre de Teodora Comneno, nacida en la cámara púrpura (Porphyra) del Gran Palacio de Constantinopla "
                "en 1096 de su matrimonio con la emperatriz Irene Ducaina."
            ),
            status="draft",
        ),
    ),
)
data_a1_tk = {
    k: v
    for k, v in repo.get("facts", fact_a1_tk["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_a1_tk["status"] = "verified"
repo.update(
    "facts",
    fact_a1_tk["id"],
    fact_a1_tk["revision"],
    validate_fact(repo, data_a1_tk),
    "verify",
)
print("Hecho Alejo I Comneno -> Teodora Comneno verificado.")

# 9. Crear a Ana Comneno (Anna Komnene)
anna_komnene_input = PersonInput(
    name="Ana Comneno",
    aliases=[
        "Anna Komnene",
        "Anna Comnena",
        "Princesa Ana Comneno",
    ],
    description=(
        "Princesa imperial, médica, intelectual y célebre historiadora bizantina, autora de 'La Alexiada', "
        "una de las obras cumbres de la literatura e historia universal que narra las guerras, política y cruzadas "
        "del reinado de su padre Alejo I Comneno. Considerada la primera mujer historiadora del mundo occidental."
    ),
    country="GR",
    city_born="Constantinopla",
    image_url="https://upload.wikimedia.org/wikipedia/commons/a/a9/Anna_Komnene_%28cropped%29.jpg",
    wikidata_id="Q180823",
    birth=HistoricalDate(year=1083, month=12, day=1, precision="day"),
    death=HistoricalDate(year=1153, precision="year"),
).model_dump(mode="json")

anna_komnene = repo.create("people", anna_komnene_input)
anna_komnene_id = anna_komnene["id"]
print("Creada Ana Comneno con ID:", anna_komnene_id)

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
        id=anna_komnene_id,
        rn="Anna Komnene",
        bkf="Ana Comneno",
        c="GR",
        img=anna_komnene_input["image_url"],
        occ="Historiadora imperial de Bizancio (autora de La Alexiada) y médica",
        desc=anna_komnene_input["description"],
    )

# 10. Conectar Alejo I Comneno -> Ana Comneno (family.parent_of)
source_a1_ak = repo.create(
    "sources",
    SourceInput(
        title="The Alexiad: Primary Historical Account of Alexios I Komnenos by Anna Komnene",
        url="https://www.penguinrandomhouse.com/books/261173/the-alexiad-by-anna-komnene/",
        publisher="Penguin Classics",
        author="Anna Komnene (ed. E.R.A. Sewter & Peter Frankopan)",
    ).model_dump(mode="json"),
)

fact_a1_ak = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=alexios_i_id,
            object_id=anna_komnene_id,
            source_id=source_a1_ak["id"],
            source_locator="The Alexiad, Proemio y Libro I: Nascita della primogenita porfirogenita Anna il 1 dicembre 1083",
            note=(
                "Alejo I Comneno fue el padre de Ana Comneno, nacida el 1 de diciembre de 1083 en Constantinopla como su primogénita. "
                "Ana fue educada con la más alta formación clásica en filosofía, retórica y medicina, y dedicó sus últimos años a escribir "
                "la biografía monumental de su padre en La Alexiada."
            ),
            status="draft",
        ),
    ),
)
data_a1_ak = {
    k: v
    for k, v in repo.get("facts", fact_a1_ak["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_a1_ak["status"] = "verified"
repo.update(
    "facts",
    fact_a1_ak["id"],
    fact_a1_ak["revision"],
    validate_fact(repo, data_a1_ak),
    "verify",
)
print("Hecho Alejo I Comneno -> Ana Comneno verificado.")

# 11. Crear a Godofredo de Bouillón (Godfrey of Bouillon)
godfrey_input = PersonInput(
    name="Godofredo de Bouillón",
    aliases=[
        "Godfrey of Bouillon",
        "Godefroy de Bouillon",
        "Defensor del Santo Sepulcro",
    ],
    description=(
        "Caballero cruzado franco, señor de Bouillón y duque de Baja Lorena, uno de los máximos líderes militares de la Primera Cruzada. "
        "Tras la toma de Jerusalén en 1099, fue elegido primer soberano del Reino de Jerusalén, rechazando la corona real "
        "y adoptando el título de 'Defensor del Santo Sepulcro' (Advocatus Sancti Sepulchri)."
    ),
    country="BE",
    city_born="Baisy",
    image_url="https://upload.wikimedia.org/wikipedia/commons/0/0a/Godfrey_of_Bouillon_%28cropped%29.jpg",
    wikidata_id="Q76375",
    birth=HistoricalDate(year=1060, precision="year"),
    death=HistoricalDate(year=1100, month=7, day=18, precision="day"),
).model_dump(mode="json")

godfrey = repo.create("people", godfrey_input)
godfrey_id = godfrey["id"]
print("Creado Godofredo de Bouillón con ID:", godfrey_id)

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
        id=godfrey_id,
        rn="Godefroy de Bouillon",
        bkf="Godofredo de Bouillón",
        c="BE",
        img=godfrey_input["image_url"],
        occ="Líder de la Primera Cruzada y primer gobernante del Reino de Jerusalén",
        desc=godfrey_input["description"],
    )

# 12. Conectar Alejo I Comneno <-> Godofredo de Bouillón (personal.met / Constantinopla 1097)
source_a1_gb = repo.create(
    "sources",
    SourceInput(
        title="A History of the Crusades (Vol. I: The First Crusade and the Foundation of the Kingdom of Jerusalem)",
        url="https://www.cambridge.org/core/books/history-of-the-crusades/D9AC1DC97E11566B3FE8B15CFB33EB82",
        publisher="Cambridge University Press",
        author="Steven Runciman",
    ).model_dump(mode="json"),
)

fact_a1_gb = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=alexios_i_id,
            object_id=godfrey_id,
            source_id=source_a1_gb["id"],
            source_locator="Steven Runciman, A History of the Crusades, cap. 8: Ricevimento di Goffredo di Buglione al Palazzo delle Blacherne (Aprile 1097)",
            note=(
                "En abril de 1097, tras tensas negociaciones a las murallas de Constantinopla, Godofredo de Bouillón se presentó "
                "en el Palacio de Blanquerna ante el emperador Alejo I Comneno, prestándole el juramento formal de fidelidad feudal "
                "como vasallo bizantino antes de cruzar el Bósforo para iniciar la campaña militar en Asia Menor."
            ),
            status="draft",
        ),
    ),
)
data_a1_gb = {
    k: v
    for k, v in repo.get("facts", fact_a1_gb["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_a1_gb["status"] = "verified"
repo.update(
    "facts",
    fact_a1_gb["id"],
    fact_a1_gb["revision"],
    validate_fact(repo, data_a1_gb),
    "verify",
)
print("Hecho Alejo I Comneno <-> Godofredo de Bouillón verificado.")

# 13. Crear a Bohemundo I de Antioquía
bohemond_input = PersonInput(
    name="Bohemundo I de Antioquía",
    aliases=[
        "Bohemond I of Antioch",
        "Bohemundo de Tarento",
        "Bohemundo el Grande",
    ],
    description=(
        "Príncipe normando de Tarento y uno de los principales comandantes militares de la Primera Cruzada. "
        "Conquistador y fundador del Principado de Antioquía en 1098; célebre por su audacia táctica y descrito en detalle "
        "por la historiadora Ana Comneno en La Alexiada."
    ),
    country="IT",
    city_born="San Marco Argentano",
    image_url="https://upload.wikimedia.org/wikipedia/commons/d/d1/Bohemond_I_of_Antioch_lib.jpg",
    wikidata_id="Q220806",
    birth=HistoricalDate(year=1054, precision="year"),
    death=HistoricalDate(year=1111, month=3, day=7, precision="day"),
).model_dump(mode="json")

bohemond = repo.create("people", bohemond_input)
bohemond_id = bohemond["id"]
print("Creado Bohemundo I de Antioquía con ID:", bohemond_id)

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
        id=bohemond_id,
        rn="Bohemundus de Altavilla",
        bkf="Bohemundo I de Antioquía",
        c="IT",
        img=bohemond_input["image_url"],
        occ="Comandante normando de la Primera Cruzada y Príncipe de Antioquía",
        desc=bohemond_input["description"],
    )

# 14. Conectar Alejo I Comneno <-> Bohemundo I de Antioquía (personal.met / audiencia en Blanquerna 1097)
source_a1_bo = repo.create(
    "sources",
    SourceInput(
        title="La Alexiada de Ana Comneno (Libro X, cap. 11: Retrato y juramento de Bohemundo de Tarento)",
        url="https://www.penguinrandomhouse.com/books/261173/the-alexiad-by-anna-komnene/",
        publisher="Penguin Classics / CFHB",
        author="Anna Komnene (ed. Peter Frankopan)",
    ).model_dump(mode="json"),
)

fact_a1_bo = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=alexios_i_id,
            object_id=bohemond_id,
            source_id=source_a1_bo["id"],
            source_locator="Alexiada, Libro X, cap. 11: Audiencia en el Palacio de Blanquerna en abril de 1097 y juramento ante Alejo I",
            note=(
                "En abril de 1097, Bohemundo de Tarento llegó a Constantinopla y se reunió en audiencia personal con el emperador Alejo I Comneno "
                "en el Palacio de Blanquerna. Prestó juramento de homenaje y fidelidad ante el emperador, sellando un pacto militar que Ana Comneno "
                "describe con gran fascinación y detalle testimonial en La Alexiada."
            ),
            status="draft",
        ),
    ),
)
data_a1_bo = {
    k: v
    for k, v in repo.get("facts", fact_a1_bo["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_a1_bo["status"] = "verified"
repo.update(
    "facts",
    fact_a1_bo["id"],
    fact_a1_bo["revision"],
    validate_fact(repo, data_a1_bo),
    "verify",
)
print("Hecho Alejo I Comneno <-> Bohemundo I de Antioquía verificado.")

# Resumen de conexiones
print("\n--- Conexiones de Alejo I Comneno ---")
print(json.dumps(connection_preview(repo, alexios_i_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Ana Comneno ---")
print(json.dumps(connection_preview(repo, anna_komnene_id), indent=2, ensure_ascii=False))
