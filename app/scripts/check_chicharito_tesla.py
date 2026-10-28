import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver

people_to_check = [
    ("Javier Hernández", "Q186438"),
    ("Chicharito", "Q186438"),
    ("Alex Ferguson", "Q44980"),
    ("Wayne Rooney", "Q26659"),
    ("Isabel II del Reino Unido", "Q9682"),
    ("Jorge VI del Reino Unido", "Q280856"),
    ("Pedro II de Yugoslavia", "Q212450"),
    ("Alejandra de Grecia y Dinamarca", "Q157147"),
    ("Sava Kosanović", "Q12758467"),
    ("Nikola Tesla", "Q9036"),
    ("Hermann von Helmholtz", "Q60024"),
]

with driver.session() as s:
    print("=== VERIFICANDO EXISTENCIA DE PERSONAS EN NEO4J ===")
    for name, qid in people_to_check:
        res = s.run("""
            MATCH (p:Person)
            WHERE p.wikidata_id = $qid
               OR toLower(coalesce(p.search_name, p.real_name, '')) CONTAINS toLower($name)
            RETURN p.id AS id, coalesce(p.search_name, p.real_name) AS name, p.wikidata_id AS qid
        """, name=name, qid=qid).data()
        print(f"Check {name} ({qid}): {res}")

    print("\n=== VERIFICANDO ORGANIZACIONES EN NEO4J ===")
    for org in ["Manchester United", "Manchester United F.C."]:
        res = s.run("""
            MATCH (o:Organization)
            WHERE toLower(coalesce(o.search_name, '')) CONTAINS toLower($org)
            RETURN o.id AS id, o.search_name AS name, o.kind AS kind
        """, org=org).data()
        print(f"Org {org}: {res}")
