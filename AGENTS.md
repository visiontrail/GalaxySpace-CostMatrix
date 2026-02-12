# Repository Guidelines

## Project Structure & Module Organization
- Root FastAPI service lives alongside analytics modules: `main.py`, `analysis_service.py`, `data_loader.py`, `export_service.py`, and logging helpers in `logger_config.py`; runtime artifacts go to `uploads/` and `logs/`.
- `backend/`: container-friendly FastAPI app (`app/main.py`, `api/routes.py`, `services/excel_processor.py`, `models/schemas.py`) with its own `requirements.txt`, `Dockerfile`, and `venv/`.
- `frontend/`: React + Vite dashboard (`src/main.tsx`, `layouts/`, `pages/`, `services/api.ts`); built assets land in `frontend/dist`.
- Utilities and config: data scripts in `scripts/` (e.g., `parse_excel_fields.py`, `query_project_cost.py`), stack orchestration via `docker-compose.yml`, sample env keys in `env.example`.

## Build, Test, and Development Commands
- Backend (root): `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`; run `python main.py` for the API.
- Backend (backend/): from `backend`, activate `venv` then `uvicorn app.main:app --reload --port 8000`; tests via `pytest` or `pytest --cov=app`.
- Frontend: `npm install`, `npm run dev` for local, `npm run build` for production bundle, `npm run lint` for ESLint, `npm run preview` to serve the build.
- Full stack: `docker-compose up --build` (API on `8000`, UI on `8180`).

## Coding Style & Naming Conventions
- Python: follow PEP8 (4-space indent) with type hints and short, single-purpose functions; modules/variables use `snake_case`; prefer pandas vectorized operations; log with `logger_config.get_logger`/`RequestLogger` instead of `print`.
- FastAPI: validate `.xlsx` uploads, clean temp files, and reuse `DataLoader`, `TravelAnalyzer`, and `ExcelExporter` when adding routes to keep behavior consistent.
- Frontend: TypeScript + React functional components in `PascalCase`; hooks and utilities in `camelCase`; keep API calls in `src/services/api.ts`; run `npm run lint` before submitting changes.

## Testing Guidelines
- Name backend tests `test_*.py`; keep them near the code or under `backend/tests/`; cover analytics branches and error handling; use `pytest --cov=app` for coverage.
- For manual smoke checks, start the API then run `python test_api.py <path-to.xlsx>`; use realistic samples from `data/` or `tesdata/`.
- Frontend currently relies on linting; if adding tests, prefer Vitest + React Testing Library and place files beside components.

## Commit & Pull Request Guidelines
- Use conventional commits as in history (`feat: ...`, `fix: ...`), keeping subjects concise (~72 chars).
- PRs should summarize scope, link issues/tasks, and include screenshots for UI or response samples for API changes.
- Confirm linting/formatting (`npm run lint`, chosen Python formatter) and tests/coverage before review; call out new env vars, data migrations, or scripts.

## Security & Configuration Tips
- Base settings on `env.example` and keep secrets in local `.env` files; never commit credentials or real traveler data.
- Avoid checking in generated payloads (`uploads/`, `logs/`, `backend/uploads/`, `backend/logs/`); clean them before commits.
- When exposing services, align ports and CORS (`5173` dev frontend, `8000` API, `8180` via Docker) and restrict origins in production.
