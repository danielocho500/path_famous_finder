import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver

candidates = [
    ("La Parka (Jesús Huerta)", "Q6464293", "Jesús Alfonso Huerta Escoboza"),
    ("L.A. Park (Adolfo Tapia)", "Q6457187", "Adolfo Tapia"),
    ("El Hijo del Santo", "Q3050073", "Jorge Guzmán"),
    ("El Santo", "Q504786", "Rodolfo Guzmán Huerta"),
    ("Claudio Brook", "Q1095992", "Claudio Brook"),
    ("Silvia Pinal", "Q284355", "Silvia Pinal"),
    ("Luis Buñuel", "Q51545", "Luis Buñuel"),
    ("Pablo Picasso", "Q5593", "Pablo Picasso"),
    ("Max Aub", "Q705355", "Max Aub"),
    ("Diego Rivera", "Q326969", "Diego Rivera"),
    ("Frida Kahlo", "Q5588", "Frida Kahlo"),
]

with driver.session() as s:
    print("=== VERIFICANDO EXISTENCIA EN NEO4J ===")
    for label, qid, name in candidates:
        res = s.run("""
            MATCH (p:Person)
            WHERE p.wikidata_id = $qid
               OR toLower(coalesce(p.search_name, p.real_name, '')) CONTAINS toLower($name)
               OR toLower(coalesce(p.best_known_for, '')) CONTAINS toLower($name)
            RETURN p.id AS id, coalesce(p.search_name, p.real_name) AS name, p.wikidata_id AS qid
        """, qid=qid, name=name).data()
        if res:
            print(f"[YA EXISTE] {label}: {res}")
        else:
            print(f"[NO EXISTE] {label} (QID: {qid})")

    # Verificar organizaciones y obras
    print("\n--- Verificando organizaciones y obras ---")
    orgs = ["Lucha Libre AAA Worldwide", "AAA", "Asistencia Asesoría y Administración"]
    for o in orgs:
        res = s.run("MATCH (o:Organization) WHERE toLower(coalesce(o.search_name, '')) CONTAINS toLower($o) RETURN o.id AS id, o.search_name AS name", o=o).data()
        if res:
            print(f"[YA EXISTE ORG] {o}: {res}")

    works = ["Santo en el museo de cera", "Simón del desierto", "El ángel exterminador", "Guernica"]
    for w in works:
        res = s.run("MATCH (w:Work) WHERE toLower(coalesce(w.search_name, '')) CONTAINS toLower($w) RETURN w.id AS id, w.search_name AS name", w=w).data()
        if res:
            print(f"[YA EXISTE WORK] {w}: {res}")
