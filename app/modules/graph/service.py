"""Catalogue rules and evidence-backed direct connection previews."""

from modules.graph.catalog import get_type
from modules.graph.models import FactInput, Period, definitely_overlap, possibly_overlap


class InvalidFact(ValueError):
    pass


def separated_lifetimes(first, second):
    """Reject direct personal ties when known lifetimes are far apart."""
    for earlier, later in ((first, second), (second, first)):
        death = earlier.get("death")
        birth = later.get("birth")
        if (death and birth and not death.get("approximate") and
                not birth.get("approximate") and death["year"] < birth["year"] - 1):
            return True
    return False


def validate_fact(repo, value, pending_context=None):
    """Return a persisted fact body after checking subtype and referenced context."""
    fact = value if isinstance(value, FactInput) else FactInput.model_validate(value)
    kind = get_type(fact.type_id)
    if not kind:
        raise InvalidFact("Unknown connection subtype")
    if not fact.source_locator.strip():
        raise InvalidFact("Source locator is required")
    if fact.role and kind.get("roles") and fact.role not in kind["roles"]:
        raise InvalidFact("Role is not allowed for this subtype")
    if kind.get("roles") and not fact.role:
        raise InvalidFact("Role is required for this subtype")
    if kind.get("pair_rule") and not (fact.side and fact.side.strip()):
        raise InvalidFact("A side is required for this subtype")
    if kind["shape"] == "direct" and fact.subject_id == fact.object_id:
        raise InvalidFact("A person cannot be related to themselves")
    if fact.side and not kind.get("pair_rule"):
        raise InvalidFact("Side is only used for matches")
    if kind["shape"] == "direct" and fact.role:
        raise InvalidFact("Direct relationships do not use a role")
    if kind.get("requires_period") and fact.status == "verified":
        if not fact.period.start or not fact.period.end:
            raise InvalidFact("Verified memberships and contributions need start and end dates")
    subject = repo.get("people", fact.subject_id)
    repo.get("sources", fact.source_id)
    collection = {"person": "people", "event": "events", "organization": "organizations",
                  "work": "works"}[kind["context_kind"]]
    context = pending_context if pending_context is not None else repo.get(collection, fact.object_id)
    if kind["shape"] == "direct" and fact.status == "verified":
        if separated_lifetimes(subject, context):
            raise InvalidFact("Known lifetimes do not permit this direct relationship")
    if pending_context is not None and collection != "events":
        raise InvalidFact("Pending context must be an event")
    if kind.get("context_type") and context.get("kind") != kind["context_type"]:
        raise InvalidFact("Context kind does not match the selected subtype")
    if kind["shape"] == "event" and fact.status == "verified":
        period = context.get("period") or {}
        if not period.get("start"):
            raise InvalidFact("Verified event participation needs a dated event")
    return {**fact.model_dump(mode="json"), "object_collection": collection,
            "predicate": kind["predicate"]}


def validate_event(repo, value):
    data = value.model_dump(mode="json", exclude={"participants"})
    if not data["source_locator"].strip():
        raise InvalidFact("Event source locator is required")
    repo.get("sources", data["source_id"])
    return data


