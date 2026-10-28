"""Conservatively add Person representation to legacy Famous nodes.

Usage: PYTHONPATH=app python app/scripts/migrate_famous.py [--apply]
Without --apply, only prints a report. Existing properties and Famous labels stay.
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
from neo4j.exceptions import AuthError, ServiceUnavailable

load_dotenv()

from database.neo4j_service import driver
from modules.graph.models import PersonInput
from modules.graph.repository import GraphRepository


def historical_date(value):
    if value is None:
        return None
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return {"year": value.year, "month": value.month, "day": value.day,
                "precision": "day", "approximate": False}
    return None


def person_data(raw):
    return PersonInput(
        name=raw.get("real_name") or raw.get("best_known_for") or "Sin nombre",
        aliases=raw.get("nicknames") or [],
        description=raw.get("profile_sumary_description"),
        country=raw.get("country") or raw.get("country_code"),
        city_born=raw.get("city_born"),
        image_url=raw.get("image_url"),
        birth=historical_date(raw.get("date_born")),
        death=historical_date(raw.get("date_died")),
    ).model_dump(mode="json")


def migrate_one(tx, element_id, raw):
    item_id=raw.get("id") or str(uuid4())
    stamp=datetime.now(timezone.utc).isoformat()
    data=person_data(raw)
    fields={
        "id":item_id, "data":json.dumps(data,ensure_ascii=False),
        "search_name":data["name"], "search_extra":" ".join(data["aliases"]),
        "revision":raw.get("revision") or 1,
        "created_at":raw.get("created_at") or stamp,
        "updated_at":raw.get("updated_at") or stamp,
    }
    tx.run("MATCH (f:Famous) WHERE elementId(f)=$element_id "
           "SET f:Person SET f += $fields",element_id=element_id,fields=fields).consume()
    return item_id


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply",action="store_true",help="Apply the migration")
    args=parser.parse_args()
    try:
        driver.verify_connectivity()
        with driver.session() as session:
            rows=[{"element_id":row["element_id"],"raw":dict(row["f"]),
                   "labels":set(row["labels"])} for row in session.run(
                "MATCH (f:Famous) RETURN elementId(f) AS element_id, f, labels(f) AS labels")]
            pending=[r for r in rows if "Person" not in r["labels"] or not r["raw"].get("data")]
            counts=Counter((r["raw"].get("real_name") or "").strip().casefold() for r in rows)
            duplicates={name:count for name,count in counts.items() if name and count>1}
            print(json.dumps({"famous_total":len(rows),"pending":len(pending),
                              "duplicate_names":duplicates,"mode":"apply" if args.apply else "dry-run"},
                             ensure_ascii=False,indent=2))
            if args.apply:
                GraphRepository(driver).ensure_schema()
                for row in pending:
                    session.execute_write(migrate_one,row["element_id"],row["raw"])
                print(f"Migrated {len(pending)} node(s); no Famous nodes or properties removed.")
    except (ValueError, ServiceUnavailable, AuthError) as error:
        print(f"Neo4j unavailable: {error}", file=sys.stderr)
        return 2
    finally:
        driver.close()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
