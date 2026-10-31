"""
Utilidades compartidas para verificar e insertar lotes históricos en Neo4j con calidad garantizada:
- Verificación de Wikidata ID (QID) y obtención automática de retrato oficial Wikimedia Commons (P18).
- Verificación HTTP 200 de cada URL de fuente (source.url) y de imagen.
- Inserción idempotente de Person, Source, Event, Work, Organization y Fact (status='verified').
"""

import time
import urllib.parse
import urllib.request
import json
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv

load_dotenv()

from database.neo4j_service import driver
from modules.graph.catalog import get_type
from modules.graph.models import (
    EventInput,
    FactInput,
    HistoricalDate,
    LocationInput,
    OrganizationInput,
    Period,
    PersonInput,
    SourceInput,
    WorkInput,
)
from modules.graph.repository import GraphRepository
from modules.graph.service import validate_event, validate_fact

repo = GraphRepository(driver)

USER_AGENT = "PathFamousFinderVerification/1.0 (https://github.com/danielocho500/path_famous_finder; danielnochess@gmail.com) Python-urllib/3"


def http_get_json(url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            if attempt == retries - 1:
                raise
            time.sleep(1.0 * (attempt + 1))
    return {}


def normalize_url(url: str) -> str:
    """Asegura que la URL tenga caracteres no-ASCII codificados adecuadamente."""
    parsed = urllib.parse.urlsplit(url.strip())
    path = urllib.parse.quote(urllib.parse.unquote(parsed.path), safe="/:@!$&'()*+,;=-._~")
    query = urllib.parse.quote(urllib.parse.unquote(parsed.query), safe="=&/:@!$'()*+,;-._~")
    fragment = urllib.parse.quote(urllib.parse.unquote(parsed.fragment), safe="/:@!$&'()*+,;=-._~")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, query, fragment))


def resolve_wikipedia_fallback(broken_url: str, fallback_title: str = "") -> Optional[str]:
    """Si una URL de Wikipedia da 404, busca el artículo real mediante la API oficial de búsqueda de Wikipedia."""
    parsed = urllib.parse.urlsplit(broken_url)
    host = parsed.netloc or "en.wikipedia.org"
    if "wikipedia.org" not in host:
        host = "en.wikipedia.org"
    slug = urllib.parse.unquote(parsed.path.split("/wiki/")[-1]).replace("_", " ") if "/wiki/" in parsed.path else ""
    for query in [fallback_title, slug]:
        if not query:
            continue
        api_url = (
            f"https://{host}/w/api.php?action=query&list=search"
            f"&srsearch={urllib.parse.quote(query)}&srlimit=1&format=json"
        )
        try:
            data = http_get_json(api_url)
            hits = ((data.get("query") or {}).get("search")) or []
            if hits and hits[0].get("title"):
                real_title = hits[0]["title"].replace(" ", "_")
                found_url = f"https://{host}/wiki/{urllib.parse.quote(real_title, safe='/:@!$&()*+,;=-._~')}"
                print(f"  [URL WIKIPEDIA CORREGIDA] {broken_url} -> {found_url}")
                return found_url
        except Exception:
            pass
    return None


def verify_url_http200(url: str, fallback_title: str = "") -> str:
    """Verifica que una URL responda HTTP 200 (siguiendo redirecciones). Si da 404 en Wikipedia, resuelve el artículo real."""
    if not url:
        raise ValueError("URL vacía")
    clean_url = normalize_url(url)
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(clean_url, method=method, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as resp:
                code = resp.getcode()
                if 200 <= code < 400:
                    return clean_url
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 406):
                continue
            if e.code == 404 and "wikipedia.org" in clean_url:
                resolved = resolve_wikipedia_fallback(clean_url, fallback_title)
                if resolved and resolved != clean_url:
                    return verify_url_http200(resolved, fallback_title="")
            raise RuntimeError(f"HTTP {e.code} al verificar URL: {clean_url}") from e
        except Exception as e:
            if method == "HEAD":
                continue
            raise RuntimeError(f"Error de red al verificar URL {clean_url}: {e}") from e
    raise RuntimeError(f"No se pudo verificar URL: {clean_url}")


