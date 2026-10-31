"""Connection types shown in the editor and enforced by the API."""

TYPES = {
    "sports.same_team": {
        "supertype": "Deportivo", "label": "Estuvieron en el mismo equipo",
        "shape": "membership", "predicate": "MEMBER_OF", "context_kind": "organization",
        "context_type": "team", "requires_period": True,
    },
    "sports.faced_in_match": {
        "supertype": "Deportivo", "label": "Se enfrentaron en un partido",
        "shape": "event", "predicate": "PARTICIPATED_IN", "context_kind": "event",
        "context_type": "sports.match", "roles": ["player"], "pair_rule": "opposite_side",
    },
    "sports.same_side_match": {
        "supertype": "Deportivo", "label": "Jugaron en el mismo bando",
        "shape": "event", "predicate": "PARTICIPATED_IN", "context_kind": "event",
        "context_type": "sports.match", "roles": ["player"], "pair_rule": "same_side",
    },
    "arts.collaborated_on_work": {
        "supertype": "Artístico", "label": "Colaboraron en una obra",
        "shape": "work", "predicate": "CONTRIBUTED_TO", "context_kind": "work",
        "requires_period": True,
        "roles": ["creator", "performer", "director", "writer", "composer"],
    },
    "arts.co_starred": {
        "supertype": "Artístico", "label": "Actuaron en la misma producción",
        "shape": "work", "predicate": "CONTRIBUTED_TO", "context_kind": "work",
        "context_type": "film", "roles": ["actor"],
        "requires_period": True,
    },
    "arts.performed_together": {
        "supertype": "Artístico", "label": "Se presentaron juntos",
        "shape": "event", "predicate": "PARTICIPATED_IN", "context_kind": "event",
        "context_type": "arts.performance", "roles": ["performer"],
    },
    "politics.co_signed_treaty": {
        "supertype": "Político", "label": "Firmaron el mismo tratado",
        "shape": "event", "predicate": "PARTICIPATED_IN", "context_kind": "event",
        "context_type": "politics.treaty_signing", "roles": ["signatory"],
    },
    "politics.same_meeting": {
        "supertype": "Político", "label": "Asistieron a la misma reunión",
        "shape": "event", "predicate": "PARTICIPATED_IN", "context_kind": "event",
        "context_type": "politics.meeting", "roles": ["attendee", "speaker", "organizer"],
    },
    "politics.same_government": {
        "supertype": "Político", "label": "Integraron el mismo gobierno",
        "shape": "membership", "predicate": "MEMBER_OF", "context_kind": "organization",
        "context_type": "government", "requires_period": True,
    },
    "family.parent_of": {
        "supertype": "Familiar", "label": "Es padre o madre de",
        "shape": "direct", "predicate": "PARENT_OF", "context_kind": "person",
    },
    "family.sibling_of": {
        "supertype": "Familiar", "label": "Son hermanos",
        "shape": "direct", "predicate": "SIBLING_OF", "context_kind": "person",
    },
    "family.spouse_of": {
        "supertype": "Familiar", "label": "Fueron cónyuges",
        "shape": "direct", "predicate": "SPOUSE_OF", "context_kind": "person",
    },
    "personal.met": {
        "supertype": "Personal y profesional", "label": "Se reunieron",
        "shape": "direct", "predicate": "MET", "context_kind": "person",
    },
    "professional.mentor_of": {
        "supertype": "Personal y profesional", "label": "Fue mentor de",
        "shape": "direct", "predicate": "MENTOR_OF", "context_kind": "person",
    },
    "professional.same_project": {
        "supertype": "Personal y profesional", "label": "Colaboraron en un proyecto",
        "shape": "work", "predicate": "CONTRIBUTED_TO", "context_kind": "work",
        "context_type": "project", "roles": ["collaborator", "researcher"],
        "requires_period": True,
    },
}


def get_type(type_id):
    return TYPES.get(type_id)


def public_catalog():
    return [{"id": key, **value} for key, value in TYPES.items()]
