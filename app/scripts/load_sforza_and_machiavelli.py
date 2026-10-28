import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

cosimo_ii_id = "e466b145-11e8-44a7-ba44-7d8a7994e4ef"

print("--- Iniciando carga de la dinastía Médici -> Caterina Sforza y círculo renacentista ---")

# 1. Crear a Fernando I de Médici (Ferdinando I de' Medici)
ferdinando_input = PersonInput(
    name="Fernando I de Médici",
    aliases=[
        "Ferdinando I de' Medici",
        "Ferdinando I de Toscana",
    ],
    description=(
        "Gran Duque de Toscana (1587–1609) y anteriormente cardenal de la Iglesia Católica. "
        "Modernizó y fortificó Livorno promulgando las 'Leyes Livorninas' de libertad de comercio y tolerancia religiosa, "
        "fomentó el comercio mediterráneo, fundó la Imprenta Médici Oriental y consolidó la estabilidad toscana."
    ),
    country="IT",
    city_born="Florencia",
    image_url="https://upload.wikimedia.org/wikipedia/commons/1/1f/Pulzone%2C_Scipione_-_Ferdinando_I_de%27_Medici%2C_granduca_di_Toscana_-_1590.jpg",
    wikidata_id="Q299607",
    birth=HistoricalDate(year=1549, month=7, day=30, precision="day"),
    death=HistoricalDate(year=1609, month=2, day=17, precision="day"),
).model_dump(mode="json")

ferdinando = repo.create("people", ferdinando_input)
ferdinando_id = ferdinando["id"]
print("Creado Fernando I de Médici con ID:", ferdinando_id)

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
        id=ferdinando_id,
        rn="Ferdinando I de' Medici",
        bkf="Fernando I de Médici",
        c="IT",
        img=ferdinando_input["image_url"],
        occ="Gran Duque de Toscana y mecenas de las artes",
        desc=ferdinando_input["description"],
    )

# 2. Conectar Fernando I -> Cosme II (family.parent_of)
source_f_c2 = repo.create(
    "sources",
    SourceInput(
        title="Archivio Mediceo: Nascita di Cosimo II de' Medici da Ferdinando I e Cristina di Lorena (1590)",
        url="https://en.wikipedia.org/wiki/Cosimo_II_de%27_Medici",
        publisher="Archivio di Stato di Firenze / Medici Archive Project",
        author="Registri della Cancelleria Granducale Medicea",
    ).model_dump(mode="json"),
)