def fetch_wikidata_info(qid: str) -> Dict[str, Any]:
    """Consulta Wikidata para un QID y devuelve label, description e image_url (P18)."""
    url = (
        f"https://www.wikidata.org/w/api.php?action=wbgetentities"
        f"&ids={urllib.parse.quote(qid)}&props=labels|descriptions|claims&languages=es|en&format=json"
    )
    data = http_get_json(url)
    entity = (data.get("entities") or {}).get(qid)
    if not entity or "missing" in entity:
        return {}
    labels = entity.get("labels") or {}
    descs = entity.get("descriptions") or {}
    label = (labels.get("es") or labels.get("en") or {}).get("value", "")
    desc = (descs.get("es") or descs.get("en") or {}).get("value", "")

    claims = entity.get("claims") or {}
    p18 = claims.get("P18") or []
    image_url = None
    if p18:
        try:
            filename = p18[0]["mainsnak"]["datavalue"]["value"]
            if filename:
                encoded = urllib.parse.quote(filename.replace(" ", "_"))
                image_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{encoded}?width=800"
        except (KeyError, IndexError, TypeError):
            pass

    return {
        "qid": qid,
        "label": label,
        "description": desc,
        "image_url": image_url,
    }


def search_wikidata_person(name: str) -> Optional[str]:
    """Busca el QID real de una persona en Wikidata por nombre."""
    for lang in ("es", "en"):
        url = (
            f"https://www.wikidata.org/w/api.php?action=wbsearchentities"
            f"&search={urllib.parse.quote(name)}&language={lang}&type=item&limit=5&format=json"
        )
        data = http_get_json(url)
        for item in data.get("search") or []:
            qid = item.get("id")
            if not qid:
                continue
            # Check if instance of human (Q5)
            ent_url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={qid}&props=claims&format=json"
            ent_data = http_get_json(ent_url)
            claims = ((ent_data.get("entities") or {}).get(qid) or {}).get("claims") or {}
            p31 = claims.get("P31") or []
            for st in p31:
                try:
                    target_id = st["mainsnak"]["datavalue"]["value"]["id"]
                    if target_id == "Q5":
                        return qid
                except (KeyError, TypeError):
                    pass
    return None


def resolve_and_verify_person_wikidata(name: str, proposed_qid: Optional[str], existing_image_url: Optional[str] = None, birth_year: Optional[int] = None) -> Dict[str, Optional[str]]:
    """
    Verifica que el QID propuesto corresponda a la persona (etiqueta + año de nacimiento);
    si no, lo resuelve vía Wikipedia (pageprops) o búsqueda en Wikidata. Nunca guarda un QID dudoso.
    """
    qid, entity = robust_resolve_qid(name, proposed_qid, birth_year)
    if qid != proposed_qid:
        print(f"  [QID CORREGIDO] '{name}': {proposed_qid} -> {qid}")
    image_url = existing_image_url or (entity_image_url(entity) if entity else None)
    return {"wikidata_id": qid, "image_url": image_url}


# ---------------------------------------------------------------------------
# Resolución robusta de QIDs (etiqueta + año de nacimiento + Wikipedia pageprops)
# ---------------------------------------------------------------------------
import unicodedata as _ud

_entity_cache: Dict[str, dict] = {}


def _norm_txt(text: str) -> str:
    return _ud.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()


def wd_entities(qids: List[str]) -> Dict[str, dict]:
    missing = [q for q in qids if q and q not in _entity_cache]
    for i in range(0, len(missing), 50):
        chunk = missing[i:i + 50]
        url = ("https://www.wikidata.org/w/api.php?action=wbgetentities&props=labels|aliases|claims|sitelinks"
               "&languages=es|en&sitefilter=eswiki|enwiki&format=json&ids=" + "|".join(chunk))
        data = http_get_json(url)
        for q, e in (data.get("entities") or {}).items():
            _entity_cache[q] = e if "missing" not in e else {}
    return {q: _entity_cache.get(q) or {} for q in qids if q}


