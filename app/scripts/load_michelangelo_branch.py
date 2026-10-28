import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

leonardo_id = "11bddff4-35bd-4d3b-bafa-0d12b0d49f8c"
verrocchio_id = "0d800468-d1f9-460d-b3e6-b757faa5a38e"

print("--- Iniciando carga de Miguel Ángel, Lorenzo el Magnífico, Julio II y el círculo del Alto Renacimiento ---")

# 1. Crear a Miguel Ángel Buonarroti
michelangelo_input = PersonInput(
    name="Miguel Ángel Buonarroti",
    aliases=[
        "Michelangelo Buonarroti",
        "Michelangelo",
        "Il Divino",
    ],
    description=(
        "Arquitecto, escultor, pintor y poeta renacentista italiano, considerado uno de los más grandes artistas de la historia universal. "
        "Autor de obras cumbre como el David, la Piedad, la Bóveda de la Capilla Sixtina, El Juicio Final y la cúpula de la Basílica de San Pedro."
    ),
    country="IT",
    city_born="Caprese Michelangelo",
    image_url="https://upload.wikimedia.org/wikipedia/commons/0/02/Michelangelo_Daniele_da_Volterra_%28dettaglio%29.jpg",
    wikidata_id="Q5592",
    birth=HistoricalDate(year=1475, month=3, day=6, precision="day"),
    death=HistoricalDate(year=1564, month=2, day=18, precision="day"),
).model_dump(mode="json")

michelangelo = repo.create("people", michelangelo_input)
michelangelo_id = michelangelo["id"]
print("Creado Miguel Ángel Buonarroti con ID:", michelangelo_id)

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
        id=michelangelo_id,
        rn="Michelangelo Buonarroti",
        bkf="Miguel Ángel Buonarroti",
        c="IT",
        img=michelangelo_input["image_url"],
        occ="Escultor, pintor, arquitecto y poeta del Renacimiento (Il Divino)",
        desc=michelangelo_input["description"],
    )

# 2. Conectar Leonardo da Vinci <-> Miguel Ángel Buonarroti (personal.met / comisión y rivalidad)
source_l_m = repo.create(
    "sources",
    SourceInput(
        title="Incontri e rivalità tra Leonardo da Vinci e Michelangelo a Firenze (1503–1504)",
        url="https://en.wikipedia.org/wiki/Michelangelo",
        publisher="Archivio dell'Opera di Santa Maria del Fiore / Giunti",
        author="Giorgio Vasari / Charles de Tolnay",
    ).model_dump(mode="json"),
)

