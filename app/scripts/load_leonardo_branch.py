import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

caterina_id = "cf5d6878-d12b-403b-815b-900c5bc8a8b3"
machiavelli_id = "0ac7ae32-dbf1-4206-8275-60a4968fcb5f"
borgia_id = "f2dafa14-e01d-432d-aa90-81df965de520"

print("--- Iniciando carga de Leonardo da Vinci y su círculo histórico ---")

# 1. Crear a Leonardo da Vinci
leonardo_input = PersonInput(
    name="Leonardo da Vinci",
    aliases=[
        "Leonardo di ser Piero da Vinci",
        "Leonardo da Vinci",
        "Da Vinci",
    ],
    description=(
        "Polímata, pintor, anatomista, arquitecto, paleontólogo, artista, botánico, científico, escritor, escultor, filósofo, "
        "ingeniero, inventor, músico y poeta renacentista italiano. Considerado el arquetipo universal del hombre del Renacimiento "
        "y uno de los mayores genios creativos de la historia, autor de la Mona Lisa, La Última Cena y el Hombre de Vitruvio."
    ),
    country="IT",
    city_born="Vinci",
    image_url="https://upload.wikimedia.org/wikipedia/commons/3/38/Leonardo_da_Vinci_-_presumed_self-portrait_-_WGA12798.jpg",
    wikidata_id="Q762",
    birth=HistoricalDate(year=1452, month=4, day=15, precision="day"),
    death=HistoricalDate(year=1519, month=5, day=2, precision="day"),
).model_dump(mode="json")

leonardo = repo.create("people", leonardo_input)
leonardo_id = leonardo["id"]
print("Creado Leonardo da Vinci con ID:", leonardo_id)

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
        id=leonardo_id,
        rn="Leonardo di ser Piero da Vinci",
        bkf="Leonardo da Vinci",
        c="IT",
        img=leonardo_input["image_url"],
        occ="Polímata del Renacimiento: pintor, anatomista, científico e ingeniero universal",
        desc=leonardo_input["description"],
    )

# 2. Conectar César Borgia <-> Leonardo da Vinci (personal.met / servicio como Ingeniero General)
source_b_l = repo.create(
    "sources",
    SourceInput(
        title="Patente de nombramiento de Leonardo da Vinci como Arquitecto e Ingeniero General por César Borgia (1502)",
        url="https://en.wikipedia.org/wiki/Leonardo_da_Vinci",
        publisher="Archivio di Stato di Firenze / Biblioteca Nazionale Centrale",
        author="Cesare Borgia, Duca di Romagna e di Valentinois",
    ).model_dump(mode="json"),
)