def entity_birth_year(entity: dict) -> Optional[int]:
    try:
        t = entity["claims"]["P569"][0]["mainsnak"]["datavalue"]["value"]["time"]
        sign = -1 if t.startswith("-") else 1
        return sign * int(t[1:].split("-")[0])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def entity_is_person(entity: dict) -> bool:
    claims = entity.get("claims") or {}
    for st in claims.get("P31") or []:
        try:
            if st["mainsnak"]["datavalue"]["value"]["id"] in ("Q5", "Q20643955", "Q15632617"):
                return True
        except (KeyError, TypeError):
            pass
    return bool(claims.get("P569") or claims.get("P570"))


def entity_names(entity: dict) -> List[str]:
    names = []
    for lang in ("es", "en"):
        lab = (entity.get("labels") or {}).get(lang)
        if lab:
            names.append(lab["value"])
        names += [a["value"] for a in (entity.get("aliases") or {}).get(lang, [])]
    for site in ("eswiki", "enwiki"):
        sl = (entity.get("sitelinks") or {}).get(site)
        if sl:
            names.append(sl["title"])
    return names


def name_overlaps(name: str, entity: dict) -> bool:
    toks = {t for t in _norm_txt(name).replace("-", " ").split() if len(t) > 2}
    if not toks:
        return False
    for other in entity_names(entity):
        otoks = {t for t in _norm_txt(other).replace("-", " ").split() if len(t) > 2}
        if toks & otoks:
            return True
    return False


def entity_image_url(entity: dict) -> Optional[str]:
    try:
        filename = entity["claims"]["P18"][0]["mainsnak"]["datavalue"]["value"]
        return "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(filename.replace(" ", "_")) + "?width=800"
    except (KeyError, IndexError, TypeError):
        return None


def entity_matches(name: str, entity: dict, birth_year: Optional[int]) -> bool:
    if not entity or not entity_is_person(entity) or not name_overlaps(name, entity):
        return False
    wy = entity_birth_year(entity)
    if birth_year is not None and wy is not None:
        if birth_year < 0:
            tol = 100
        elif birth_year < 1500:
            tol = 50
        elif birth_year < 1850:
            tol = 10
        else:
            tol = 1
        return abs(wy - birth_year) <= tol
    return True


def wikipedia_qid(lang: str, title: str) -> Optional[str]:
    url = (f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=pageprops&redirects=1&format=json"
           f"&titles={urllib.parse.quote(title)}")
    try:
        data = http_get_json(url)
    except Exception:
        return None
    for page in ((data.get("query") or {}).get("pages") or {}).values():
        props = page.get("pageprops") or {}
        if "disambiguation" in props:
            return None
        if props.get("wikibase_item"):
            return props["wikibase_item"]
    return None


def robust_resolve_qid(name: str, proposed: Optional[str], birth_year: Optional[int]):
    if proposed:
        ent = wd_entities([proposed]).get(proposed)
        if entity_matches(name, ent, birth_year):
            return proposed, ent
    candidates = []
    for lang in ("es", "en"):
        q = wikipedia_qid(lang, name)
        if q:
            candidates.append(q)
    for lang in ("es", "en"):
        try:
            data = http_get_json(
                "https://www.wikidata.org/w/api.php?action=wbsearchentities&type=item&limit=7&format=json"
                f"&language={lang}&search={urllib.parse.quote(name)}")
            candidates += [it["id"] for it in data.get("search") or []]
        except Exception:
            pass
    seen = []
    for q in candidates:
        if q not in seen:
            seen.append(q)
    ents = wd_entities(seen)
    for q in seen:
        if entity_matches(name, ents.get(q), birth_year):
            return q, ents[q]
    return None, None


def make_date(d: Optional[dict]) -> Optional[HistoricalDate]:
    if not d or not d.get("year"):
        return None
    precision = d.get("precision") or "year"
    month = d.get("month") if precision in ("month", "day") else None
    day = d.get("day") if precision == "day" else None
    if precision == "day" and not day:
        precision = "month" if month else "year"
    if precision == "month" and not month:
        precision = "year"
    return HistoricalDate(
        year=int(d["year"]),
        precision=precision,
        month=int(month) if month else None,
        day=int(day) if day else None,
        approximate=bool(d.get("approximate", False)),
    )


