# CCL AI Suite

## Full AI tool suite


#### How To Start:

- Make sure Python 3.x is installed.
- Clone this repo
 ```bash
git clone https://github.com/EF-Code/ccl-suite.git
```
- Create a virtual environment
```bash
cd ccl-suite
python -m venv .venv
```
- Install dependencies
```bash
python -m pip install -r requirements.txt
```

- Start the API:

```bash
python -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation.

## API endpoints

- `GET /health` returns the service status.
- `POST /projects` creates an in-memory project from a title and optional description.
- `GET /projects` lists projects created since the server started.

Request bodies are limited to 1 MiB. The API endpoints still use temporary
in-memory storage until the database repository is connected.

## Database setup

```bash
export DATABASE_URL='postgresql+psycopg://localhost/ccl_suite'
python -m alembic upgrade head
```

To roll the local schema back to its empty state:

```bash
python -m alembic downgrade base
```

## Tests

```bash
python -m pytest
```