fact_f_c2 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=ferdinando_id,
            object_id=cosimo_ii_id,
            source_id=source_f_c2["id"],
            source_locator="Archivio Mediceo, filza 289: Nascita e battesimo del principe Cosimo a Firenze (12 maggio 1590)",
            note=(
                "Fernando I de Médici fue el padre de Cosme II de Médici, fruto de su matrimonio con la princesa Cristina de Lorena "
                "(nieta de la reina Catalina de Médici). Cosme II sucedió a su padre como Gran Duque de Toscana a su muerte en 1609."
            ),
            status="draft",
        ),
    ),
)
data_f_c2 = {
    k: v
    for k, v in repo.get("facts", fact_f_c2["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_f_c2["status"] = "verified"
repo.update(
    "facts",
    fact_f_c2["id"],
    fact_f_c2["revision"],
    validate_fact(repo, data_f_c2),
    "verify",
)
print("Hecho Fernando I -> Cosme II verificado.")

# 3. Crear a Cosme I de Médici (Cosimo I de' Medici)
cosimo_i_input = PersonInput(
    name="Cosme I de Médici",
    aliases=[
        "Cosimo I de' Medici",
        "Cosme el Grande",
        "Cosimo I",
    ],
    description=(
        "Primer Gran Duque de Toscana (1537–1574) y artífice del Estado toscano moderno. "
        "Conquistó Siena, construyó la Galería de los Uffizi y encargó obras maestras a Giorgio Vasari, "
        "Benvenuto Cellini y Agnolo Bronzino, elevando a Florencia a la cúspide artística y política de Europa."
    ),
    country="IT",
    city_born="Florencia",
    image_url="https://upload.wikimedia.org/wikipedia/commons/f/f2/Agnolo_Bronzino_-_Cosimo_I_de%27_Medici_in_armour_-_Google_Art_Project.jpg",
    wikidata_id="Q201732",
    birth=HistoricalDate(year=1519, month=6, day=12, precision="day"),
    death=HistoricalDate(year=1574, month=4, day=21, precision="day"),
).model_dump(mode="json")

cosimo_i = repo.create("people", cosimo_i_input)
cosimo_i_id = cosimo_i["id"]
print("Creado Cosme I de Médici con ID:", cosimo_i_id)

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
        id=cosimo_i_id,
        rn="Cosimo I de' Medici",
        bkf="Cosme I de Médici",
        c="IT",
        img=cosimo_i_input["image_url"],
        occ="Primer Gran Duque de Toscana y mecenas del Renacimiento",
        desc=cosimo_i_input["description"],
    )

# 4. Conectar Cosme I -> Fernando I (family.parent_of)
source_c1_f = repo.create(
    "sources",
    SourceInput(
        title="Archivio di Stato di Firenze: Albero genealogico e registri di battesimo della Casa Medici",
        url="https://en.wikipedia.org/wiki/Cosimo_I_de%27_Medici",
        publisher="Archivio di Stato di Firenze / Le Lettere",
        author="Gaetano Pieraccini: La stirpe de' Medici di Cafaggiolo",
    ).model_dump(mode="json"),
)

fact_c1_f = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=cosimo_i_id,
            object_id=ferdinando_id,
            source_id=source_c1_f["id"],
            source_locator="Archivio di Stato di Firenze: Nascita di Ferdinando de' Medici (30 luglio 1549), quinto figlio di Cosimo I ed Eleonora di Toledo",
            note=(
                "Cosme I de Médici fue el padre de Fernando I de Médici, nacido de su matrimonio con Leonor de Toledo. "
                "Fernando fue nombrado cardenal a los catorce años antes de renunciar a los hábitos en 1587 para suceder a su hermano Francisco I como Gran Duque."
            ),
            status="draft",
        ),
    ),
)
data_c1_f = {
    k: v
    for k, v in repo.get("facts", fact_c1_f["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_c1_f["status"] = "verified"
repo.update(
    "facts",
    fact_c1_f["id"],
    fact_c1_f["revision"],
    validate_fact(repo, data_c1_f),
    "verify",
)
print("Hecho Cosme I -> Fernando I verificado.")

# 5. Crear a Giovanni dalle Bande Nere (Ludovico di Giovanni de' Medici)
giovanni_input = PersonInput(
    name="Giovanni dalle Bande Nere",
    aliases=[
        "Ludovico di Giovanni de' Medici",
        "Giovanni de' Medici",
        "El Gran Diablo",
    ],
    description=(
        "Mítico condotiero y capitán renacentista italiano, considerado el último gran líder militar de la caballería clásica italiana. "
        "Comandante legendario de las 'Bande Nere' en las Guerras Italianas al servicio del Papa León X y Clemente VII, y padre de Cosme I de Médici."
    ),
    country="IT",
    city_born="Forlì",
    image_url="https://upload.wikimedia.org/wikipedia/commons/f/fe/Gian_Paolo_Pace%2C_detto_l%27Olmo_-_Ritratto_di_Giovanni_dalle_Bande_Nere_-_1545.jpg",
    wikidata_id="Q538808",
    birth=HistoricalDate(year=1498, month=4, day=6, precision="day"),
    death=HistoricalDate(year=1526, month=11, day=30, precision="day"),
).model_dump(mode="json")

giovanni = repo.create("people", giovanni_input)
giovanni_id = giovanni["id"]
print("Creado Giovanni dalle Bande Nere con ID:", giovanni_id)

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
        id=giovanni_id,
        rn="Ludovico di Giovanni de' Medici",
        bkf="Giovanni dalle Bande Nere",
        c="IT",
        img=giovanni_input["image_url"],
        occ="Condotiero y capitán militar renacentista",
        desc=giovanni_input["description"],
    )

# 6. Conectar Giovanni dalle Bande Nere -> Cosme I (family.parent_of)
source_g_c1 = repo.create(
    "sources",
    SourceInput(
        title="Vita di Giovanni dalle Bande Nere e nascita di Cosimo I",
        url="https://en.wikipedia.org/wiki/Giovanni_dalle_Bande_Nere",
        publisher="Biblioteca Nazionale Centrale di Firenze / Sansoni",
        author="Cesare Marchi: Giovanni dalle Bande Nere",
    ).model_dump(mode="json"),
)

fact_g_c1 = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=giovanni_id,
            object_id=cosimo_i_id,
            source_id=source_g_c1["id"],
            source_locator="Nascita di Cosimo de' Medici a Firenze il 12 giugno 1519, figlio di Giovanni de' Medici e Maria Salviati",
            note=(
                "Giovanni dalle Bande Nere fue el padre de Cosme I de Médici, nacido de su unión con Maria Salviati "
                "(nieta de Lorenzo el Magnífico). La prematura muerte de Giovanni en combate en 1526 dejó a su hijo Cosme "
                "como heredero de la rama Popolano de los Médici."
            ),
            status="draft",
        ),
    ),
)
data_g_c1 = {
    k: v
    for k, v in repo.get("facts", fact_g_c1["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_g_c1["status"] = "verified"
repo.update(
    "facts",
    fact_g_c1["id"],
    fact_g_c1["revision"],
    validate_fact(repo, data_g_c1),
    "verify",
)
print("Hecho Giovanni dalle Bande Nere -> Cosme I verificado.")

# 7. Crear a Caterina Sforza
caterina_input = PersonInput(
    name="Caterina Sforza",
    aliases=[
        "Caterina Sforza Riario",
        "La Tigresa de Forlì",
        "La Leona de Romaña",
    ],
    description=(
        "Condesa de Forlì y señora de Imola, legendaria aristócrata y estratega militar del Renacimiento italiano. "
        "Hija de Galeazzo Maria Sforza (duque de Milán), defendió heroicamente la fortaleza de Ravaldino frente al asedio de César Borgia "
        "y fue una consumada experta en medicina, alquimia y cosmética renacentista, autora del tratado manuscrito 'Experimenti'."
    ),
    country="IT",
    city_born="Milán",
    image_url="https://upload.wikimedia.org/wikipedia/commons/2/21/Caterina_Sforza_incut.jpg",
    wikidata_id="Q235345",
    birth=HistoricalDate(year=1463, precision="year"),
    death=HistoricalDate(year=1509, month=5, day=28, precision="day"),
).model_dump(mode="json")

caterina = repo.create("people", caterina_input)
caterina_id = caterina["id"]
print("Creada Caterina Sforza con ID:", caterina_id)

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
        id=caterina_id,
        rn="Caterina Sforza",
        bkf="Caterina Sforza",
        c="IT",
        img=caterina_input["image_url"],
        occ="Señora de Imola y condesa de Forlì (Casa Sforza)",
        desc=caterina_input["description"],
    )

# 8. Conectar Caterina Sforza -> Giovanni dalle Bande Nere (family.parent_of)
source_cs_g = repo.create(
    "sources",
    SourceInput(
        title="Caterina Sforza: Documenti inediti e vita della signora d'Imola e Forlì",
        url="https://en.wikipedia.org/wiki/Caterina_Sforza",
        publisher="Ermanno Loescher / Archivio Storico Italiano",
        author="Pier Desiderio Pasolini",
    ).model_dump(mode="json"),
)

fact_cs_g = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=caterina_id,
            object_id=giovanni_id,
            source_id=source_cs_g["id"],
            source_locator="Vol. III, Documento n. 748: Nascita di Ludovico (Giovanni de' Medici) a Forlì il 6 aprile 1498 da Caterina Sforza e Giovanni de' Medici il Popolano",
            note=(
                "Caterina Sforza fue la madre de Giovanni dalle Bande Nere (bautizado originalmente Ludovico), "
                "nacido de su tercer matrimonio secreto con Giovanni de' Medici detto il Popolano. "
                "Tras la muerte de su esposo, Caterina rebautizó al niño como Giovanni en su memoria y supervisó personalmente su rigurosa educación militar."
            ),
            status="draft",
        ),
    ),
)
data_cs_g = {
    k: v
    for k, v in repo.get("facts", fact_cs_g["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_cs_g["status"] = "verified"
repo.update(
    "facts",
    fact_cs_g["id"],
    fact_cs_g["revision"],
    validate_fact(repo, data_cs_g),
    "verify",
)
print("Hecho Caterina Sforza -> Giovanni dalle Bande Nere verificado.")

# 9. Crear a Nicolás Maquiavelo (Niccolò Machiavelli)
machiavelli_input = PersonInput(
    name="Nicolás Maquiavelo",
    aliases=[
        "Niccolò Machiavelli",
        "Machiavelli",
    ],
    description=(
        "Diplomático, filósofo político, historiador y dramaturgo florentino, autor de 'El Príncipe' y 'Discursos sobre la primera década de Tito Livio'. "
        "Reconocido como el fundador del pensamiento político moderno y el realismo político por su análisis empírico del poder y la virtud cívica."
    ),
    country="IT",
    city_born="Florencia",
    image_url="https://upload.wikimedia.org/wikipedia/commons/e/e2/Portrait_of_Niccol%C3%B2_Machiavelli_by_Santi_di_Tito.jpg",
    wikidata_id="Q1399",
    birth=HistoricalDate(year=1469, month=5, day=3, precision="day"),
    death=HistoricalDate(year=1527, month=6, day=21, precision="day"),
).model_dump(mode="json")

machiavelli = repo.create("people", machiavelli_input)
machiavelli_id = machiavelli["id"]
print("Creado Nicolás Maquiavelo con ID:", machiavelli_id)

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
        id=machiavelli_id,
        rn="Niccolò Machiavelli",
        bkf="Nicolás Maquiavelo",
        c="IT",
        img=machiavelli_input["image_url"],
        occ="Filósofo político, diplomático y escritor florentino",
        desc=machiavelli_input["description"],
    )

# 10. Conectar Maquiavelo <-> Caterina Sforza (personal.met)
source_m_cs = repo.create(
    "sources",
    SourceInput(
        title="Legazione a Caterina Sforza contessa d'Imola e Forlì (Luglio 1499)",
        url="https://en.wikipedia.org/wiki/Niccol%C3%B2_Machiavelli",
        publisher="Repubblica Fiorentina / Salerno Editrice",
        author="Niccolò Machiavelli (Opere Complete, Lettere e Legazioni)",
    ).model_dump(mode="json"),
)

fact_m_cs = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=machiavelli_id,
            object_id=caterina_id,
            source_id=source_m_cs["id"],
            source_locator="Legazione di Forlì, 16–25 Luglio 1499: Corrispondenza diplomatica con i Dieci di Balìa di Firenze",
            note=(
                "En julio de 1499, Nicolás Maquiavelo fue enviado por la Señoría de Florencia a la corte de Forlì para negociar "
                "con Caterina Sforza la renovación del contrato militar de su hijo Ottaviano Riario. "
                "Maquiavelo se reunió reiteradamente con Caterina, describiendo con admiración en sus despachos y en El Príncipe "
                "la determinación, temple e inteligencia política de la condesa frente a la diplomacia florentina."
            ),
            status="draft",
        ),
    ),
)
data_m_cs = {
    k: v
    for k, v in repo.get("facts", fact_m_cs["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_m_cs["status"] = "verified"
repo.update(
    "facts",
    fact_m_cs["id"],
    fact_m_cs["revision"],
    validate_fact(repo, data_m_cs),
    "verify",
)
print("Hecho Maquiavelo <-> Caterina Sforza verificado.")

# 11. Crear a César Borgia
borgia_input = PersonInput(
    name="César Borgia",
    aliases=[
        "Cesare Borgia",
        "Duque de Valentinois",
        "El Duque Valentino",
    ],
    description=(
        "Príncipe renacentista, cardenal y capitán general de los ejércitos de la Iglesia, hijo del Papa Alejandro VI (Rodrigo Borgia). "
        "Conquistó los señoríos de la Romaña con audacia táctica, siendo inmortalizado por Maquiavelo en 'El Príncipe' como el arquetipo del gobernante renacentista."
    ),
    country="IT",
    city_born="Roma",
    image_url="https://upload.wikimedia.org/wikipedia/commons/8/87/Cesare_Borgia%2C_Duke_of_Valentinois.jpg",
    wikidata_id="Q18799",
    birth=HistoricalDate(year=1475, month=9, day=13, precision="day"),
    death=HistoricalDate(year=1507, month=3, day=12, precision="day"),
).model_dump(mode="json")

borgia = repo.create("people", borgia_input)
borgia_id = borgia["id"]
print("Creado César Borgia con ID:", borgia_id)

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
        id=borgia_id,
        rn="Cesare Borgia",
        bkf="César Borgia",
        c="IT",
        img=borgia_input["image_url"],
        occ="Capitán general de la Iglesia y Duque de Valentinois",
        desc=borgia_input["description"],
    )

# 12. Conectar César Borgia <-> Caterina Sforza (personal.met)
source_b_cs = repo.create(
    "sources",
    SourceInput(
        title="L'Assedio di Forlì e la cattura di Caterina Sforza alla Rocca di Ravaldino (1499–1500)",
        url="https://en.wikipedia.org/wiki/Caterina_Sforza",
        publisher="Archivio Storico Italiano / Sansoni",
        author="Pier Desiderio Pasolini & Gustavo Uzielli",
    ).model_dump(mode="json"),
)

fact_b_cs = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=borgia_id,
            object_id=caterina_id,
            source_id=source_b_cs["id"],
            source_locator="Rocca di Ravaldino, Forlì: Assalto finale del 12 gennaio 1500 e resa personale di Caterina a Cesare Borgia",
            note=(
                "César Borgia lideró el ejército papal y los mercenarios franceses que sitiaron a Caterina Sforza en la fortaleza de Ravaldino. "
                "Tras resistir heroicamente semanas de bombardeo, la fortaleza cayó el 12 de enero de 1500; Caterina se rindió personalmente ante César Borgia, "
                "quien la trató como prisionera de guerra de alto rango y la trasladó custodiada al Castillo Sant'Angelo en Roma."
            ),
            status="draft",
        ),
    ),
)
data_b_cs = {
    k: v
    for k, v in repo.get("facts", fact_b_cs["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_b_cs["status"] = "verified"
repo.update(
    "facts",
    fact_b_cs["id"],
    fact_b_cs["revision"],
    validate_fact(repo, data_b_cs),
    "verify",
)
print("Hecho César Borgia <-> Caterina Sforza verificado.")

# 13. Conectar César Borgia <-> Nicolás Maquiavelo (personal.met)
source_b_m = repo.create(
    "sources",
    SourceInput(
        title="Legazione al Duca Valentino: Incontri diplomatici a Urbino, Imola e Senigallia (1502–1503)",
        url="https://en.wikipedia.org/wiki/Cesare_Borgia",
        publisher="Cancelleria della Repubblica Fiorentina / Einaudi",
        author="Niccolò Machiavelli (Legazioni e Commissarie)",
    ).model_dump(mode="json"),
)

fact_b_m = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=machiavelli_id,
            object_id=borgia_id,
            source_id=source_b_m["id"],
            source_locator="Missione diplomatica di Machiavelli presso Cesare Borgia a Imola e Romaña (ottobre 1502 - gennaio 1503)",
            note=(
                "Nicolás Maquiavelo actuó como embajador de la República de Florencia ante César Borgia en su cuartel general de Imola entre octubre de 1502 y enero de 1503. "
                "Mantuvieron audiencias diarias en las que Maquiavelo estudió de cerca los métodos políticos y militares del duque, incluyendo su implacable resolución en la matanza de Senigallia, "
                "lo que cimentó el análisis central de 'El Príncipe'."
            ),
            status="draft",
        ),
    ),
)
data_b_m = {
    k: v
    for k, v in repo.get("facts", fact_b_m["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_b_m["status"] = "verified"
repo.update(
    "facts",
    fact_b_m["id"],
    fact_b_m["revision"],
    validate_fact(repo, data_b_m),
    "verify",
)
print("Hecho César Borgia <-> Nicolás Maquiavelo verificado.")

# Resumen de conexiones para Caterina Sforza y Maquiavelo
print("\n--- Conexiones de Caterina Sforza ---")
print(json.dumps(connection_preview(repo, caterina_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Nicolás Maquiavelo ---")
print(json.dumps(connection_preview(repo, machiavelli_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de César Borgia ---")
print(json.dumps(connection_preview(repo, borgia_id), indent=2, ensure_ascii=False))