def make_period(p: Optional[dict]) -> Period:
    if not p:
        return Period()
    start = make_date(p.get("start"))
    end = make_date(p.get("end"))
    return Period(start=start, end=end)


def find_existing_person(tx, wikidata_id: Optional[str], name: str):
    if wikidata_id:
        res = tx.run(
            "MATCH (p:Person {wikidata_id: $qid}) RETURN p.id AS id, coalesce(p.search_name, p.real_name) AS name, p.wikidata_id AS wikidata_id, p.image_url AS image_url, p.data AS data",
            qid=wikidata_id,
        ).single()
        if res:
            return dict(res)

    res = tx.run(
        """
        MATCH (p:Person)
        WHERE toLower(coalesce(p.search_name, '')) = toLower($name)
           OR toLower(coalesce(p.real_name, '')) = toLower($name)
           OR toLower(coalesce(p.best_known_for, '')) = toLower($name)
        RETURN p.id AS id, coalesce(p.search_name, p.real_name) AS name, p.wikidata_id AS wikidata_id, p.image_url AS image_url, p.data AS data
        LIMIT 1
        """,
        name=name,
    ).single()
    if res:
        return dict(res)
    return None


def upsert_person(person_data: dict) -> str:
    """Verifica QID e imagen en Wikidata, y crea o actualiza la persona en Neo4j."""
    name = person_data["name"].strip()
    resolved = resolve_and_verify_person_wikidata(
        name=name,
        proposed_qid=person_data.get("wikidata_id"),
        existing_image_url=person_data.get("image_url"),
        birth_year=(person_data.get("birth") or {}).get("year"),
    )
    qid = resolved["wikidata_id"]
    image_url = resolved["image_url"]
    if not qid:
        print(f"  [ADVERTENCIA] No se pudo verificar el QID de '{name}'; se guarda sin wikidata_id.")
    if not image_url:
        print(f"  [ADVERTENCIA] '{name}' no tiene retrato P18 en Wikidata.")

    with driver.session() as session:
        existing = session.execute_read(find_existing_person, qid, name)

    if existing:
        person_id = existing["id"]
        try:
            body = json.loads(existing.get("data") or "{}")
        except Exception:
            body = {}
        if image_url and not body.get("image_url"):
            body["image_url"] = image_url
        if qid and not body.get("wikidata_id"):
            body["wikidata_id"] = qid
        with driver.session() as session:
            session.run(
                """
                MATCH (p:Person {id: $id})
                SET p:Famous,
                    p.wikidata_id = coalesce(p.wikidata_id, $qid),
                    p.image_url = coalesce(p.image_url, $img),
                    p.principal_occupation = coalesce(p.principal_occupation, $occ),
                    p.data = $data
                """,
                id=person_id,
                qid=qid,
                img=image_url,
                occ=person_data.get("principal_occupation", ""),
                data=json.dumps(body, ensure_ascii=False) if body else existing.get("data"),
            )
        print(f"  [EXISTE PERSONA] {name} (ID: {person_id}, QID: {qid})")
        return person_id

    p_input = PersonInput(
        name=name,
        aliases=person_data.get("aliases") or [],
        description=person_data.get("description") or "",
        country=person_data.get("country"),
        city_born=person_data.get("city_born"),
        image_url=image_url,
        wikidata_id=qid,
        birth=make_date(person_data.get("birth")),
        death=make_date(person_data.get("death")),
    )
    created = repo.create("people", p_input.model_dump(mode="json"))
    person_id = created["id"]

    with driver.session() as session:
        session.run(
            """
            MATCH (p:Person {id: $id})
            SET p:Famous,
                p.real_name = $rn,
                p.best_known_for = $bkf,
                p.country = $c,
                p.image_url = $img,
                p.principal_occupation = $occ,
                p.profile_sumary_description = $desc
            """,
            id=person_id,
            rn=name,
            bkf=name,
            c=p_input.country,
            img=image_url,
            occ=person_data.get("principal_occupation", ""),
            desc=p_input.description,
        )
    print(f"  [NUEVA PERSONA] {name} (ID: {person_id}, QID: {qid}, Img: {'OK' if image_url else 'NONE'})")
    return person_id