def connection_preview(repo, person_id):
    """Derive only direct links supported by verified facts and compatible roles."""
    own = repo.facts_for_person(person_id)
    contexts = {f["object_id"] for f in own
                if get_type(f["type_id"])["shape"] != "direct"}
    peers = repo.facts_for_contexts(list(contexts))
    results = []
    seen = set()
    match_types = {"sports.faced_in_match", "sports.same_side_match"}
    for fact in own:
        spec = get_type(fact["type_id"])
        if spec["shape"] == "direct":
            other = fact["object_id"] if fact["subject_id"] == person_id else fact["subject_id"]
            key = (fact["id"],)
            if key not in seen:
                seen.add(key)
                results.append({"person_id": other, "type_id": fact["type_id"],
                                "direction": "outgoing" if fact["subject_id"] == person_id else "incoming",
                                "context_id": None, "fact_ids": [fact["id"]],
                                "source_ids": [fact["source_id"]],
                                "location": fact.get("location")})
            continue
        if fact["subject_id"] != person_id:
            continue
        for peer in peers:
            if peer["id"] == fact["id"] or peer["subject_id"] == person_id:
                continue
            if peer["object_id"] != fact["object_id"]:
                continue
            is_match = fact["type_id"] in match_types and peer["type_id"] in match_types
            if not is_match and peer["type_id"] != fact["type_id"]:
                continue
            if spec.get("roles") and (fact.get("role") not in spec["roles"] or
                                      peer.get("role") not in spec["roles"]):
                continue
            if is_match:
                if not fact.get("side") or not peer.get("side"):
                    continue
                result_type = ("sports.same_side_match" if fact["side"] == peer["side"]
                               else "sports.faced_in_match")
            else:
                result_type = fact["type_id"]
                rule = spec.get("pair_rule")
                if rule == "opposite_side" and (not fact.get("side") or not peer.get("side") or
                                                fact["side"] == peer["side"]):
                    continue
                if rule == "same_side" and (not fact.get("side") or fact["side"] != peer.get("side")):
                    continue
            if spec["shape"] == "membership":
                first = Period.model_validate(fact.get("period") or {})
                second = Period.model_validate(peer.get("period") or {})
                if not definitely_overlap(first, second):
                    continue
            if spec["shape"] == "work":
                first = Period.model_validate(fact.get("period") or {})
                second = Period.model_validate(peer.get("period") or {})
                if not possibly_overlap(first, second):
                    continue
            ids = tuple(sorted((fact["id"], peer["id"])))
            if ids in seen:
                continue
            seen.add(ids)
            loc = fact.get("location") or peer.get("location")
            if not loc and spec["shape"] == "event":
                try:
                    ev = repo.get("events", fact["object_id"])
                    loc = ev.get("location") or ({"name": ev["place"]} if ev.get("place") else None)
                except Exception:
                    pass
            results.append({"person_id": peer["subject_id"], "type_id": result_type,
                            "direction": "shared",
                            "context_id": fact["object_id"], "fact_ids": list(ids),
                            "source_ids": sorted({fact["source_id"], peer["source_id"]}),
                            "location": loc})
    return results


import unicodedata
from collections import defaultdict, deque
from difflib import SequenceMatcher


def _norm(text: str) -> str:
    if not text:
        return ""
    return (
        unicodedata.normalize("NFKD", str(text))
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
        .strip()
    )


def search_people(repo, q: str = None, limit: int = 10):
    """Return top `limit` people matching `q` case-insensitively and accent-insensitively."""
    limit = max(1, min(limit, 50))
    people = repo.all_people_with_degree() if hasattr(repo, "all_people_with_degree") else repo.list("people", q, limit)
    qn = _norm(q)
    if not qn:
        ranked = sorted(
            people,
            key=lambda p: (-int(p.get("degree") or 0), _norm(p.get("name") or "")),
        )
        return ranked[:limit]

    q_tokens = [t for t in qn.split() if t]
    scored = []
    for person in people:
        name_n = _norm(person.get("name") or "")
        real_n = _norm(person.get("real_name") or "")
        bkf_n = _norm(person.get("best_known_for") or "")
        aliases_n = [_norm(a) for a in (person.get("aliases") or []) if a]
        occ_n = _norm(person.get("principal_occupation") or "")
        city_n = _norm(person.get("city_born") or "")
        desc_n = _norm(person.get("description") or "")

        name_words = name_n.split()
        alias_words = [w for a in aliases_n for w in a.split()]
        combined_names = " ".join([name_n, real_n, bkf_n, *aliases_n])

        score = 0
        if qn in (name_n, bkf_n, real_n) or qn in aliases_n:
            score = 1000
        elif name_n.startswith(qn) or bkf_n.startswith(qn):
            score = 750
        elif any(w.startswith(qn) for w in name_words):
            score = 600
        elif real_n.startswith(qn) or any(a.startswith(qn) for a in aliases_n) or any(w.startswith(qn) for w in alias_words):
            score = 500
        elif qn in name_n or qn in bkf_n:
            score = 400
        elif qn in real_n or any(qn in a for a in aliases_n):
            score = 320
        elif len(q_tokens) > 1 and all(t in combined_names for t in q_tokens):
            score = 260
        elif qn in occ_n or qn in city_n:
            score = 120
        elif qn in desc_n:
            score = 80
        else:
            # Fuzzy fallback for slight typos (e.g., "kansela" -> "kanzela", "piccaso" -> "picasso")
            candidates = [name_n, *name_words, *aliases_n, *alias_words]
            best_ratio = max(
                (SequenceMatcher(None, qn, cand).ratio() for cand in candidates if cand),
                default=0.0,
            )
            if best_ratio >= 0.73:
                score = int(best_ratio * 150)

        if score > 0:
            deg_bonus = min(int(person.get("degree") or 0), 15) * 2
            scored.append((score + deg_bonus, person))

    scored.sort(key=lambda item: (-item[0], _norm(item[1].get("name") or "")))
    return [item[1] for item in scored[:limit]]