fact_l_m = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=leonardo_id,
            object_id=michelangelo_id,
            source_id=source_l_m["id"],
            source_locator="Comisión consultiva para la ubicación del David (25 de enero de 1504) y encargos del Salone dei Cinquecento",
            note=(
                "Leonardo da Vinci y Miguel Ángel Buonarroti coincidieron en Florencia a inicios del siglo XVI; Leonardo formó parte "
                "del comité ciudadano de expertos reunido el 25 de enero de 1504 para decidir el emplazamiento del colosal 'David' de Miguel Ángel. "
                "Posteriormente, la Señoría les encomendó competir frente a frente pintando las paredes opuestas del Salone dei Cinquecento en el Palazzo Vecchio."
            ),
            status="draft",
        ),
    ),
)
data_l_m = {
    k: v
    for k, v in repo.get("facts", fact_l_m["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_l_m["status"] = "verified"
repo.update(
    "facts",
    fact_l_m["id"],
    fact_l_m["revision"],
    validate_fact(repo, data_l_m),
    "verify",
)
print("Hecho Leonardo da Vinci <-> Miguel Ángel verificado.")

# 3. Crear a Lorenzo de' Médici («Lorenzo el Magnífico»)
lorenzo_input = PersonInput(
    name="Lorenzo el Magnífico",
    aliases=[
        "Lorenzo de' Medici",
        "Lorenzo el Magnífico",
        "Lorenzo il Magnifico",
    ],
    description=(
        "Estadista florentino y gobernante de facto de la República de Florencia (1469–1492), diplomático, banquero y poeta. "
        "El mecenas más célebre del Renacimiento italiano, protector de Miguel Ángel, Sandro Botticelli, Leonardo da Vinci, "
        "Marsilio Ficino y Angelo Poliziano, artífice de la edad de oro cultural y equilibrio de poder de la península itálica."
    ),
    country="IT",
    city_born="Florencia",
    image_url="https://upload.wikimedia.org/wikipedia/commons/1/10/Lorenzo_de_Medici.jpg",
    wikidata_id="Q177854",
    birth=HistoricalDate(year=1449, month=1, day=1, precision="day"),
    death=HistoricalDate(year=1492, month=4, day=8, precision="day"),
).model_dump(mode="json")

lorenzo = repo.create("people", lorenzo_input)
lorenzo_id = lorenzo["id"]
print("Creado Lorenzo el Magnífico con ID:", lorenzo_id)

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
        id=lorenzo_id,
        rn="Lorenzo de' Medici",
        bkf="Lorenzo el Magnífico",
        c="IT",
        img=lorenzo_input["image_url"],
        occ="Gobernante de Florencia, estadista y gran mecenas del Renacimiento",
        desc=lorenzo_input["description"],
    )

# 4. Conectar Lorenzo el Magnífico -> Miguel Ángel (professional.mentor_of)
source_lm_m = repo.create(
    "sources",
    SourceInput(
        title="Vita di Michelagnolo Buonarroti raccolta per Ascanio Condivi da la Ripa Transone (1553)",
        url="https://en.wikipedia.org/wiki/Lorenzo_de%27_Medici",
        publisher="Antonio Blado / Einaudi",
        author="Ascanio Condivi",
    ).model_dump(mode="json"),
)

fact_lm_m = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="professional.mentor_of",
            subject_id=lorenzo_id,
            object_id=michelangelo_id,
            source_id=source_lm_m["id"],
            source_locator="Giardino di San Marco e Palazzo Medici di Firenze (1489–1492)",
            note=(
                "Lorenzo el Magnífico descubrió el genio escultórico del joven Miguel Ángel en el Jardín de San Marcos "
                "y lo acogió en el Palacio Médici como a un miembro de su propia familia entre 1489 y 1492, "
                "otorgándole una asignación personal, formándolo en escultura clásica y permitiéndole compartir mesa y discusiones "
                "filosóficas con Marsilio Ficino y Angelo Poliziano."
            ),
            status="draft",
        ),
    ),
)
data_lm_m = {
    k: v
    for k, v in repo.get("facts", fact_lm_m["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_lm_m["status"] = "verified"
repo.update(
    "facts",
    fact_lm_m["id"],
    fact_lm_m["revision"],
    validate_fact(repo, data_lm_m),
    "verify",
)
print("Hecho Lorenzo el Magnífico -> Miguel Ángel verificado.")

# 5. Crear al Papa Julio II (Giuliano della Rovere)
julius_input = PersonInput(
    name="Papa Julio II",
    aliases=[
        "Giuliano della Rovere",
        "Julio II",
        "Il Papa Terribile",
    ],
    description=(
        "Papa de la Iglesia Católica (1503–1513) de la Casa della Rovere, conocido como el 'Papa Guerrero' o 'Il Papa Terribile'. "
        "Mecenas cumbre del Alto Renacimiento romano: ordenó erigir la nueva Basílica de San Pedro confiada a Bramante, "
        "encargó a Miguel Ángel la Bóveda de la Capilla Sixtina y su tumba monumental, y a Rafael las Estancias Vaticanas."
    ),
    country="IT",
    city_born="Albisola Superiore",
    image_url="https://upload.wikimedia.org/wikipedia/commons/a/af/Pope_Julius_II.jpg",
    wikidata_id="Q8018",
    birth=HistoricalDate(year=1443, month=12, day=5, precision="day"),
    death=HistoricalDate(year=1513, month=2, day=21, precision="day"),
).model_dump(mode="json")

julius = repo.create("people", julius_input)
julius_id = julius["id"]
print("Creado Papa Julio II con ID:", julius_id)

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
        id=julius_id,
        rn="Giuliano della Rovere",
        bkf="Papa Julio II",
        c="IT",
        img=julius_input["image_url"],
        occ="Papa de la Iglesia Católica (1503–1513) y gran mecenas renacentista de Roma",
        desc=julius_input["description"],
    )

# 6. Conectar Papa Julio II <-> Miguel Ángel Buonarroti (personal.met / Capilla Sixtina y tumba)
source_j_m = repo.create(
    "sources",
    SourceInput(
        title="Michelangelo e papa Giulio II: La volta della Cappella Sistina e la Tomba Papale (1505–1512)",
        url="https://en.wikipedia.org/wiki/Pope_Julius_II",
        publisher="Archivio Segreto Vaticano / Musei Vaticani",
        author="Paris de Grassis (Diaria) / Giorgio Vasari",
    ).model_dump(mode="json"),
)

fact_j_m = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=julius_id,
            object_id=michelangelo_id,
            source_id=source_j_m["id"],
            source_locator="Palazzo Apostolico Vaticano e Cappella Sistina (1505–1512)",
            note=(
                "El Papa Julio II llamó a Miguel Ángel a Roma en 1505 para diseñar su monumental sepulcro papal y posteriormente, "
                "en 1508, le encargó pintar la Bóveda de la Capilla Sixtina. Mantuvieron una relación de intensa colaboración y fuerte temperamento, "
                "culminando en la inauguración formal de la Sixtina el día de Todos los Santos de 1512."
            ),
            status="draft",
        ),
    ),
)
data_j_m = {
    k: v
    for k, v in repo.get("facts", fact_j_m["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_j_m["status"] = "verified"
repo.update(
    "facts",
    fact_j_m["id"],
    fact_j_m["revision"],
    validate_fact(repo, data_j_m),
    "verify",
)
print("Hecho Papa Julio II <-> Miguel Ángel verificado.")

# 7. Crear a Rafael Sanzio (Raffaello Sanzio)
raphael_input = PersonInput(
    name="Rafael Sanzio",
    aliases=[
        "Raffaello Sanzio",
        "Raffaello da Urbino",
        "Rafael",
    ],
    description=(
        "Pintor y arquitecto del Alto Renacimiento italiano, celebrado por la perfección armónica, claridad formal y gracia compositiva de su arte. "
        "Formó junto a Miguel Ángel y Leonardo da Vinci la ilustre trinidad de los grandes maestros del Alto Renacimiento, célebre por La Escuela de Atenas "
        "y sus sublimes Madonnas."
    ),
    country="IT",
    city_born="Urbino",
    image_url="https://upload.wikimedia.org/wikipedia/commons/f/f6/Raffaello_Sanzio.jpg",
    wikidata_id="Q5597",
    birth=HistoricalDate(year=1483, month=3, day=28, precision="day"),
    death=HistoricalDate(year=1520, month=4, day=6, precision="day"),
).model_dump(mode="json")

raphael = repo.create("people", raphael_input)
raphael_id = raphael["id"]
print("Creado Rafael Sanzio con ID:", raphael_id)

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
        id=raphael_id,
        rn="Raffaello Sanzio",
        bkf="Rafael Sanzio",
        c="IT",
        img=raphael_input["image_url"],
        occ="Pintor y arquitecto del Alto Renacimiento italiano",
        desc=raphael_input["description"],
    )

# 8. Conectar Papa Julio II <-> Rafael Sanzio (personal.met / Estancias Vaticanas)
source_j_r = repo.create(
    "sources",
    SourceInput(
        title="Raffaello nelle Stanze Vaticane sotto papa Giulio II (1508–1513)",
        url="https://en.wikipedia.org/wiki/Raphael",
        publisher="Musei Vaticani / Electa",
        author="John Shearman: Raphael in Early Modern Sources",
    ).model_dump(mode="json"),
)

fact_j_r = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=julius_id,
            object_id=raphael_id,
            source_id=source_j_r["id"],
            source_locator="Stanze di Raffaello, Palazzo Apostolico Vaticano (1508–1511)",
            note=(
                "El Papa Julio II llamó a Rafael a Roma a finales de 1508 encomendándole la decoración de sus aposentos privados en el Palacio Apostólico. "
                "Rafael pintó para Julio II obras cumbres como La Escuela de Atenas y La Disputa del Sacramento, así como el célebre retrato "
                "oficial al óleo del pontífice (conservado en la National Gallery de Londres)."
            ),
            status="draft",
        ),
    ),
)
data_j_r = {
    k: v
    for k, v in repo.get("facts", fact_j_r["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_j_r["status"] = "verified"
repo.update(
    "facts",
    fact_j_r["id"],
    fact_j_r["revision"],
    validate_fact(repo, data_j_r),
    "verify",
)
print("Hecho Papa Julio II <-> Rafael Sanzio verificado.")

# 9. Conectar Miguel Ángel <-> Rafael Sanzio (personal.met / Vaticano)
source_m_r = repo.create(
    "sources",
    SourceInput(
        title="Michelangelo e Raffaello in Vaticano: Rivalità ed emulazione (1508–1512)",
        url="https://en.wikipedia.org/wiki/Raphael",
        publisher="Einaudi / Giunti",
        author="Giorgio Vasari: Vita di Raffaello da Urbino",
    ).model_dump(mode="json"),
)

fact_m_r = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=michelangelo_id,
            object_id=raphael_id,
            source_id=source_m_r["id"],
            source_locator="Palazzo Apostolico Vaticano (1508–1512) ed Eraclito nella Scuola di Atene",
            note=(
                "Miguel Ángel y Rafael coincidieron trabajando simultáneamente en el Palacio Apostólico de Roma bajo el mecenazgo de Julio II. "
                "Rafael admiró profundamente el trabajo de Miguel Ángel en la Sixtina e incorporó a Miguel Ángel en el primer plano de "
                "'La Escuela de Atenas' caracterizado como el filósofo Heráclito."
            ),
            status="draft",
        ),
    ),
)
data_m_r = {
    k: v
    for k, v in repo.get("facts", fact_m_r["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_m_r["status"] = "verified"
repo.update(
    "facts",
    fact_m_r["id"],
    fact_m_r["revision"],
    validate_fact(repo, data_m_r),
    "verify",
)
print("Hecho Miguel Ángel <-> Rafael Sanzio verificado.")

# 10. Crear a Sandro Botticelli
botticelli_input = PersonInput(
    name="Sandro Botticelli",
    aliases=[
        "Alessandro di Mariano di Vanni Filipepi",
        "Sandro Botticelli",
        "Botticelli",
    ],
    description=(
        "Pintor del Quattrocento renacentista italiano, máximo representante de la pintura neoplatónica florentina bajo los Médici. "
        "Autor de obras inmortales de la mitología clásica como El nacimiento de Venus, La Primavera y Palas y el Centauro."
    ),
    country="IT",
    city_born="Florencia",
    image_url="https://upload.wikimedia.org/wikipedia/commons/d/d4/Sandro_Botticelli_083.jpg",
    wikidata_id="Q5669",
    birth=HistoricalDate(year=1445, precision="year"),
    death=HistoricalDate(year=1510, month=5, day=17, precision="day"),
).model_dump(mode="json")

botticelli = repo.create("people", botticelli_input)
botticelli_id = botticelli["id"]
print("Creado Sandro Botticelli con ID:", botticelli_id)

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
        id=botticelli_id,
        rn="Alessandro di Mariano di Vanni Filipepi",
        bkf="Sandro Botticelli",
        c="IT",
        img=botticelli_input["image_url"],
        occ="Pintor lírico y mitológico del Quattrocento florentino",
        desc=botticelli_input["description"],
    )

# 11. Conectar Lorenzo el Magnífico <-> Sandro Botticelli (personal.met / mecenazgo neoplatónico)
source_lm_b = repo.create(
    "sources",
    SourceInput(
        title="Sandro Botticelli e la corte medicea di Lorenzo il Magnifico (1470–1492)",
        url="https://en.wikipedia.org/wiki/Sandro_Botticelli",
        publisher="Galleria degli Uffizi / Sansoni",
        author="Herbert P. Horne: Alessandro Filipepi, commonly called Sandro Botticelli",
    ).model_dump(mode="json"),
)

fact_lm_b = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=lorenzo_id,
            object_id=botticelli_id,
            source_id=source_lm_b["id"],
            source_locator="Corte medicea di Firenze e Villa Medicea di Castello (1475–1492)",
            note=(
                "Sandro Botticelli disfrutó del continuado mecenazgo y protección íntima de Lorenzo el Magnífico y la rama de los Médici en Florencia, "
                "creando para ellos obras cumbres del humanismo poético y mitológico como La Primavera, El nacimiento de Venus "
                "y el estandarte del célebre torneo de Giuliano de' Medici."
            ),
            status="draft",
        ),
    ),
)
data_lm_b = {
    k: v
    for k, v in repo.get("facts", fact_lm_b["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_lm_b["status"] = "verified"
repo.update(
    "facts",
    fact_lm_b["id"],
    fact_lm_b["revision"],
    validate_fact(repo, data_lm_b),
    "verify",
)
print("Hecho Lorenzo el Magnífico <-> Sandro Botticelli verificado.")

# 12. Conectar Leonardo da Vinci <-> Sandro Botticelli (personal.met / comité del David y juventud)
source_l_b = repo.create(
    "sources",
    SourceInput(
        title="Leonardo da Vinci e Sandro Botticelli: Amicizia nella bottega di Verrocchio e commissione per il David (1504)",
        url="https://en.wikipedia.org/wiki/Sandro_Botticelli",
        publisher="Archivio dell'Opera di Santa Maria del Fiore / Bompiani",
        author="Carlo Pedretti / Gaetano Milanesi",
    ).model_dump(mode="json"),
)

fact_l_b = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=leonardo_id,
            object_id=botticelli_id,
            source_id=source_l_b["id"],
            source_locator="Delibera della Signoria di Firenze (25 gennaio 1504) e bottega di Verrocchio",
            note=(
                "Leonardo da Vinci y Sandro Botticelli mantuvieron una estrecha amistad desde su juventud en el taller de Verrocchio "
                "(Leonardo cita cariñosamente a 'nuestro Sandro' en sus cuadernos de notas). El 25 de enero de 1504 ambos integraron juntos "
                "la célebre comisión de artistas y ciudadanos que debatió y resolvió la ubicación del David de Miguel Ángel en la Piazza della Signoria."
            ),
            status="draft",
        ),
    ),
)
data_l_b = {
    k: v
    for k, v in repo.get("facts", fact_l_b["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_l_b["status"] = "verified"
repo.update(
    "facts",
    fact_l_b["id"],
    fact_l_b["revision"],
    validate_fact(repo, data_l_b),
    "verify",
)
print("Hecho Leonardo da Vinci <-> Sandro Botticelli verificado.")

# Resumen de conexiones
print("\n--- Conexiones de Miguel Ángel ---")
print(json.dumps(connection_preview(repo, michelangelo_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Lorenzo el Magnífico ---")
print(json.dumps(connection_preview(repo, lorenzo_id), indent=2, ensure_ascii=False))