_verified_urls_cache: Dict[str, str] = {}


def upsert_source(source_data: dict, location_data: Optional[dict] = None) -> str:
    title = (source_data.get("title") or "Fuente histórica verificada").strip()
    url = (source_data.get("url") or "").strip()
    if url:
        if url not in _verified_urls_cache:
            _verified_urls_cache[url] = verify_url_http200(url, fallback_title=title)
        url = _verified_urls_cache[url]

    with driver.session() as session:
        res = session.run(
            """
            MATCH (s:Source)
            WHERE toLower(coalesce(s.search_name, '')) = toLower($title)
            RETURN s.id AS id
            LIMIT 1
            """,
            title=title,
        ).single()
        if res:
            return res["id"]

    loc = LocationInput(**location_data) if location_data else None
    s_input = SourceInput(
        title=title,
        url=url or None,
        citation=source_data.get("citation") or title,
        author=source_data.get("author") or "Archivo histórico / Wikipedia",
        publisher=source_data.get("publisher") or "Wikipedia / Archivo",
        accessed_at="2026-10-28",
        location=loc,
    )
    created = repo.create("sources", s_input.model_dump(mode="json"))
    return created["id"]


def upsert_organization(name: str, kind: str, description: str) -> str:
    with driver.session() as session:
        rows = session.run(
            """
            MATCH (o:Organization)
            WHERE toLower(coalesce(o.search_name, '')) = toLower($name)
            RETURN o.id AS id, o.data AS data
            """,
            name=name.strip(),
        )
        for row in rows:
            body = json.loads(row["data"] or "{}")
            if body.get("kind") == kind:
                return row["id"]

    org_in = OrganizationInput(name=name.strip(), kind=kind, description=description or "")
    created = repo.create("organizations", org_in.model_dump(mode="json"))
    return created["id"]


def upsert_work(name: str, kind: str, period: Period, description: str) -> str:
    with driver.session() as session:
        rows = session.run(
            """
            MATCH (w:Work)
            WHERE toLower(coalesce(w.search_name, '')) = toLower($name)
            RETURN w.id AS id, w.data AS data
            """,
            name=name.strip(),
        )
        for row in rows:
            body = json.loads(row["data"] or "{}")
            if body.get("kind") == kind:
                return row["id"]

    work_in = WorkInput(name=name.strip(), kind=kind, period=period, description=description or "")
    created = repo.create("works", work_in.model_dump(mode="json"))
    return created["id"]


def upsert_event(name: str, kind: str, period: Period, location: LocationInput, source_id: str, locator: str) -> str:
    with driver.session() as session:
        rows = session.run(
            """
            MATCH (e:Event)
            WHERE toLower(coalesce(e.search_name, '')) = toLower($name)
            RETURN e.id AS id, e.data AS data
            """,
            name=name.strip(),
        )
        for row in rows:
            body = json.loads(row["data"] or "{}")
            if body.get("kind") == kind:
                return row["id"]

    ev_in = EventInput(
        name=name.strip(),
        kind=kind,
        period=period,
        place=location.name,
        location=location,
        source_id=source_id,
        source_locator=locator or "Registro principal",
        participants=[],
    )
    validated = validate_event(repo, ev_in)
    created = repo.create("events", validated)
    return created["id"]


