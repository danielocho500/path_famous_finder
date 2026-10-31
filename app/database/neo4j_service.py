import os
from neo4j import GraphDatabase

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME")
PASS = os.getenv("NEO4J_PASS") or os.getenv("NEO4J_PASSWORD")
AUTH = (USER, PASS) if (USER and PASS) else None

driver = GraphDatabase.driver(URI, auth=AUTH)
