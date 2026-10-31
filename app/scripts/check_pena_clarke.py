import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver

people_to_check = [
    ("Enrique Peña Nieto", "Q296741"),
    ("Emilia Clarke", "Q235196"),
    ("Leonardo DiCaprio", "Q38111"),
    ("Samuel L. Jackson", "Q172678"),
    ("Carlos Slim", "Q170419"),
    ("Quentin Tarantino", "Q3772"),
    ("Olivia Colman", "Q7088045"),
    ("Isabel II del Reino Unido", "Q9682"),
]

with driver.session() as s:
    print("=== VERIFICANDO EXISTENCIA EN NEO4J ===")
    for name, qid in people_to_check:
        res = s.run("""
            MATCH (p:Person)
            WHERE p.wikidata_id = $qid
               OR toLower(coalesce(p.search_name, p.real_name, '')) CONTAINS toLower($name)
            RETURN p.id AS id, coalesce(p.search_name, p.real_name) AS name, p.wikidata_id AS qid
        """, name=name, qid=qid).data()
        print(f"Check {name} ({qid}): {res}")

    print("\n--- Verificando Obras ---")
    for w in ["Django Unchained", "Secret Invasion"]:
        res = s.run("MATCH (w:Work) WHERE toLower(coalesce(w.search_name, '')) CONTAINS toLower($w) RETURN w.id AS id, w.search_name AS name", w=w).data()
        print(f"Work {w}: {res}")
