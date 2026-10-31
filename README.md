# **Path Finder** 🔗🎯  

*"Every connection needs a story and a source."*

The goal is to find explainable, source-backed paths between real people through documented relationships and concrete shared events. Phase 1 includes a private manual editor and JSON API for people, sources, contexts, and documented facts. Multi-hop path search is the next phase.

---

### **How It Works** 🔍  
- Neo4j stores people, events, organizations, works, sources, and versioned facts. Direct connections are derived from verified facts and their sources.

The proposed data model is in [docs/graph-architecture.md](docs/graph-architecture.md); the first delivery plan for a manual editor is in [docs/phase-1-manual-editor.md](docs/phase-1-manual-editor.md).

---

## **Technologies Used** 🛠️  
- **Neo4j** (*"It’s like LinkedIn for celebrities and dead philosophers"*)  
- **FastAPI** (*"Faster than explaining your conspiracy theory"*)  

---

## **Setup & Run** 🚀  

### 1. **Clone the Project**  
```sh
git clone https://github.com/danielocho500/path_famous_finder
```

### 2. Prepare environment variables

Create a `.env` file in the project root. Docker Compose passes these values to the API. Neo4j and Cloudinary must be available separately. When Neo4j runs on your Mac, Python connects through `localhost`, while the web container reaches the same instance through `host.docker.internal`.

Required environment variables:

- PREFIX= "/prefix"
- PROD= 1 if prod, 0 if dev
- CLOUDINARY_CLOUD_NAME=
- CLOUDINARY_API_KEY=
- CLOUDINARY_API_SECRET=
- CLOUDINARY_URL=
- NEO4J_URI=bolt://localhost:7687 for local Python / Neo4j Desktop
- NEO4J_DOCKER_URI=bolt://host.docker.internal:7687 for the web container (default)
- NEO4J_USER=
- NEO4J_PASS=
- WEB_BIND_IP=127.0.0.1 by default; use a private LAN/VPN address for team access

### 3. Use docker compose to build and run the project
```sh
docker compose up --build
```

Open `http://localhost:8004/relation_finder/editor` for the editor and
`http://localhost:8004/relation_finder/docs` for the API documentation. If
`PREFIX` differs, replace `relation_finder` in the URL. No application login
is provided; keep `WEB_BIND_IP` on a private interface or behind an internal
proxy.

To inspect legacy `Famous` records before migration:

```sh
docker compose exec web python scripts/migrate_famous.py
```

To add the `Person` label and editor fields to those same nodes without
removing their existing properties:

```sh
docker compose exec web python scripts/migrate_famous.py --apply
```

The migration is repeatable and reports duplicate names without merging them.
New records sent to the legacy `/famous` endpoint are also written as `Person`
nodes. The initial connection catalogue lives in
[`app/modules/graph/catalog.py`](app/modules/graph/catalog.py). The editor
allows creating and editing its instances; adding a new subtype changes code.

The editor supports year-level dates (use negative years for BCE). The API also
accepts month/day precision and approximate dates. Each fact requires a source
and a locator such as a page or section. Verify both participation facts to
show a shared connection. Editing a verified fact or its source/context sends
dependent facts back to draft for review. Facts are archived, not deleted.

The JSON API is under `/relation_finder/api/v1` (or your configured `PREFIX`).
It exposes `GET`/`POST` on `/people`, `/sources`, `/organizations`, `/works`,
`/events`, and `/facts`; `GET`/`PATCH` on `/{collection}/{id}`;
`POST /facts/batch`, `/facts/{id}/verify`, and `/facts/{id}/archive`;
`GET /people/{id}/connections`, `/sources/{id}/facts`, and
`/{collection}/{id}/history`. Send the revision returned by a record when
editing, verifying, or archiving it. New facts always begin as drafts.

For example, after creating two people and a source, a direct family fact is:

```json
{"type_id":"family.parent_of","subject_id":"PERSON_ID_1","object_id":"PERSON_ID_2","source_id":"SOURCE_ID","source_locator":"p. 42"}
```

Send it to `POST /facts`, then `POST /facts/{id}/verify` with
`{"revision":1}` after reviewing the source.

Run the local tests with:

```sh
PYTHONPATH=app python -m unittest discover -s app/test -v
```
