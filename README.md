# Arc Lite

Rule-based FAQ assistant for ArchintX students. Matches questions with TF-IDF and cosine similarity and returns stored canonical answers only.

## Layout

- `backend/`: FastAPI app, matching engine, database access, tests
- `frontend/`: public chat page and staff screens (added in later steps)

## Backend setup (Windows Command Prompt)

Option A: double-click `setup.bat` in the project root. It creates the virtualenv, installs dependencies, and copies `backend\.env.example` to `backend\.env`.

Option B: run the steps yourself:

```bat
cd backend
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Fill in `backend\.env` (`DATABASE_URL`, `JWT_SECRET`) before running anything that touches the database.

## Backend setup (macOS / Linux)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in values
uvicorn app.main:app --reload
```

Health check: open `http://127.0.0.1:8000/health` in a browser. It should show `{"status": "ok"}`.
