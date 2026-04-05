# CTF Backend (Flask + Oracle)

This backend provides API endpoints and Oracle database connectivity for the CTF platform.

## Setup

1. Create an Oracle database/schema.
2. Set `ORACLE_USER`, `ORACLE_PASSWORD`, and `ORACLE_DSN`.
3. Install dependencies.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Database

Run `schema.sql` against your Oracle schema to create the tables.

For existing databases, run the migration script before starting the backend:

```sql
@migrations/20260404_challenge_soft_delete.sql
```

Required environment variables:

- `ORACLE_USER`
- `ORACLE_PASSWORD`
- `ORACLE_DSN`
- `CORS_ORIGIN` for your frontend URL

## Run locally

```powershell
python app.py
```

Server default: `http://localhost:3000`

## Test endpoints

- Health check: `GET http://localhost:3000/api/health`
- Database ping: `GET http://localhost:3000/api/db/ping`
- Admin deactivate challenge (soft delete): `DELETE http://localhost:3000/api/admin/challenges/<challenge_no>`
