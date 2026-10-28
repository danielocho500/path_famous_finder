"""Neo4j persistence for the manual editor. All writes use managed transactions."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from database.neo4j_service import driver


LABELS = {
    "people": "Person", "sources": "Source", "organizations": "Organization",
    "works": "Work", "events": "Event", "facts": "Fact",
}


class MissingEntity(Exception):
    pass


class Conflict(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def unpack(node):
    if node is None:
        return None
    raw = dict(node)
    data = json.loads(raw.get("data") or "{}")
    if not data and "real_name" in raw:  # Famous nodes awaiting migration.
        data = {"name": raw["real_name"], "image_url": raw.get("image_url")}
    return {
        **data, "id": raw.get("id"), "revision": raw.get("revision", 1),
        "created_at": raw.get("created_at"), "updated_at": raw.get("updated_at"),
        **({"status": raw["status"]} if "status" in raw else {}),
    }


def assert_exists(tx, collection, entity_id):
    label = LABELS[collection]
    if not tx.run(f"MATCH (n:{label} {{id:$id}}) RETURN n.id AS id", id=entity_id).single():
        raise MissingEntity(f"{collection}: {entity_id}")


def audit(tx, entity_id, collection, action, revision, before, after):
    tx.run(
        "CREATE (a:AuditEntry {id:$id, entity_id:$entity_id, collection:$collection, "
        "action:$action, revision:$revision, before:$before, after:$after, at:$at})",
        id=str(uuid4()), entity_id=entity_id, collection=collection, action=action,
        revision=revision, before=json.dumps(before, ensure_ascii=False) if before else None,
        after=json.dumps(after, ensure_ascii=False) if after else None, at=now(),
    )


def attach_fact(tx, fact):
    assert_exists(tx, "people", fact["subject_id"])
    assert_exists(tx, "sources", fact["source_id"])
    target = fact["object_collection"]
    assert_exists(tx, target, fact["object_id"])
    target_label = LABELS[target]
    tx.run(
        f"MATCH (f:Fact {{id:$fid}}), (p:Person {{id:$subject}}), "
        f"(o:{target_label} {{id:$object}}), (s:Source {{id:$source}}) "
        "MERGE (p)-[:SUBJECT_OF]->(f) "
        "MERGE (f)-[:OBJECT]->(o) MERGE (f)-[:SUPPORTED_BY]->(s)",
        fid=fact["id"], subject=fact["subject_id"], object=fact["object_id"],
        source=fact["source_id"],
    )


def detach_fact(tx, fact_id):
    tx.run(
        "MATCH (f:Fact {id:$id}) OPTIONAL MATCH (f)-[r]-() DELETE r",
        id=fact_id,
    )


def invalidate_dependents(tx, collection, entity_id):
    """Reopen verification when a source or context is corrected."""
    if collection == "sources":
        query = ("MATCH (f:Fact {status:'verified'})-[:SUPPORTED_BY]->"
                 "(s:Source {id:$id}) RETURN f")
    elif collection == "people":
        query = ("MATCH (f:Fact {status:'verified'}) WHERE f.subject_id=$id "
                 "OR f.object_id=$id RETURN f")
    else:
        query = "MATCH (f:Fact {status:'verified', object_id:$id}) RETURN f"
    affected = [unpack(row["f"]) for row in tx.run(query, id=entity_id)]
    for previous in affected:
        body = {key: value for key, value in previous.items()
                if key not in ("id", "revision", "created_at", "updated_at")}
        body["status"] = "draft"
        stamp = now()
        tx.run("MATCH (f:Fact {id:$id}) SET f.status='draft', f.revision=$revision, "
               "f.updated_at=$stamp, f.data=$data",
               id=previous["id"], revision=previous["revision"]+1, stamp=stamp,
               data=json.dumps(body, ensure_ascii=False))
        after = {**body, "id": previous["id"], "revision": previous["revision"]+1,
                 "created_at":previous["created_at"], "updated_at":stamp}
        audit(tx, previous["id"], "facts", "reopen_after_context_edit",
              after["revision"], previous, after)


class GraphRepository:
    def __init__(self, neo4j_driver=None):
        self.driver = neo4j_driver or driver

    def ensure_schema(self):
        with self.driver.session() as session:
            for label in (*LABELS.values(), "AuditEntry"):
                session.run(
                    f"CREATE CONSTRAINT {label.lower()}_id_unique IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.id IS UNIQUE"
                ).consume()
            session.run(
                "CREATE CONSTRAINT person_wikidata_unique IF NOT EXISTS "
                "FOR (n:Person) REQUIRE n.wikidata_id IS UNIQUE"
            ).consume()

    def list(self, collection, q=None, limit=100):
        label = LABELS[collection]
        limit = max(1, min(limit, 200))
        query = (
            f"MATCH (n:{label}) WHERE $q IS NULL OR "
            "toLower(coalesce(n.search_name,'')) CONTAINS toLower($q) "
            "OR toLower(coalesce(n.search_extra,'')) CONTAINS toLower($q) "
            "RETURN n ORDER BY n.updated_at DESC LIMIT $limit"
        )
        with self.driver.session() as session:
            return [unpack(row["n"]) for row in session.run(query, q=q or None, limit=limit)]

    def get(self, collection, entity_id):
        label = LABELS[collection]
        with self.driver.session() as session:
            record = session.run(
                f"MATCH (n:{label} {{id:$id}}) RETURN n", id=entity_id
            ).single()
            if not record:
                raise MissingEntity(f"{collection}: {entity_id}")
            return unpack(record["n"])

    def history(self, collection, entity_id):
        self.get(collection, entity_id)
        with self.driver.session() as session:
            rows = session.run(
                "MATCH (a:AuditEntry {collection:$collection, entity_id:$id}) "
                "RETURN a ORDER BY a.revision DESC LIMIT 100",
                collection=collection, id=entity_id,
            )
            return [{**dict(row["a"]),
                     "before": json.loads(row["a"].get("before")) if row["a"].get("before") else None,
                     "after": json.loads(row["a"].get("after")) if row["a"].get("after") else None}
                    for row in rows]

    def facts_for_source(self, source_id):
        self.get("sources", source_id)
        with self.driver.session() as session:
            rows = session.run(
                "MATCH (f:Fact)-[:SUPPORTED_BY]->(s:Source {id:$id}) "
                "RETURN f ORDER BY f.updated_at DESC LIMIT 200", id=source_id,
            )
            return [unpack(row["f"]) for row in rows]

    @staticmethod
    def _create(tx, collection, data):
        label = LABELS[collection]
        entity_id = str(uuid4())
        stamp = now()
        body = dict(data)
        body.pop("participants", None)
        search_name = body.get("name") or body.get("title") or ""
        search_extra = " ".join(body.get("aliases") or []) if collection == "people" else ""
        fields = {
            "id": entity_id, "data": json.dumps(body, ensure_ascii=False),
            "revision": 1, "created_at": stamp, "updated_at": stamp,
            "search_name": search_name, "search_extra": search_extra,
        }
        if collection == "people" and body.get("wikidata_id"):
            fields["wikidata_id"] = body["wikidata_id"]
        if collection == "facts":
            fields["status"] = body["status"]
            fields["type_id"] = body["type_id"]
            fields["subject_id"] = body["subject_id"]
            fields["object_id"] = body["object_id"]
        if body.get("location") and isinstance(body["location"], dict):
            loc = body["location"]
            if loc.get("name"): fields["location_name"] = loc["name"]
            if loc.get("lat") is not None: fields["latitude"] = loc["lat"]
            if loc.get("lng") is not None: fields["longitude"] = loc["lng"]
            if loc.get("city") is not None: fields["city"] = loc["city"]
            if loc.get("country") is not None: fields["country"] = loc["country"]
        tx.run(f"CREATE (n:{label}) SET n = $fields", fields=fields).consume()
        result = {**body, "id": entity_id, "revision": 1,
                  "created_at": stamp, "updated_at": stamp}
        if collection == "facts":
            attach_fact(tx, result)
        if collection == "events":
            assert_exists(tx, "sources", body["source_id"])
            tx.run(
                "MATCH (e:Event {id:$id}), (s:Source {id:$source}) "
                "MERGE (e)-[:SUPPORTED_BY]->(s)", id=entity_id, source=body["source_id"],
            )
        audit(tx, entity_id, collection, "create", 1, None, result)
        return result

    def create(self, collection, data):
        with self.driver.session() as session:
            return session.execute_write(self._create, collection, data)

    def create_event_with_facts(self, event_data, facts):
        def operation(tx):
            event = self._create(tx, "events", event_data)
            created = []
            for fact in facts:
                item = dict(fact)
                item["object_id"] = event["id"]
                created.append(self._create(tx, "facts", item))
            return {**event, "participants": created}
        with self.driver.session() as session:
            return session.execute_write(operation)

    def create_facts(self, facts):
        def operation(tx):
            return [self._create(tx, "facts", fact) for fact in facts]
        with self.driver.session() as session:
            return session.execute_write(operation)

    @staticmethod
    def _update(tx, collection, entity_id, revision, data, action):
        label = LABELS[collection]
        record = tx.run(
            f"MATCH (n:{label} {{id:$id}}) RETURN n", id=entity_id
        ).single()
        if not record:
            raise MissingEntity(f"{collection}: {entity_id}")
        previous = unpack(record["n"])
        if previous["revision"] != revision:
            raise Conflict("This record changed. Reload it before saving.")
        body = dict(data)
        body.pop("participants", None)
        stamp = now()
        fields = {
            "data": json.dumps(body, ensure_ascii=False),
            "revision": revision + 1, "updated_at": stamp,
            "search_name": body.get("name") or body.get("title") or "",
            "search_extra": " ".join(body.get("aliases") or []) if collection == "people" else "",
        }
        if collection == "people":
            fields["wikidata_id"] = body.get("wikidata_id")
        if collection == "facts":
            fields.update(status=body["status"], type_id=body["type_id"],
                          subject_id=body["subject_id"], object_id=body["object_id"])
            detach_fact(tx, entity_id)
        if body.get("location") and isinstance(body["location"], dict):
            loc = body["location"]
            if loc.get("name"): fields["location_name"] = loc["name"]
            if loc.get("lat") is not None: fields["latitude"] = loc["lat"]
            if loc.get("lng") is not None: fields["longitude"] = loc["lng"]
            if loc.get("city") is not None: fields["city"] = loc["city"]
            if loc.get("country") is not None: fields["country"] = loc["country"]
        if collection == "events":
            tx.run("MATCH (e:Event {id:$id})-[r:SUPPORTED_BY]->() DELETE r", id=entity_id)
        tx.run(f"MATCH (n:{label} {{id:$id}}) SET n += $fields", id=entity_id, fields=fields)
        result = {**body, "id": entity_id, "revision": revision + 1,
                  "created_at": previous["created_at"], "updated_at": stamp}
        if collection == "facts":
            attach_fact(tx, result)
        if collection == "events":
            assert_exists(tx, "sources", body["source_id"])
            tx.run("MATCH (e:Event {id:$id}), (s:Source {id:$source}) "
                   "MERGE (e)-[:SUPPORTED_BY]->(s)", id=entity_id, source=body["source_id"])
        if collection in ("people", "sources", "organizations", "works", "events"):
            old_body = {key: value for key, value in previous.items()
                        if key not in ("id", "revision", "created_at", "updated_at")}
            relevant_change = (old_body.get("birth") != body.get("birth") or
                               old_body.get("death") != body.get("death")) if collection == "people" else old_body != body
            if relevant_change:
                invalidate_dependents(tx, collection, entity_id)
        audit(tx, entity_id, collection, action, revision + 1, previous, result)
        return result

    def update(self, collection, entity_id, revision, data, action="update"):
        with self.driver.session() as session:
            return session.execute_write(self._update, collection, entity_id, revision, data, action)

    def facts_for_person(self, person_id):
        self.get("people", person_id)
        with self.driver.session() as session:
            rows = session.run(
                "MATCH (f:Fact {status:'verified'}) WHERE f.subject_id=$id "
                "OR (f.object_id=$id AND f.type_id IN "
                "['family.parent_of','family.sibling_of','family.spouse_of',"
                "'personal.met','professional.mentor_of']) "
                "RETURN f ORDER BY f.updated_at DESC LIMIT 500", id=person_id,
            )
            return [unpack(row["f"]) for row in rows]

    def facts_for_contexts(self, context_ids):
        if not context_ids:
            return []
        with self.driver.session() as session:
            rows = session.run(
                "MATCH (f:Fact {status:'verified'}) "
                "WHERE f.object_id IN $ids RETURN f LIMIT 2000", ids=context_ids,
            )
            return [unpack(row["f"]) for row in rows]

    def all_verified_facts(self):
        with self.driver.session() as session:
            rows = session.run(
                "MATCH (f:Fact {status:'verified'}) RETURN f LIMIT 5000"
            )
            return [unpack(row["f"]) for row in rows]

    def all_people_with_degree(self):
        with self.driver.session() as session:
            rows = session.run(
                "MATCH (p:Person) "
                "OPTIONAL MATCH (p)-[:SUBJECT_OF|OBJECT]-(f:Fact {status:'verified'}) "
                "RETURN p, count(f) AS degree"
            )
            results = []
            for row in rows:
                node = row["p"]
                raw = dict(node)
                item = unpack(node)
                if raw.get("principal_occupation") and not item.get("principal_occupation"):
                    item["principal_occupation"] = raw.get("principal_occupation")
                if raw.get("real_name") and not item.get("real_name"):
                    item["real_name"] = raw.get("real_name")
                if raw.get("best_known_for") and not item.get("best_known_for"):
                    item["best_known_for"] = raw.get("best_known_for")
                item["degree"] = row["degree"]
                results.append(item)
            return results

    def get_nodes_by_ids(self, ids):
        if not ids:
            return {}
        with self.driver.session() as session:
            rows = session.run(
                "MATCH (n) WHERE n.id IN $ids RETURN n", ids=list(set(ids))
            )
            return {row["n"]["id"]: unpack(row["n"]) for row in rows if row["n"].get("id")}



