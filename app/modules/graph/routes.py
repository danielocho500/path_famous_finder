"""JSON endpoints for the private manual graph editor."""

from fastapi import APIRouter, Body, HTTPException, Query
from neo4j.exceptions import Neo4jError
from pydantic import ValidationError

from modules.graph.catalog import public_catalog
from modules.graph.models import (EventInput, FactBatchInput, FactInput, OrganizationInput,
                                  PersonInput, RevisionPatch, SourceInput, WorkInput)
from modules.graph.repository import Conflict, GraphRepository, MissingEntity
from modules.graph.service import (
    InvalidFact,
    connection_preview,
    search_people,
    shortest_path,
    validate_event,
    validate_fact,
)


router = APIRouter()
repo = GraphRepository()
MODELS = {
    "people": PersonInput, "sources": SourceInput, "organizations": OrganizationInput,
    "works": WorkInput, "events": EventInput, "facts": FactInput,
}


def collection_model(collection):
    if collection not in MODELS:
        raise HTTPException(404, "Unknown collection")
    return MODELS[collection]


def translate_error(error):
    if isinstance(error, MissingEntity):
        raise HTTPException(404, str(error)) from error
    if isinstance(error, Conflict):
        raise HTTPException(409, str(error)) from error
    if isinstance(error, (InvalidFact, ValidationError)):
        raise HTTPException(422, str(error)) from error
    if isinstance(error, Neo4jError) and "ConstraintValidationFailed" in (error.code or ""):
        raise HTTPException(409, "Unique identifier already exists") from error
    raise error


@router.get("/connection-types")
def connection_types():
    return public_catalog()


@router.get("/people/search")
def search_people_endpoint(q: str = None, limit: int = Query(10, ge=1, le=200)):
    try:
        return search_people(repo, q=q, limit=limit)
    except Exception as error:
        translate_error(error)


@router.get("/paths/shortest")
def shortest_path_endpoint(from_id: str = Query(..., min_length=1), to_id: str = Query(..., min_length=1)):
    try:
        return shortest_path(repo, from_id=from_id, to_id=to_id)
    except Exception as error:
        translate_error(error)


@router.get("/people/{person_id}/connections")
def person_connections(person_id: str):
    try:
        return connection_preview(repo, person_id)
    except Exception as error:
        translate_error(error)


@router.get("/sources/{source_id}/facts")
def source_facts(source_id: str):
    try:
        return repo.facts_for_source(source_id)
    except Exception as error:
        translate_error(error)


@router.post("/facts/batch", status_code=201)
def create_fact_batch(batch: FactBatchInput):
    try:
        if any(item.status != "draft" for item in batch.facts):
            raise InvalidFact("New facts start as drafts; use verify after review")
        facts = [validate_fact(repo, item) for item in batch.facts]
        return repo.create_facts(facts)
    except Exception as error:
        translate_error(error)


@router.post("/facts/{fact_id}/verify")
def verify_fact(fact_id: str, patch: RevisionPatch):
    try:
        current = repo.get("facts", fact_id)
        if current["revision"] != patch.revision:
            raise Conflict("This record changed. Reload it before saving.")
        if current["status"] == "archived":
            raise InvalidFact("Archived facts cannot be verified")
        if patch.changes:
            raise InvalidFact("Verification does not accept field changes")
        data = {key: value for key, value in current.items()
                if key not in ("id", "revision", "created_at", "updated_at")}
        data["status"] = "verified"
        return repo.update("facts", fact_id, patch.revision,
                           validate_fact(repo, data), "verify")
    except Exception as error:
        translate_error(error)


@router.post("/facts/{fact_id}/archive")
def archive_fact(fact_id: str, patch: RevisionPatch):
    try:
        current = repo.get("facts", fact_id)
        if current["revision"] != patch.revision:
            raise Conflict("This record changed. Reload it before saving.")
        if patch.changes:
            raise InvalidFact("Archive does not accept field changes")
        data = {key: value for key, value in current.items()
                if key not in ("id", "revision", "created_at", "updated_at")}
        if data["status"] == "archived":
            raise InvalidFact("Fact is already archived")
        data["status"] = "archived"
        return repo.update("facts", fact_id, patch.revision, data, "archive")
    except Exception as error:
        translate_error(error)


@router.get("/{collection}")
def list_entities(collection: str, q: str = None, limit: int = Query(100, ge=1, le=200)):
    collection_model(collection)
    try:
        return repo.list(collection, q, limit)
    except Exception as error:
        translate_error(error)


@router.post("/{collection}", status_code=201)
def create_entity(collection: str, body: dict = Body(...)):
    model = collection_model(collection)
    try:
        parsed = model.model_validate(body)
        if collection == "facts":
            if parsed.status != "draft":
                raise InvalidFact("New facts start as drafts; use verify after review")
            return repo.create("facts", validate_fact(repo, parsed))
        if collection == "events":
            event = validate_event(repo, parsed)
            if parsed.participants:
                if any(item.status != "draft" for item in parsed.participants):
                    raise InvalidFact("New facts start as drafts; use verify after review")
                facts = [validate_fact(repo, item, pending_context=event)
                         for item in parsed.participants]
                if any(item["object_collection"] != "events" for item in facts):
                    raise InvalidFact("Participants must refer to this event")
                return repo.create_event_with_facts(event, facts)
            return repo.create("events", event)
        return repo.create(collection, parsed.model_dump(mode="json"))
    except Exception as error:
        translate_error(error)


@router.get("/{collection}/{entity_id}")
def get_entity(collection: str, entity_id: str):
    collection_model(collection)
    try:
        return repo.get(collection, entity_id)
    except Exception as error:
        translate_error(error)


@router.get("/{collection}/{entity_id}/history")
def entity_history(collection: str, entity_id: str):
    collection_model(collection)
    try:
        return repo.history(collection, entity_id)
    except Exception as error:
        translate_error(error)


@router.patch("/{collection}/{entity_id}")
def update_entity(collection: str, entity_id: str, patch: RevisionPatch):
    model = collection_model(collection)
    try:
        current = repo.get(collection, entity_id)
        if current["revision"] != patch.revision:
            raise Conflict("This record changed. Reload it before saving.")
        if collection == "facts" and current["status"] == "archived":
            raise InvalidFact("Archived facts cannot be edited")
        allowed = set(model.model_fields) - ({"participants"} if collection == "events" else set())
        unknown = set(patch.changes) - allowed
        if unknown:
            raise InvalidFact(f"Unknown fields: {', '.join(sorted(unknown))}")
        merged = {key: current.get(key) for key in allowed}
        merged.update(patch.changes)
        if collection == "facts" and patch.changes:
            if "status" in patch.changes:
                raise InvalidFact("Use verify or archive action to change fact status")
            merged["status"] = "draft"
        parsed = model.model_validate(merged)
        if collection == "facts":
            data = validate_fact(repo, parsed)
        elif collection == "events":
            data = validate_event(repo, parsed)
        else:
            data = parsed.model_dump(mode="json")
        return repo.update(collection, entity_id, patch.revision, data)
    except Exception as error:
        translate_error(error)
