import json
from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver

with driver.session() as s:
    people = s.run("MATCH (p:Person) RETURN p.id AS id, coalesce(p.search_name, p.real_name) AS name, p.wikidata_id AS qid ORDER BY name").data()
    print(f"Total people in DB: {len(people)}")
    for row in people:
        print(f" - {row['name']} ({row['qid']}) [ID: {row['id']}]")