def upsert_verified_fact(fact_input: FactInput) -> str:
    with driver.session() as session:
        if get_type(fact_input.type_id)["shape"] == "direct":
            res = session.run(
                """
                MATCH (p:Person)-[:SUBJECT_OF]->(f:Fact)-[:OBJECT]->(o:Person)
                WHERE ((p.id = $sub AND o.id = $obj) OR (p.id = $obj AND o.id = $sub))
                  AND f.type_id = $type_id
                RETURN f.id AS id, f.status AS status
                LIMIT 1
                """,
                sub=fact_input.subject_id,
                obj=fact_input.object_id,
                type_id=fact_input.type_id,
            ).single()
        else:
            res = session.run(
                """
                MATCH (p:Person {id: $sub})-[:SUBJECT_OF]->(f:Fact {type_id: $type_id})-[:OBJECT]->(o {id: $obj})
                RETURN f.id AS id, f.status AS status
                LIMIT 1
                """,
                sub=fact_input.subject_id,
                obj=fact_input.object_id,
                type_id=fact_input.type_id,
            ).single()

    if res:
        return res["id"]

    validated = validate_fact(repo, fact_input)
    created = repo.create("facts", validated)
    fact_id = created["id"]

    current = repo.get("facts", fact_id)
    data = {k: v for k, v in current.items() if k not in ("id", "revision", "created_at", "updated_at")}
    data["status"] = "verified"
    repo.update("facts", fact_id, current["revision"], validate_fact(repo, data), "verify")
    return fact_id


def resolve_person_id(qid: Optional[str], name: str, id_map: Dict[str, str]) -> str:
    if qid and qid in id_map:
        return id_map[qid]
    if name in id_map:
        return id_map[name]
    with driver.session() as session:
        existing = session.execute_read(find_existing_person, qid, name)
    if existing:
        if qid:
            id_map[qid] = existing["id"]
        id_map[name] = existing["id"]
        return existing["id"]
    raise KeyError(f"No se encontró en Neo4j a la persona: {name} ({qid})")


def ingest_connection(conn: dict, id_map: Dict[str, str]):
    """
    Normaliza, valida e inserta una conexión entre dos personas cumpliendo las reglas de catalog.py y service.py.
    """
    from_id = resolve_person_id(conn.get("from_wikidata_id"), conn["from_name"], id_map)
    to_id = resolve_person_id(conn.get("to_wikidata_id"), conn["to_name"], id_map)

    type_id = conn["type_id"]
    ctx = conn.get("context") or {}

    # Normalización inteligente si un lote externo usó sports.same_team para una empresa o institución
    if type_id == "sports.same_team" and ctx.get("kind") == "institution":
        type_id = "professional.same_project"
        ctx["category"] = "work"
        ctx["kind"] = "project"

    spec = get_type(type_id)
    if not spec:
        raise ValueError(f"Tipo de conexión desconocido: {type_id}")

    loc_dict = conn["location"]
    location = LocationInput(**loc_dict)
    period = make_period(conn.get("period"))
    # Ensure both start and end are populated if one is missing
    if period.start and not period.end:
        period = Period(start=period.start, end=period.start)
    elif period.end and not period.start:
        period = Period(start=period.end, end=period.end)

    source_data = conn["source"]
    source_id = upsert_source(source_data, loc_dict)
    locator = (source_data.get("locator") or source_data.get("citation") or "Sección principal").strip()
    note = (conn.get("note") or "").strip()

    shape = spec["shape"]
    if shape == "direct":
        if ctx.get("name") and ctx["name"].lower() not in note.lower():
            note = f"{ctx['name']}: {note}" if note else ctx["name"]
        fact_in = FactInput(
            type_id=type_id,
            subject_id=from_id,
            object_id=to_id,
            source_id=source_id,
            source_locator=locator,
            role=None,
            side=None,
            period=period,
            status="draft",
            note=note,
            location=location,
        )
        fid = upsert_verified_fact(fact_in)
        print(f"  [CONEXIÓN DIRECTA] {conn['from_name']} <-> {conn['to_name']} ({type_id}) -> Fact {fid}")
        return

    # Context-based connection (event, work, membership)
    ctx_name = (ctx.get("name") or f"Contexto {conn['from_name']} - {conn['to_name']}").strip()
    ctx_desc = (ctx.get("description") or note).strip()
    expected_kind = spec.get("context_type")

    if shape == "membership":
        org_kind = expected_kind or ctx.get("kind") or "team"
        ctx_id = upsert_organization(ctx_name, org_kind, ctx_desc)
    elif shape == "work":
        work_kind = expected_kind or ctx.get("kind") or "other"
        if work_kind not in ("film", "music", "book", "artwork", "project", "other"):
            work_kind = "other"
        ctx_id = upsert_work(ctx_name, work_kind, period, ctx_desc)
    elif shape == "event":
        ev_kind = expected_kind or ctx.get("kind") or "other"
        ctx_id = upsert_event(ctx_name, ev_kind, period, location, source_id, locator)
    else:
        raise ValueError(f"Shape no soportado: {shape}")

    allowed_roles = spec.get("roles") or []
    from_role = (conn.get("from_role") or "").strip().casefold() or None
    to_role = (conn.get("to_role") or "").strip().casefold() or None

    if allowed_roles:
        if from_role not in allowed_roles:
            from_role = allowed_roles[0]
        if to_role not in allowed_roles:
            to_role = allowed_roles[0]
    else:
        from_role = None
        to_role = None

    pair_rule = spec.get("pair_rule")
    from_side = (conn.get("from_side") or "").strip().casefold() or None
    to_side = (conn.get("to_side") or "").strip().casefold() or None
    if pair_rule == "opposite_side":
        from_side = from_side or "home"
        to_side = to_side if (to_side and to_side != from_side) else ("away" if from_side == "home" else "home")
    elif pair_rule == "same_side":
        from_side = from_side or "home"
        to_side = from_side
    else:
        from_side = None
        to_side = None

    f1 = FactInput(
        type_id=type_id,
        subject_id=from_id,
        object_id=ctx_id,
        source_id=source_id,
        source_locator=locator,
        role=from_role,
        side=from_side,
        period=period,
        status="draft",
        note=note,
        location=location,
    )
    f2 = FactInput(
        type_id=type_id,
        subject_id=to_id,
        object_id=ctx_id,
        source_id=source_id,
        source_locator=locator,
        role=to_role,
        side=to_side,
        period=period,
        status="draft",
        note=note,
        location=location,
    )
    fid1 = upsert_verified_fact(f1)
    fid2 = upsert_verified_fact(f2)
    print(f"  [CONEXIÓN CONTEXTO] {conn['from_name']} <-> {conn['to_name']} ({type_id} @ {ctx_name}) -> Facts {fid1}, {fid2}")


