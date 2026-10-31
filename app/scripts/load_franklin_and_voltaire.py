import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import FactInput, HistoricalDate, PersonInput, SourceInput
from modules.graph.repository import GraphRepository
from modules.graph.service import connection_preview, validate_fact

repo = GraphRepository(driver)

louis_id = "ce132017-4ecd-4aa7-beb9-55450639c54b"

# 1. Crear a Benjamin Franklin
franklin_input = PersonInput(
    name="Benjamin Franklin",
    aliases=[
        "Benjamin Franklin",
        "Ben Franklin",
    ],
    description=(
        "Polímata, científico, impresor, filósofo y Padre Fundador de los Estados Unidos. "
        "Pionero del estudio de la electricidad (inventor del pararrayos) y artífice de la diplomacia "
        "en París que consolidó la alianza militar y financiera con Francia frente a Gran Bretaña."
    ),
    country="US",
    city_born="Boston",
    image_url="https://upload.wikimedia.org/wikipedia/commons/8/87/Joseph_Siffrein_Duplessis_-_Benjamin_Franklin_-_Google_Art_Project.jpg",
    wikidata_id="Q34969",
    birth=HistoricalDate(year=1706, month=1, day=17, precision="day"),
    death=HistoricalDate(year=1790, month=4, day=17, precision="day"),
).model_dump(mode="json")

franklin = repo.create("people", franklin_input)
franklin_id = franklin["id"]
print("Creado Benjamin Franklin con ID:", franklin_id)

# Ajustar compatibilidad
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
        id=franklin_id,
        rn="Benjamin Franklin",
        bkf="Benjamin Franklin",
        c="US",
        img=franklin_input["image_url"],
        occ="Científico, diplomático y Padre Fundador",
        desc=franklin_input["description"],
    )

# 2. Conectar Franklin con Luis XVI
source_franklin_louis = repo.create(
    "sources",
    SourceInput(
        title="Audience of Benjamin Franklin with King Louis XVI at Versailles (March 20, 1778)",
        url="https://en.wikipedia.org/wiki/Treaty_of_Alliance_(1778)",
        publisher="National Archives / French Diplomatic Archive",
        author="Diplomatic Records of the American Revolution",
    ).model_dump(mode="json"),
)
print("Fuente Franklin-Luis XVI creada:", source_franklin_louis["id"])

fact_fl = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=franklin_id,
            object_id=louis_id,
            source_id=source_franklin_louis["id"],
            source_locator="Recepción formal y audiencia en el Palacio de Versalles, 20 de marzo de 1778",
            note=(
                "El rey Luis XVI recibió en audiencia solemne en el Palacio de Versalles a Benjamin Franklin "
                "y a los comisionados estadounidenses para rubricar formalmente la alianza militar y política entre Francia y EE. UU."
            ),
            status="draft",
        ),
    ),
)
data_fl = {
    k: v
    for k, v in repo.get("facts", fact_fl["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_fl["status"] = "verified"
repo.update(
    "facts",
    fact_fl["id"],
    fact_fl["revision"],
    validate_fact(repo, data_fl),
    "verify",
)
print("Hecho Franklin <-> Luis XVI verificado.")

# 3. Crear a Voltaire
voltaire_input = PersonInput(
    name="Voltaire",
    aliases=[
        "François-Marie Arouet",
        "Voltaire",
    ],
    description=(
        "Escritor, filósofo, historiador y jurista francés. Máxima figura del Siglo de las Luces (Ilustración). "
        "Insigne defensor de la libertad de pensamiento, la tolerancia religiosa y la razón crítica. "
        "Autor de obras fundamentales como Cándido y el Diccionario filosófico."
    ),
    country="FR",
    city_born="París",
    image_url="https://upload.wikimedia.org/wikipedia/commons/b/bf/Nicolas_de_Largilli%C3%A8re_-_Portrait_de_Voltaire_%281694-1778%29_en_1718_-_P208_-_mus%C3%A9e_Carnavalet_-_5_%28cropped%29.jpg",
    wikidata_id="Q9068",
    birth=HistoricalDate(year=1694, month=11, day=21, precision="day"),
    death=HistoricalDate(year=1778, month=5, day=30, precision="day"),
).model_dump(mode="json")

voltaire = repo.create("people", voltaire_input)
voltaire_id = voltaire["id"]
print("Creado Voltaire con ID:", voltaire_id)

# Ajustar compatibilidad
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
        id=voltaire_id,
        rn="François-Marie Arouet",
        bkf="Voltaire",
        c="FR",
        img=voltaire_input["image_url"],
        occ="Filósofo y escritor de la Ilustración",
        desc=voltaire_input["description"],
    )

# 4. Conectar Voltaire con Franklin
source_voltaire_franklin = repo.create(
    "sources",
    SourceInput(
        title="Meeting of Voltaire and Benjamin Franklin at the French Academy of Sciences (April 1778)",
        url="https://en.wikipedia.org/wiki/Voltaire",
        publisher="Académie des Sciences / Condorcet Memoirs",
        author="Marquis de Condorcet & John Adams Journals",
    ).model_dump(mode="json"),
)
print("Fuente Voltaire-Franklin creada:", source_voltaire_franklin["id"])

fact_vf = repo.create(
    "facts",
    validate_fact(
        repo,
        FactInput(
            type_id="personal.met",
            subject_id=voltaire_id,
            object_id=franklin_id,
            source_id=source_voltaire_franklin["id"],
            source_locator="Sesión pública de la Academia de Ciencias de París, 29 de abril de 1778",
            note=(
                "Voltaire y Benjamin Franklin se encontraron en una célebre sesión pública de la Academia de Ciencias "
                "de París el 29 de abril de 1778, donde se abrazaron y besaron las mejillas ante los vítores del público, "
                "quien exclamó la inmortal frase: '¡He aquí a Solón abrazando a Sófocles!'."
            ),
            status="draft",
        ),
    ),
)
data_vf = {
    k: v
    for k, v in repo.get("facts", fact_vf["id"]).items()
    if k not in ("id", "revision", "created_at", "updated_at")
}
data_vf["status"] = "verified"
repo.update(
    "facts",
    fact_vf["id"],
    fact_vf["revision"],
    validate_fact(repo, data_vf),
    "verify",
)
print("Hecho Voltaire <-> Franklin verificado.")

# 5. Comprobar conexiones
print("\n--- Conexiones de Voltaire ---")
print(json.dumps(connection_preview(repo, voltaire_id), indent=2, ensure_ascii=False))

print("\n--- Conexiones de Franklin ---")
print(json.dumps(connection_preview(repo, franklin_id), indent=2, ensure_ascii=False))
