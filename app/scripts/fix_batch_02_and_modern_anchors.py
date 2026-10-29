import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.repository import GraphRepository
from modules.graph.models import FactInput, Period, HistoricalDate, LocationInput
from modules.graph.service import validate_fact, shortest_path
from scripts.batch_loader_utils import fetch_wikidata_info, upsert_verified_fact, upsert_source, upsert_work

repo = GraphRepository(driver)

print("--- 1. Corrigiendo QID e imagen de Luis Miguel y Checo Pérez ---")
with driver.session() as session:
    # Luis Miguel -> Q215766
    info_lm = fetch_wikidata_info("Q215766")
    img_lm = info_lm.get("image_url")
    session.run(
        """
        MATCH (p:Person)
        WHERE toLower(coalesce(p.search_name, p.real_name)) = 'luis miguel'
        SET p.wikidata_id = 'Q215766',
            p.image_url = $img
        """,
        img=img_lm
    )
    print(f"  Luis Miguel actualizado a Q215766 (Img: {'OK' if img_lm else 'None'})")

    # Checo Pérez -> Q173035
    info_sp = fetch_wikidata_info("Q173035")
    img_sp = info_sp.get("image_url")
    session.run(
        """
        MATCH (p:Person)
        WHERE toLower(coalesce(p.search_name, p.real_name)) = 'sergio perez'
           OR toLower(coalesce(p.search_name, p.real_name)) = 'sergio pérez'
        SET p.wikidata_id = 'Q173035',
            p.image_url = $img
        """,
        img=img_sp
    )
    print(f"  Sergio Pérez actualizado a Q173035 (Img: {'OK' if img_sp else 'None'})")

print("\n--- 2. Actualizando periodo de Lionel Messi en FC Barcelona a 2004–2021 ---")
with driver.session() as session:
    # Buscar el hecho de membresía de Messi en FC Barcelona
    res = session.run(
        """
        MATCH (p:Person)-[:SUBJECT_OF]->(f:Fact {type_id: 'sports.same_team'})-[:OBJECT]->(o:Organization)
        WHERE (p.wikidata_id = 'Q615' OR toLower(coalesce(p.search_name, p.real_name)) = 'lionel messi')
          AND toLower(coalesce(o.search_name, '')) CONTAINS 'barcelona'
        RETURN f.id AS id, f.revision AS revision, f.data AS data
        """
    ).data()
    for row in res:
        fid = row["id"]
        current = repo.get("facts", fid)
        data = {k: v for k, v in current.items() if k not in ("id", "revision", "created_at", "updated_at")}
        data["period"] = {
            "start": {"year": 2004, "month": 10, "precision": "month", "approximate": False},
            "end": {"year": 2021, "month": 8, "precision": "month", "approximate": False}
        }
        data["status"] = "verified"
        repo.update("facts", fid, current["revision"], validate_fact(repo, data), "verify")
        print(f"  Hecho {fid} de Messi en FC Barcelona actualizado a 2004–2021.")

print("\n--- 3. Conectando a 'Los Tres Amigos' (Guillermo del Toro, Alfonso Cuarón e Iñárritu en Cha Cha Chá Films / Rudo y Cursi) ---")
# Obtener IDs
with driver.session() as session:
    gdt_id = session.run("MATCH (p:Person {wikidata_id: 'Q219124'}) RETURN p.id AS id").single()["id"]
    cuaron_id = session.run("MATCH (p:Person {wikidata_id: 'Q28028'}) RETURN p.id AS id").single()["id"]
    inarritu_id = session.run("MATCH (p:Person {wikidata_id: 'Q55215'}) RETURN p.id AS id").single()["id"]

source_id = upsert_source({
    "title": "Rudo y Cursi",
    "url": "https://en.wikipedia.org/wiki/Rudo_y_Cursi",
    "publisher": "Wikipedia",
    "citation": "Película producida por Cha Cha Chá Films (Alfonso Cuarón, Guillermo del Toro y Alejandro González Iñárritu), 2008.",
    "locator": "Production"
})

period_rudo = Period(
    start=HistoricalDate(year=2007, precision="year"),
    end=HistoricalDate(year=2008, precision="year")
)

work_id = upsert_work(
    name="Rudo y Cursi (Cha Cha Chá Films, 2008)",
    kind="film",
    period=period_rudo,
    description="Primera producción cinematográfica de la productora Cha Cha Chá Films, fundada conjuntamente por los 'Tres Amigos': Alfonso Cuarón, Guillermo del Toro y Alejandro González Iñárritu."
)

loc_mex = LocationInput(name="Cihuatlán, Jalisco", city="Cihuatlán", country="MX", lat=19.2333, lng=-104.5667)

for name, pid in [("Guillermo del Toro", gdt_id), ("Alfonso Cuarón", cuaron_id), ("Alejandro González Iñárritu", inarritu_id)]:
    f = FactInput(
        type_id="arts.collaborated_on_work",
        subject_id=pid,
        object_id=work_id,
        source_id=source_id,
        source_locator="Production",
        role="creator",
        period=period_rudo,
        status="draft",
        note=f"{name} co-produjo 'Rudo y Cursi' (2008) como socio fundador de Cha Cha Chá Films.",
        location=loc_mex
    )
    fid = upsert_verified_fact(f)
    print(f"  {name} conectado a 'Rudo y Cursi' -> Fact {fid}")

print("\n--- 4. Verificación de conectividad de Ronaldinho, Del Toro y Cuarón ---")
dicaprio_id = repo.driver.session().run("MATCH (p:Person {wikidata_id: 'Q38111'}) RETURN p.id AS id").single()["id"]
ronaldinho_id = repo.driver.session().run("MATCH (p:Person {wikidata_id: 'Q39444'}) RETURN p.id AS id").single()["id"]

for name, pid in [("Ronaldinho", ronaldinho_id), ("Guillermo del Toro", gdt_id), ("Alfonso Cuarón", cuaron_id)]:
    p = shortest_path(repo, pid, dicaprio_id)
    if p.get("found"):
        print(f"  OK: {name} -> Leonardo DiCaprio ({p['hop_count']} saltos)")
    else:
        print(f"  FALLO: {name} sigue sin camino a Leonardo DiCaprio.")

driver.close()