def ingest_batch(batch_title: str, people: List[dict], connections: List[dict]):
    print("=" * 80)
    print(f"  CARGANDO LOTE: {batch_title}")
    print("=" * 80)

    id_map: Dict[str, str] = {}
    print(f"\n--- 1. Verificando QIDs, retratos P18 y registrando {len(people)} personas ---")
    for p in people:
        orig_qid = p.get("wikidata_id")
        pid = upsert_person(p)
        id_map[p["name"].strip()] = pid
        if orig_qid:
            id_map[orig_qid] = pid

    print(f"\n--- 2. Verificando URLs (HTTP 200) y registrando {len(connections)} conexiones ---")
    for conn in connections:
        ingest_connection(conn, id_map)

    print(f"\n--- 3. Verificación de conectividad del lote '{batch_title}' ---")
    from modules.graph.service import shortest_path

    # Usamos Leonardo DiCaprio o Benito Juárez como nodo ancla del grafo principal
    anchor_id = None
    with driver.session() as session:
        res = session.run(
            "MATCH (p:Person) WHERE p.wikidata_id IN ['Q38111', 'Q160607', 'Q935'] RETURN p.id AS id, coalesce(p.search_name, p.real_name) AS name LIMIT 1"
        ).single()
        if res:
            anchor_id = res["id"]
            anchor_name = res["name"]

    if anchor_id:
        connected_count = 0
        disconnected = []
        for p in people:
            pid = id_map[p["name"].strip()]
            res_path = shortest_path(repo, pid, anchor_id)
            if res_path.get("found"):
                connected_count += 1
            else:
                disconnected.append(p["name"])
        print(f"  [CONECTIVIDAD] {connected_count}/{len(people)} personas conectadas a '{anchor_name}'.")
        if disconnected:
            print(f"  [ALERTA] Personas sin camino a '{anchor_name}': {disconnected}")
    print("=" * 80)

