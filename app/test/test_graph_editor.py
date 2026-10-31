import os
import json
import unittest
from datetime import date
from unittest.mock import Mock, patch

os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "test")
os.environ.setdefault("NEO4J_PASS", "test")

from fastapi import HTTPException

from modules.graph.models import HistoricalDate, LocationInput, Period, PersonInput, FactInput, definitely_overlap
from modules.graph.routes import create_entity, update_entity
from modules.graph.models import RevisionPatch
from modules.graph.repository import Conflict, MissingEntity, invalidate_dependents
from modules.graph.service import InvalidFact, connection_preview, search_people, shortest_path, validate_fact
from scripts.migrate_famous import migrate_one, person_data


class FakeRepo:
    def __init__(self, entities=None, own=None, peers=None):
        self.entities=entities or {}
        self.own=own or []
        self.peers=peers or []

    def get(self, collection, entity_id):
        try:
            return self.entities[(collection,entity_id)]
        except KeyError:
            raise MissingEntity(f"{collection}: {entity_id}")

    def facts_for_person(self, person_id):
        self.get("people", person_id)
        return self.own

    def facts_for_contexts(self, ids):
        return [f for f in self.peers if f["object_id"] in ids]

    def all_people_with_degree(self):
        return [entity for (coll, _), entity in self.entities.items() if coll == "people"]

    def all_verified_facts(self):
        return [f for f in (self.own + self.peers) if f.get("status", "verified") == "verified"]

    def get_nodes_by_ids(self, ids):
        out = {}
        for (_, eid), entity in self.entities.items():
            if eid in ids:
                out[eid] = entity
        return out

    def create(self, collection, data):
        return data

    def create_event_with_facts(self, event, facts):
        return {"event":event,"facts":facts}


def membership(fid, subject, start, end, source):
    return {"id":fid,"type_id":"sports.same_team","subject_id":subject,
            "object_id":"team","source_id":source,
            "period":{"start":{"year":start},"end":{"year":end}},
            "status":"verified"}


