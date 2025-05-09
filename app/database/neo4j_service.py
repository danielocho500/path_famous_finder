import os
from neo4j import GraphDatabase

URI = os.getenv("NEO4J_URI")
AUTH = os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASS")

with GraphDatabase.driver(URI, auth=AUTH) as driver:
    driver.verify_connectivity()
