"""Audita y corrige wikidata_id / image_url de TODAS las personas en Neo4j.
Uso: python fix_all_qids.py [--apply]
"""
import json
import sys

from scripts.batch_loader_utils import driver, robust_resolve_qid, entity_image_url, wd_entities

APPLY = "--apply" in sys.argv

with driver.session() as s:
    rows = [dict(r) for r in s.run(
        "MATCH (p:Person) RETURN p.id AS id, coalesce(p.search_name, p.real_name) AS name, "
        "p.wikidata_id AS qid, p.image_url AS img, p.data AS data")]

used = {r["qid"]: r["id"] for r in rows if r["qid"]}
wd_entities([r["qid"] for r in rows if r["qid"]])  # precarga en bloque

changes, unresolved = [], []
for r in rows:
    try:
        body = json.loads(r["data"] or "{}")
    except Exception:
        body = {}
    by = (body.get("birth") or {}).get("year")
    qid, ent = robust_resolve_qid(r["name"], r["qid"], by)
    if qid == r["qid"]:
        if ent and not r["img"]:
            img = entity_image_url(ent)
            if img:
                changes.append((r, qid, img, "solo imagen"))
        continue
    if qid is None:
        unresolved.append(r)
        continue
    if qid in used and used[qid] != r["id"]:
        print(f"[DUPLICADO] {r['name']} -> {qid} ya pertenece a otro nodo ({used[qid]})")
        continue
    img = entity_image_url(ent) or r["img"]
    changes.append((r, qid, img, f"{r['qid']} -> {qid}"))

for r, qid, img, why in changes:
    print(f"[CAMBIO] {r['name']}: {why}")
for r in unresolved:
    print(f"[SIN RESOLVER] {r['name']} (QID actual {r['qid']}) -> se quitará el QID incorrecto")

if APPLY:
    with driver.session() as s:
        for r, qid, img, why in changes:
            body = json.loads(r["data"] or "{}")
            body["wikidata_id"] = qid
            if img:
                body["image_url"] = img
            s.run("MATCH (p:Person {id:$id}) SET p.wikidata_id=$q, p.image_url=$img, p.data=$d",
                  id=r["id"], q=qid, img=img, d=json.dumps(body, ensure_ascii=False))
            used[qid] = r["id"]
        for r in unresolved:
            if not r["qid"]:
                continue
            body = json.loads(r["data"] or "{}")
            body["wikidata_id"] = None
            s.run("MATCH (p:Person {id:$id}) REMOVE p.wikidata_id SET p.data=$d",
                  id=r["id"], d=json.dumps(body, ensure_ascii=False))
    print(f"APLICADO: {len(changes)} cambios, {len(unresolved)} QIDs incorrectos retirados.")
else:
    print(f"DRY RUN: {len(changes)} cambios, {len(unresolved)} sin resolver.")
driver.close()