fact_b_l = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=borgia_id,
            object_id=leonardo_id,
            source_id=source_b_l["id"],
            source_locator="Decreto patente ducal expedido en Pavía el 18 de agosto de 1502 a favor de Leonardo Vinci",
            note=(
                "En agosto de 1502, César Borgia expidió un célebre salvoconducto y patente nombrando a Leonardo da Vinci su "
                "'Architecto et Ingegnero Generale'. Leonardo viajó con César Borgia por Romaña inspeccionando fortalezas y puertos en "
                "Urbino, Cesena, Pésaro e Imola, diseñando planos urbanísticos y maquinaria militar defensiva."
            ),
            status="draft",
        ),
    ),
)
data_b_l = {
    k: v
    for k, v in repo.get("facts", fact_b_l["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_b_l["status"] = "verified"
repo.update(
    "facts",
    fact_b_l["id"],
    fact_b_l["revision"],
    validate_fact(repo, data_b_l),
    "verify",
)
print("Hecho César Borgia <-> Leonardo da Vinci verificado.")

# 3. Conectar Nicolás Maquiavelo <-> Leonardo da Vinci (personal.met / colaboración)
source_m_l = repo.create(
    "sources",
    SourceInput(
        title="Incontri tra Niccolò Machiavelli e Leonardo da Vinci a Imola e Firenze (1502–1504)",
        url="https://en.wikipedia.org/wiki/Niccol%C3%B2_Machiavelli",
        publisher="Cancelleria Fiorentina / Einaudi",
        author="Maurizio Viroli: Il sorriso di Niccolò / Roger D. Masters: Fortune Is a River",
    ).model_dump(mode="json"),
)

fact_m_l = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=machiavelli_id,
            object_id=leonardo_id,
            source_id=source_m_l["id"],
            source_locator="Imola (otoño de 1502) y Palazzo Vecchio de Florencia (1503–1504)",
            note=(
                "Nicolás Maquiavelo y Leonardo da Vinci se conocieron en el cuartel general de César Borgia en Imola en el otoño de 1502. "
                "Posteriormente en Florencia colaboraron directamente en el ambicioso proyecto estratégico de la República para desviar el río Arno "
                "y en el encargo oficial de los frescos del Salone dei Cinquecento en el Palazzo Vecchio."
            ),
            status="draft",
        ),
    ),
)
data_m_l = {
    k: v
    for k, v in repo.get("facts", fact_m_l["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_m_l["status"] = "verified"
repo.update(
    "facts",
    fact_m_l["id"],
    fact_m_l["revision"],
    validate_fact(repo, data_m_l),
    "verify",
)
print("Hecho Nicolás Maquiavelo <-> Leonardo da Vinci verificado.")

# 4. Crear a Andrea del Verrocchio
verrocchio_input = PersonInput(
    name="Andrea del Verrocchio",
    aliases=[
        "Andrea di Michele di Francesco de' Cioni",
        "Andrea del Verrocchio",
        "Verrocchio",
    ],
    description=(
        "Escultor, pintor y orfebre renacentista florentino, director del taller artístico más influyente de Florencia en la segunda mitad del siglo XV. "
        "Maestro formador de Leonardo da Vinci, Pietro Perugino, Domenico Ghirlandaio y Sandro Botticelli, célebre por su monumento ecuestre a Bartolomeo Colleoni."
    ),
    country="IT",
    city_born="Florencia",
    image_url="https://upload.wikimedia.org/wikipedia/commons/a/aa/Andrea_del_Castagno%2C_portrait_de_Verrocchio%2C_vers_1470.jpg",
    wikidata_id="Q183458",
    birth=HistoricalDate(year=1435, precision="year"),
    death=HistoricalDate(year=1488, month=10, day=7, precision="day"),
).model_dump(mode="json")

verrocchio = repo.create("people", verrocchio_input)
verrocchio_id = verrocchio["id"]
print("Creado Andrea del Verrocchio con ID:", verrocchio_id)

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
        id=verrocchio_id,
        rn="Andrea di Michele di Francesco de' Cioni",
        bkf="Andrea del Verrocchio",
        c="IT",
        img=verrocchio_input["image_url"],
        occ="Escultor, pintor y maestro del taller renacentista de Florencia",
        desc=verrocchio_input["description"],
    )

# 5. Conectar Verrocchio -> Leonardo da Vinci (professional.mentor_of)
source_v_l = repo.create(
    "sources",
    SourceInput(
        title="Le Vite de' più eccellenti pittori, scultori, e architettori: Vita di Lionardo da Vinci",
        url="https://en.wikipedia.org/wiki/Andrea_del_Verrocchio",
        publisher="Lorenzo Torrentino / Giunti",
        author="Giorgio Vasari",
    ).model_dump(mode="json"),
)

fact_v_l = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="professional.mentor_of",
            subject_id=verrocchio_id,
            object_id=leonardo_id,
            source_id=source_v_l["id"],
            source_locator="Bottega di Verrocchio a Firenze (c. 1466–1476) e pala del Battesimo di Cristo (Uffizi)",
            note=(
                "Andrea del Verrocchio fue el maestro formativo de Leonardo da Vinci en su influyente taller florentino desde c. 1466. "
                "Allí Leonardo aprendió dibujo, pintura, escultura, fundición y metalistería, colaborando célebremente con su maestro "
                "en la tabla de 'El bautismo de Cristo' (Uffizi), donde Leonardo pintó el ángel arrodillado de la izquierda."
            ),
            status="draft",
        ),
    ),
)
data_v_l = {
    k: v
    for k, v in repo.get("facts", fact_v_l["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_v_l["status"] = "verified"
repo.update(
    "facts",
    fact_v_l["id"],
    fact_v_l["revision"],
    validate_fact(repo, data_v_l),
    "verify",
)
print("Hecho Verrocchio -> Leonardo da Vinci verificado.")

# 6. Crear a Ludovico Sforza ("Il Moro")
ludovico_input = PersonInput(
    name="Ludovico Sforza",
    aliases=[
        "Ludovico Maria Sforza",
        "Il Moro",
        "Ludovico el Moro",
    ],
    description=(
        "Duque de Milán (1494–1499) y regente de la dinastía Sforza, hijo de Francesco Sforza. "
        "Fue uno de los mecenas más espléndidos del Renacimiento, reuniendo en su corte a Leonardo da Vinci "
        "(a quien encargó La Última Cena y el Gran Cavallo) y a Donato Bramante."
    ),
    country="IT",
    city_born="Vigevano",
    image_url="https://upload.wikimedia.org/wikipedia/commons/8/8f/Pala_Sforzesca_-_detail_01.jpg",
    wikidata_id="Q207390",
    birth=HistoricalDate(year=1452, month=7, day=27, precision="day"),
    death=HistoricalDate(year=1508, month=5, day=27, precision="day"),
).model_dump(mode="json")

ludovico = repo.create("people", ludovico_input)
ludovico_id = ludovico["id"]
print("Creado Ludovico Sforza con ID:", ludovico_id)

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
        id=ludovico_id,
        rn="Ludovico Maria Sforza",
        bkf="Ludovico Sforza",
        c="IT",
        img=ludovico_input["image_url"],
        occ="Duque de Milán y mecenas renacentista (Casa Sforza)",
        desc=ludovico_input["description"],
    )

# 7. Conectar Ludovico Sforza <-> Leonardo da Vinci (personal.met / mecenazgo en Milán)
source_ls_l = repo.create(
    "sources",
    SourceInput(
        title="Leonardo da Vinci alla corte di Ludovico il Moro a Milano (1482–1499)",
        url="https://en.wikipedia.org/wiki/Ludovico_Sforza",
        publisher="Archivio di Stato di Milano / Electa",
        author="Carlo Pedretti: Leonardo a Milano",
    ).model_dump(mode="json"),
)

fact_ls_l = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=ludovico_id,
            object_id=leonardo_id,
            source_id=source_ls_l["id"],
            source_locator="Corte Sforzesca di Milano: Lettera d'impiego del 1482 e committenza del Cenacolo di Santa Maria delle Grazie",
            note=(
                "Leonardo da Vinci se presentó ante Ludovico Sforza en 1482 con una célebre carta ofreciendo sus habilidades como ingeniero militar y pintor. "
                "Permaneció casi dos décadas a su servicio en Milán, donde Ludovico le encargó obras cumbre como La Última Cena en el refectorio de Santa Maria delle Grazie "
                "y el colosal monumento ecuestre a Francesco Sforza."
            ),
            status="draft",
        ),
    ),
)
data_ls_l = {
    k: v
    for k, v in repo.get("facts", fact_ls_l["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_ls_l["status"] = "verified"
repo.update(
    "facts",
    fact_ls_l["id"],
    fact_ls_l["revision"],
    validate_fact(repo, data_ls_l),
    "verify",
)
print("Hecho Ludovico Sforza <-> Leonardo da Vinci verificado.")

# 8. Crear a Galeazzo Maria Sforza
galeazzo_input = PersonInput(
    name="Galeazzo Maria Sforza",
    aliases=[
        "Galeazzo Maria Sforza",
        "Galeazzo Sforza",
    ],
    description=(
        "Quinto Duque de Milán (1466–1476), sucesor e hijo de Francesco I Sforza y Bianca Maria Visconti. "
        "Padre de Caterina Sforza y hermano de Ludovico el Moro, fue un importante promotor de la música polifónica y la economía lombarda."
    ),
    country="IT",
    city_born="Fermo",
    image_url="https://upload.wikimedia.org/wikipedia/commons/9/92/Piero_Pollaiuolo_Portrait_of_Galeazzo_Maria_Sforza.jpg",
    wikidata_id="Q315286",
    birth=HistoricalDate(year=1444, month=1, day=24, precision="day"),
    death=HistoricalDate(year=1476, month=12, day=26, precision="day"),
).model_dump(mode="json")

galeazzo = repo.create("people", galeazzo_input)
galeazzo_id = galeazzo["id"]
print("Creado Galeazzo Maria Sforza con ID:", galeazzo_id)

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
        id=galeazzo_id,
        rn="Galeazzo Maria Sforza",
        bkf="Galeazzo Maria Sforza",
        c="IT",
        img=galeazzo_input["image_url"],
        occ="Duque de Milán (Casa Sforza)",
        desc=galeazzo_input["description"],
    )

# 9. Conectar Galeazzo Maria Sforza -> Caterina Sforza (family.parent_of)
source_gm_cs = repo.create(
    "sources",
    SourceInput(
        title="Genealogia Sforzesca: Nascita e legittimazione di Caterina Sforza figlia di Galeazzo Maria",
        url="https://en.wikipedia.org/wiki/Caterina_Sforza",
        publisher="Archivio Storico Lombardo / Società Storica Lombarda",
        author="Pier Desiderio Pasolini: Caterina Sforza",
    ).model_dump(mode="json"),
)

fact_gm_cs = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.parent_of",
            subject_id=galeazzo_id,
            object_id=caterina_id,
            source_id=source_gm_cs["id"],
            source_locator="Archivio di Stato di Milano: Nascita di Caterina Sforza (1463) e successivo atto di legittimazione ducale",
            note=(
                "Galeazzo Maria Sforza fue el padre de Caterina Sforza, nacida de su relación con Lucrezia Landriani. "
                "Caterina fue legitimada formalmente y educada en la corte ducal del Castillo Sforzesco de Milán junto a la nobleza sforzesca."
            ),
            status="draft",
        ),
    ),
)
data_gm_cs = {
    k: v
    for k, v in repo.get("facts", fact_gm_cs["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_gm_cs["status"] = "verified"
repo.update(
    "facts",
    fact_gm_cs["id"],
    fact_gm_cs["revision"],
    validate_fact(repo, data_gm_cs),
    "verify",
)
print("Hecho Galeazzo Maria Sforza -> Caterina Sforza verificado.")

# 10. Conectar Galeazzo Maria Sforza <-> Ludovico Sforza (family.sibling_of)
source_gm_ls = repo.create(
    "sources",
    SourceInput(
        title="Archivio Visconteo-Sforzesco: I figli del duca Francesco Sforza e di Bianca Maria Visconti",
        url="https://en.wikipedia.org/wiki/Ludovico_Sforza",
        publisher="Archivio di Stato di Milano",
        author="Registri della Cancelleria Ducale di Milano",
    ).model_dump(mode="json"),
)

fact_gm_ls = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="family.sibling_of",
            subject_id=galeazzo_id,
            object_id=ludovico_id,
            source_id=source_gm_ls["id"],
            source_locator="Albero genealogico della Casa Sforza: Fratelli legittimi nati dal matrimonio di Francesco Sforza e Bianca Maria Visconti",
            note=(
                "Galeazzo Maria Sforza y Ludovico Sforza 'Il Moro' eran hermanos carnales, hijos legítimos del primer duque sforzesco de Milán, "
                "Francesco I Sforza, y de la heredera viscontea Bianca Maria Visconti."
            ),
            status="draft",
        ),
    ),
)
data_gm_ls = {
    k: v
    for k, v in repo.get("facts", fact_gm_ls["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_gm_ls["status"] = "verified"
repo.update(
    "facts",
    fact_gm_ls["id"],
    fact_gm_ls["revision"],
    validate_fact(repo, data_gm_ls),
    "verify",
)
print("Hecho Galeazzo Maria Sforza <-> Ludovico Sforza verificado.")

# 11. Crear a Francisco I de Francia (Francis I)
francisco_input = PersonInput(
    name="Francisco I de Francia",
    aliases=[
        "François Ier",
        "Francis I of France",
        "El Padre de las Letras",
    ],
    description=(
        "Rey de Francia (1515–1547) de la rama Valois-Angulema, monarca emblemático del Renacimiento francés. "
        "Gran mecenas de las artes que atrajo a Leonardo da Vinci a Francia y adquirió la Mona Lisa, fundador del Collège de France "
        "y gran rival del emperador Carlos V."
    ),
    country="FR",
    city_born="Cognac",
    image_url="https://upload.wikimedia.org/wikipedia/commons/8/87/Fran%C3%A7ois_Ier_Louvre.jpg",
    wikidata_id="Q129857",
    birth=HistoricalDate(year=1494, month=9, day=12, precision="day"),
    death=HistoricalDate(year=1547, month=3, day=31, precision="day"),
).model_dump(mode="json")

francisco = repo.create("people", francisco_input)
francisco_id = francisco["id"]
print("Creado Francisco I de Francia con ID:", francisco_id)

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
        id=francisco_id,
        rn="François Ier de France",
        bkf="Francisco I de Francia",
        c="FR",
        img=francisco_input["image_url"],
        occ="Rey de Francia y mecenas del Renacimiento francés (Casa de Valois)",
        desc=francisco_input["description"],
    )

# 12. Conectar Francisco I <-> Leonardo da Vinci (personal.met / mecenazgo en Francia)
source_f_l = repo.create(
    "sources",
    SourceInput(
        title="Léonard de Vinci au service du roi François Ier au Château du Clos Lucé (1516–1519)",
        url="https://en.wikipedia.org/wiki/Francis_I_of_France",
        publisher="Archives Nationales de France / Domaine du Clos Lucé",
        author="Registres des dépenses de la Maison du Roi / Giorgio Vasari",
    ).model_dump(mode="json"),
)

fact_f_l = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=francisco_id,
            object_id=leonardo_id,
            source_id=source_f_l["id"],
            source_locator="Château d'Amboise et Manoir du Clos Lucé (1516–1519)",
            note=(
                "El rey Francisco I de Francia invitó personalmente a Leonardo da Vinci a residir en Francia en 1516, otorgándole la residencia del "
                "Castillo du Clos Lucé junto al castillo real de Amboise, una generosa pensión y el título de 'Premier peintre et ingénieur et architecte du Roi'. "
                "Francisco I visitaba con asiduidad a Leonardo para conversar sobre arte y filosofía, y conservó sus obras maestras, incluida la Gioconda."
            ),
            status="draft",
        ),
    ),
)
data_f_l = {
    k: v
    for k, v in repo.get("facts", fact_f_l["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_f_l["status"] = "verified"
repo.update(
    "facts",
    fact_f_l["id"],
    fact_f_l["revision"],
    validate_fact(repo, data_f_l),
    "verify",
)
print("Hecho Francisco I <-> Leonardo da Vinci verificado.")

# Resumen de conexiones para Leonardo da Vinci
print("\n--- Conexiones de Leonardo da Vinci ---")
print(json.dumps(connection_preview(repo, leonardo_id), indent=2, ensure_ascii=False))