def shortest_path(repo, from_id: str, to_id: str):
    """Compute the shortest verified path between two people with rich context, locations, and sources."""
    from_person_base = repo.get("people", from_id)
    to_person_base = repo.get("people", to_id)

    people_map = {}
    if hasattr(repo, "all_people_with_degree"):
        for p in repo.all_people_with_degree():
            people_map[p["id"]] = p
    people_map.setdefault(from_id, from_person_base)
    people_map.setdefault(to_id, to_person_base)

    if from_id == to_id:
        return {
            "found": True,
            "from_person": people_map[from_id],
            "to_person": people_map[to_id],
            "hop_count": 0,
            "steps": [],
        }

    facts = repo.all_verified_facts() if hasattr(repo, "all_verified_facts") else []
    adj = defaultdict(list)
    by_context = defaultdict(list)
    match_types = {"sports.faced_in_match", "sports.same_side_match"}

    for fact in facts:
        if fact.get("status") != "verified":
            continue
        spec = get_type(fact.get("type_id"))
        if not spec:
            continue
        if spec["shape"] == "direct":
            u = fact["subject_id"]
            v = fact["object_id"]
            if u == v:
                continue
            edge = {
                "type_id": fact["type_id"],
                "shape": "direct",
                "context_id": None,
                "context_kind": "person",
                "facts": [fact],
            }
            adj[u].append((v, edge))
            adj[v].append((u, edge))
        else:
            by_context[fact["object_id"]].append(fact)

    for ctx_id, ctx_facts in by_context.items():
        n = len(ctx_facts)
        for i in range(n):
            f1 = ctx_facts[i]
            spec = get_type(f1.get("type_id"))
            if not spec:
                continue
            for j in range(i + 1, n):
                f2 = ctx_facts[j]
                if f1["subject_id"] == f2["subject_id"]:
                    continue
                is_match = f1["type_id"] in match_types and f2["type_id"] in match_types
                if not is_match and f1["type_id"] != f2["type_id"]:
                    continue
                if spec.get("roles") and (
                    f1.get("role") not in spec["roles"] or f2.get("role") not in spec["roles"]
                ):
                    continue
                if is_match:
                    if not f1.get("side") or not f2.get("side"):
                        continue
                    result_type = (
                        "sports.same_side_match"
                        if f1["side"] == f2["side"]
                        else "sports.faced_in_match"
                    )
                else:
                    result_type = f1["type_id"]
                    rule = spec.get("pair_rule")
                    if rule == "opposite_side" and (
                        not f1.get("side") or not f2.get("side") or f1["side"] == f2["side"]
                    ):
                        continue
                    if rule == "same_side" and (
                        not f1.get("side") or f1["side"] != f2["side"]
                    ):
                        continue
                if spec["shape"] == "membership":
                    p1 = Period.model_validate(f1.get("period") or {})
                    p2 = Period.model_validate(f2.get("period") or {})
                    if not definitely_overlap(p1, p2):
                        continue
                if spec["shape"] == "work":
                    p1 = Period.model_validate(f1.get("period") or {})
                    p2 = Period.model_validate(f2.get("period") or {})
                    if not possibly_overlap(p1, p2):
                        continue

                u = f1["subject_id"]
                v = f2["subject_id"]
                edge = {
                    "type_id": result_type,
                    "shape": spec["shape"],
                    "context_id": ctx_id,
                    "context_kind": spec["context_kind"],
                    "facts": [f1, f2],
                }
                adj[u].append((v, edge))
                adj[v].append((u, edge))

    # BFS for shortest path
    queue = deque([from_id])
    visited = {from_id}
    parent = {from_id: None}

    found = False
    while queue:
        curr = queue.popleft()
        if curr == to_id:
            found = True
            break
        for nxt, edge in adj.get(curr, []):
            if nxt not in visited:
                visited.add(nxt)
                parent[nxt] = (curr, edge)
                queue.append(nxt)

    if not found:
        return {
            "found": False,
            "from_person": people_map.get(from_id) or repo.get("people", from_id),
            "to_person": people_map.get(to_id) or repo.get("people", to_id),
            "hop_count": 0,
            "steps": [],
        }

    # Reconstruct path
    raw_hops = []
    node = to_id
    while parent[node] is not None:
        prev_node, edge = parent[node]
        raw_hops.append((prev_node, node, edge))
        node = prev_node
    raw_hops.reverse()

    needed_ids = set()
    for _, _, edge in raw_hops:
        if edge.get("context_id"):
            needed_ids.add(edge["context_id"])
        for f in edge.get("facts") or []:
            if f.get("source_id"):
                needed_ids.add(f["source_id"])

    batch_nodes = (
        repo.get_nodes_by_ids(needed_ids)
        if hasattr(repo, "get_nodes_by_ids")
        else {}
    )
    context_cache = {}
    source_cache = {}
    collection_for_kind = {
        "work": "works",
        "event": "events",
        "organization": "organizations",
    }

    def get_person(pid):
        if pid not in people_map:
            people_map[pid] = repo.get("people", pid)
        return people_map[pid]

    def get_context(kind, cid):
        if not cid or kind not in collection_for_kind:
            return None
        if cid in batch_nodes:
            return batch_nodes[cid]
        key = (kind, cid)
        if key not in context_cache:
            try:
                context_cache[key] = repo.get(collection_for_kind[kind], cid)
            except Exception:
                context_cache[key] = None
        return context_cache[key]

    def get_source(sid):
        if not sid:
            return None
        if sid in batch_nodes:
            return batch_nodes[sid]
        if sid not in source_cache:
            try:
                source_cache[sid] = repo.get("sources", sid)
            except Exception:
                source_cache[sid] = None
        return source_cache[sid]

    steps = []
    for idx, (u_id, v_id, edge) in enumerate(raw_hops, start=1):
        u_person = get_person(u_id)
        v_person = get_person(v_id)
        spec = get_type(edge["type_id"]) or {}
        ctx = get_context(edge["context_kind"], edge["context_id"])
        edge_facts = edge["facts"]

        # Order facts so u's fact is first if shared context
        if len(edge_facts) == 2 and edge_facts[1].get("subject_id") == u_id:
            edge_facts = [edge_facts[1], edge_facts[0]]

        # Resolve location with lat/lng
        loc = None
        for f in edge_facts:
            floc = f.get("location")
            if floc and floc.get("lat") is not None and floc.get("lng") is not None:
                loc = floc
                break
        if not loc and ctx:
            cloc = ctx.get("location")
            if cloc and cloc.get("lat") is not None and cloc.get("lng") is not None:
                loc = cloc
        if not loc:
            for f in edge_facts:
                if f.get("location"):
                    loc = f.get("location")
                    break
        if not loc and ctx and ctx.get("place"):
            loc = {"name": ctx["place"]}

        # Resolve period
        period = None
        for f in edge_facts:
            p = f.get("period")
            if p and (p.get("start") or p.get("end")):
                period = p
                break
        if not period and ctx and ctx.get("period"):
            period = ctx.get("period")

        # Resolve notes & roles
        notes = []
        for f in edge_facts:
            n_txt = (f.get("note") or "").strip()
            if n_txt and n_txt not in notes:
                notes.append(n_txt)

        from_role = edge_facts[0].get("role") if edge_facts else None
        to_role = edge_facts[1].get("role") if len(edge_facts) > 1 else None
        from_side = edge_facts[0].get("side") if edge_facts else None
        to_side = edge_facts[1].get("side") if len(edge_facts) > 1 else None

        # Resolve sources
        sources = []
        seen_sids = set()
        for f in edge_facts:
            sid = f.get("source_id")
            src = get_source(sid)
            if src:
                entry = {
                    "id": src["id"],
                    "title": src.get("title"),
                    "url": src.get("url"),
                    "citation": src.get("citation"),
                    "author": src.get("author"),
                    "publisher": src.get("publisher"),
                    "locator": f.get("source_locator"),
                }
                if not loc and src.get("location"):
                    loc = src.get("location")
                if (sid, f.get("source_locator")) not in seen_sids:
                    seen_sids.add((sid, f.get("source_locator")))
                    sources.append(entry)

        steps.append({
            "step": idx,
            "from_person": u_person,
            "to_person": v_person,
            "type_id": edge["type_id"],
            "type_label": spec.get("label", edge["type_id"]),
            "supertype": spec.get("supertype", ""),
            "shape": edge["shape"],
            "context": ctx,
            "period": period,
            "location": loc,
            "note": " ".join(notes) if notes else (ctx.get("description") if ctx else ""),
            "notes": notes,
            "roles": {
                "from_role": from_role,
                "to_role": to_role,
                "from_side": from_side,
                "to_side": to_side,
            },
            "fact_ids": [f["id"] for f in edge_facts],
            "sources": sources,
        })

    return {
        "found": True,
        "from_person": get_person(from_id),
        "to_person": get_person(to_id),
        "hop_count": len(steps),
        "steps": steps,
    }