class GraphEditorTests(unittest.TestCase):
    def setUp(self):
        self.repo=FakeRepo({("people","a"):{"id":"a","name":"Ada Lovelace","degree":3},
                            ("people","b"):{"id":"b","name":"Benito Juárez","degree":5},
                            ("people","c"):{"id":"c","name":"Nelson Kanzela","aliases":["El Rey del Baile"],"degree":2},
                            ("sources","s1"):{"id":"s1","title":"Archivo General","url":"https://example.org/doc"},
                            ("organizations","team"):{"id":"team","kind":"team"},
                            ("works","book"):{"id":"book","kind":"book"},
                            ("events","match"):{"id":"match","kind":"sports.match",
                                                "period":{"start":{"year":2022}}}})

    def test_same_team_needs_documented_overlapping_memberships(self):
        first=membership("f1","a",2019,2022,"s1")
        second=membership("f2","b",2020,2023,"s2")
        self.repo.own=[first];self.repo.peers=[first,second]
        result=connection_preview(self.repo,"a")
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["source_ids"],["s1","s2"])
        self.assertEqual(result[0]["fact_ids"],["f1","f2"])
        second["period"]={"start":{"year":2024},"end":{"year":2025}}
        self.assertEqual(connection_preview(self.repo,"a"),[])

    def test_opposite_sides_are_required_for_a_match(self):
        first={"id":"f1","type_id":"sports.faced_in_match","subject_id":"a",
               "object_id":"match","source_id":"s1","role":"player","side":"home"}
        second={**first,"id":"f2","subject_id":"b","side":"away","source_id":"s2"}
        self.repo.own=[first];self.repo.peers=[first,second]
        self.assertEqual(connection_preview(self.repo,"a")[0]["type_id"],"sports.faced_in_match")
        second["side"]="home"
        second["type_id"]="sports.same_side_match"
        self.assertEqual(connection_preview(self.repo,"a")[0]["type_id"],"sports.same_side_match")

    def test_work_contributors_from_different_eras_do_not_connect(self):
        first={"id":"f1","type_id":"arts.collaborated_on_work","subject_id":"a",
               "object_id":"book","source_id":"s1","role":"writer",
               "period":{"start":{"year":1800},"end":{"year":1800}}}
        second={**first,"id":"f2","subject_id":"b","source_id":"s2",
                "period":{"start":{"year":2000},"end":{"year":2000}}}
        self.repo.own=[first];self.repo.peers=[first,second]
        self.assertEqual(connection_preview(self.repo,"a"),[])
        second["period"]={"start":{"year":1800},"end":{"year":1800}}
        self.assertEqual(len(connection_preview(self.repo,"a")),1)

    def test_direct_tie_cannot_be_verified_across_known_lifetimes(self):
        self.repo.entities[("people","a")]["death"]={"year":-30}
        self.repo.entities[("people","b")]["birth"]={"year":2000}
        fact={"type_id":"personal.met","subject_id":"a","object_id":"b",
              "source_id":"s1","source_locator":"p. 3","status":"verified"}
        with self.assertRaises(InvalidFact):
            validate_fact(self.repo,fact)

    def test_source_context_and_role_are_checked(self):
        body={"type_id":"sports.faced_in_match","subject_id":"a","object_id":"match",
              "source_id":"s1","source_locator":"p. 4","role":"player","side":"home"}
        self.assertEqual(validate_fact(self.repo,body)["object_collection"],"events")
        with self.assertRaises(MissingEntity):
            validate_fact(self.repo,{**body,"source_id":"missing"})
        with self.assertRaises(InvalidFact):
            validate_fact(self.repo,{**body,"role":"spectator"})
        with self.assertRaises(InvalidFact):
            validate_fact(self.repo,{**body,"source_locator":" "})

    def test_verified_membership_requires_interval(self):
        body={"type_id":"sports.same_team","subject_id":"a","object_id":"team",
              "source_id":"s1","source_locator":"p. 5","status":"verified"}
        with self.assertRaises(InvalidFact):
            validate_fact(self.repo,body)
        work={"type_id":"arts.collaborated_on_work","subject_id":"a","object_id":"book",
              "source_id":"s1","source_locator":"credits","role":"writer","status":"verified"}
        with self.assertRaises(InvalidFact):
            validate_fact(self.repo,work)

    def test_event_participant_does_not_need_event_id_before_creation(self):
        body={"name":"Final","kind":"sports.match","period":{"start":{"year":2022}},
              "source_id":"s1","source_locator":"match record",
              "participants":[{"type_id":"sports.faced_in_match","subject_id":"a",
                               "source_id":"s1","source_locator":"lineup","role":"player",
                               "side":"home"}]}
        with patch("modules.graph.routes.repo",self.repo):
            with patch.object(self.repo,"create_event_with_facts",return_value={"id":"created"}) as save:
                result=create_entity("events",body)
        self.assertEqual(result["id"],"created")
        self.assertEqual(save.call_args.args[1][0]["object_id"],"_pending_")

    def test_historical_years_and_uncertain_periods(self):
        self.assertEqual(HistoricalDate(year=-30).year,-30)
        with self.assertRaises(ValueError): HistoricalDate(year=0)
        first=Period(start=HistoricalDate(year=-31),end=HistoricalDate(year=-29))
        second=Period(start=HistoricalDate(year=-30),end=HistoricalDate(year=-28))
        self.assertTrue(definitely_overlap(first,second))
        second.start.approximate=True
        self.assertFalse(definitely_overlap(first,second))

    def test_api_maps_missing_reference_and_revision_conflict(self):
        with patch("modules.graph.routes.repo", self.repo):
            with self.assertRaises(HTTPException) as caught:
                create_entity("facts",{"type_id":"family.parent_of","subject_id":"a",
                                       "object_id":"b","source_id":"missing",
                                       "source_locator":"p. 3"})
            self.assertEqual(caught.exception.status_code,404)
            with self.assertRaises(HTTPException) as caught:
                create_entity("facts",{"type_id":"family.parent_of","subject_id":"a",
                                       "object_id":"b","source_id":"s1",
                                       "source_locator":"p. 3","status":"verified"})
            self.assertEqual(caught.exception.status_code,422)
        current={**PersonInput(name="Ada").model_dump(mode="json"),"id":"a","revision":2,
                 "created_at":"t","updated_at":"t"}
        with patch("modules.graph.routes.repo") as mocked:
            mocked.get.return_value=current
            mocked.update.side_effect=Conflict("changed")
            with self.assertRaises(HTTPException) as caught:
                update_entity("people","a",RevisionPatch(revision=1,changes={"name":"Ada L."}))
            self.assertEqual(caught.exception.status_code,409)

    def test_source_correction_reopens_dependent_verified_fact(self):
        body={"type_id":"family.parent_of","subject_id":"a","object_id":"b",
              "source_id":"s1","source_locator":"p. 3","status":"verified"}
        raw={"id":"f1","revision":2,"created_at":"old","updated_at":"old",
             "status":"verified","data":json.dumps(body)}
        tx=Mock();tx.run.side_effect=[[{"f":raw}],Mock()]
        with patch("modules.graph.repository.audit") as audit:
            invalidate_dependents(tx,"sources","s1")
        self.assertEqual(tx.run.call_count,2)
        self.assertEqual(json.loads(tx.run.call_args.kwargs["data"])["status"],"draft")
        self.assertEqual(tx.run.call_args.kwargs["revision"],3)
        self.assertEqual(audit.call_args.args[3],"reopen_after_context_edit")
        tx=Mock();tx.run.return_value=[]
        invalidate_dependents(tx,"people","a")
        self.assertIn("f.subject_id=$id",tx.run.call_args.args[0])
        self.assertIn("f.object_id=$id",tx.run.call_args.args[0])

    def test_legacy_famous_migration_keeps_original_node(self):
        legacy={"real_name":"Ada Lovelace","nicknames":["Ada"],
                "date_born":date(1815,12,10),"image_url":"https://example.com/ada.jpg"}
        converted=person_data(legacy)
        self.assertEqual(converted["birth"]["precision"],"day")
        self.assertEqual(converted["aliases"],["Ada"])
        tx=Mock();migrate_one(tx,"legacy-element",legacy)
        query=tx.run.call_args.args[0]
        self.assertIn("SET f:Person",query)
        self.assertNotIn("DELETE",query)
        self.assertEqual(tx.run.call_args.kwargs["fields"]["search_name"],"Ada Lovelace")

    def test_location_validation_and_preview(self):
        loc = LocationInput(name="Palacio de Versalles", city="Versalles", country="FR", lat=48.8049, lng=2.1204)
        self.assertEqual(loc.lat, 48.8049)
        with self.assertRaises(ValueError):
            LocationInput(name="Invalid", lat=95.0)
        with self.assertRaises(ValueError):
            LocationInput(name="Invalid", lng=-200.0)

        fact = {"id": "f_loc", "type_id": "personal.met", "subject_id": "a", "object_id": "b",
                "source_id": "s1", "source_locator": "p. 1", "status": "verified",
                "location": loc.model_dump(mode="json")}
        self.repo.own = [fact]
        preview = connection_preview(self.repo, "a")
        self.assertEqual(len(preview), 1)
        self.assertIsNotNone(preview[0].get("location"))
        self.assertEqual(preview[0]["location"]["name"], "Palacio de Versalles")
        self.assertEqual(preview[0]["location"]["country"], "FR")

    def test_search_people_case_and_accent_insensitive_top_10(self):
        for i in range(12):
            pid = f"p_{i}"
            self.repo.entities[("people", pid)] = {
                "id": pid,
                "name": f"Personaje Histórico {i}",
                "degree": i,
            }
        top10 = search_people(self.repo, "", limit=10)
        self.assertEqual(len(top10), 10)
        juarez = search_people(self.repo, "bEnItO jUaReZ", limit=10)
        self.assertTrue(len(juarez) >= 1)
        self.assertEqual(juarez[0]["id"], "b")
        kanzela = search_people(self.repo, "nelson kansela", limit=10)
        self.assertTrue(len(kanzela) >= 1)
        self.assertEqual(kanzela[0]["id"], "c")

    def test_shortest_path_sequence_and_coordinates(self):
        self.repo.own = [
            {
                "id": "f_ab",
                "type_id": "personal.met",
                "subject_id": "a",
                "object_id": "b",
                "source_id": "s1",
                "source_locator": "acta 1",
                "status": "verified",
                "period": {"start": {"year": 1850, "month": 5, "day": 10}},
                "location": {
                    "name": "Palacio Nacional",
                    "city": "Ciudad de México",
                    "country": "México",
                    "lat": 19.4326,
                    "lng": -99.1332,
                },
                "note": "Encuentro en Palacio Nacional.",
            },
            {
                "id": "f_bc",
                "type_id": "personal.met",
                "subject_id": "b",
                "object_id": "c",
                "source_id": "s1",
                "source_locator": "acta 2",
                "status": "verified",
                "period": {"start": {"year": 2020, "month": 1, "day": 15}},
                "location": {
                    "name": "Auditorio",
                    "city": "Veracruz",
                    "country": "México",
                    "lat": 19.1738,
                    "lng": -96.1342,
                },
                "note": "Encuentro en Veracruz.",
            },
        ]
        res = shortest_path(self.repo, "a", "c")
        self.assertTrue(res["found"])
        self.assertEqual(res["hop_count"], 2)
        self.assertEqual(len(res["steps"]), 2)
        self.assertEqual(res["steps"][0]["from_person"]["id"], "a")
        self.assertEqual(res["steps"][0]["to_person"]["id"], "b")
        self.assertAlmostEqual(res["steps"][0]["location"]["lat"], 19.4326)
        self.assertEqual(res["steps"][1]["from_person"]["id"], "b")
        self.assertEqual(res["steps"][1]["to_person"]["id"], "c")
        self.assertEqual(res["steps"][1]["location"]["city"], "Veracruz")


if __name__=="__main__": unittest.main()
