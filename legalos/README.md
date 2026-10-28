# LegalOS — AI Legal & Compliance Operating System for Indian SMEs

LegalOS is a multi-workspace production-grade system designed for Indian SMEs to manage legal and compliance needs.

## LICENSE NOTE
> [!WARNING]
> This project uses **PyMuPDF** (via the `pymupdf` library) for PDF parsing, which is licensed under the **GNU AGPL (Affero General Public License)**. If this application is distributed or deployed as a public network service (SaaS), you must make the source code available under the AGPL terms.

## Part 1 Structure
- `backend/`: FastAPI application handling logic, centralized embeddings (MiniLM-L6-v2), Qdrant vector retrieval, and LLM orchestration (Gemini-3.5-flash).
- `frontend/`: React, TypeScript, Vite, Tailwind CSS v3.4 app implementing the workspace and role switcher dashboard.

## Quick Start
1. Copy `.env.example` to `.env` in the root:
   ```bash
   cp .env.example .env
   ```
   *Ensure you populate the `GEMINI_API_KEY`.*
2. Start the services:
   ```bash
   docker-compose up --build
   ```
3. Run migrations on startup (if not automatic):
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

## Backups

`scripts\backup.ps1` backs up everything that cannot be rebuilt: the Postgres database (`pg_dump`, custom format) and
every Qdrant collection (a snapshot each). Add `-IncludeUploads` to also zip `backend\uploads`.

```powershell
.\scripts\backup.ps1                       # -> backups\<yyyyMMdd-HHmmss>\legalos.dump + qdrant\*.snapshot
.\scripts\backup.ps1 -OutDir D:\legalos-backups -KeepDays 30 -IncludeUploads
```

Restore (stack running, backend stopped so nothing writes meanwhile):

```powershell
docker compose cp backups\<stamp>\legalos.dump db:/tmp/legalos.dump
docker compose exec -T db pg_restore -U legalos -d legalos --clean --if-exists /tmp/legalos.dump
# one Qdrant collection (repeat per file in backups\<stamp>\qdrant):
curl.exe -X POST "http://localhost:6335/collections/<name>/snapshots/upload?priority=snapshot" -F "snapshot=@backups\<stamp>\qdrant\<name>.snapshot"
```

The LLM response cache (`storage/llm_cache`) and registry cache (`storage/registry_cache`) are disposable and not backed up.
Run the script from Task Scheduler for a nightly backup. `/health` shows queue depth, cache stats and DB / Qdrant latency;
`/health/llm` shows the AI provider in detail. Every response carries an `X-Request-ID`; the same id is on every log line
of that request (set `LOG_FORMAT=json` for one JSON object per line).
