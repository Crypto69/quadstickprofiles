#!/bin/sh
# Wait for Postgres, migrate, seed (idempotent), then serve.
set -e
python - <<'PY'
import sys
import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db import engine

# "Still starting up" and "it will never work" look the same to a retry loop, so
# tell them apart: a refused connection is worth waiting for, a rejected password
# never is. Printing only the exception class (which this used to do) turns a
# one-line diagnosis into a long hunt.
FATAL = (
    ("password authentication failed", """
The database is running but rejected the password.

Postgres only applies POSTGRES_PASSWORD when it creates an *empty* data
directory. After that the password lives inside the data directory and the
environment variable is ignored — so changing QS_DB_PASSWORD in .env after the
first deploy leaves the API using the new one and the database still expecting
the old one. The database starts fine and reports healthy, which is why this
shows up as a login failure rather than a startup failure.

Either put the original password back in .env, or reset the password on the
database that already exists:

  docker compose exec db psql -U quadstick -d quadstick \\
    -c "alter user quadstick with password '<the value in .env>';"

If there is nothing in there worth keeping, delete the data directory and let it
initialise again with the password now in .env (this erases every profile):

  docker compose down && rm -rf data/pg && ./deploy.sh --no-pull
"""),
    ("permission denied", """
The database server is running but cannot read its own files.

Almost always an ownership mismatch on the bind-mounted data directory: the
directory belongs to one uid and the postgres user inside the image is another.
The Debian postgres image runs as uid 999, the -alpine variant as uid 70, and
deploy.sh chowns ./data/pg to 999. Postgres still starts and accepts
connections, so it looks like a login problem rather than a file problem.

Check them against each other:

  ls -lan data/pg | head -2                       # who owns the directory
  docker compose exec db id postgres              # who postgres runs as

Then make them agree (as root on the host):

  docker compose down && chown -R 999:999 data/pg && ./deploy.sh --no-pull
"""),
    ("does not exist", """
The database server is running but the database or role does not exist.

This usually means the data directory was initialised with different
POSTGRES_DB / POSTGRES_USER values than the API is now asking for. Check them
against QS_DATABASE_URL in docker-compose.yml.
"""),
)

last = None
for _ in range(60):
    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
        break
    except OperationalError as e:
        last = e
        msg = str(e.orig or e).lower()
        for needle, advice in FATAL:
            if needle in msg:
                print(f"\ncannot connect to the database: {e.orig or e}".rstrip(), flush=True)
                print(advice, flush=True)
                sys.exit(1)
        # transient: the server is not accepting connections yet
        print(f"waiting for database ({(e.orig or e).__class__.__name__}: "
              f"{str(e.orig or e).splitlines()[0][:80]})", flush=True)
        time.sleep(1)
    except Exception as e:              # a driver or URL problem, not a wait
        print(f"\ncannot connect to the database: {e.__class__.__name__}: {e}", flush=True)
        sys.exit(1)
else:
    print(f"\ndatabase never became ready after 60s. Last error:\n  {last.orig or last}"
          if last else "\ndatabase never became ready after 60s.", flush=True)
    sys.exit(1)
PY
alembic upgrade head
if [ "${QS_SEED_ON_START:-1}" = "1" ]; then python -m app.seed; fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
