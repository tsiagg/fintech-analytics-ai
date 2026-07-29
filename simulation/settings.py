import os


def postgres_dsn_parts() -> dict:
    return {
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": int(os.environ.get("POSTGRES_PORT", "5432")),
        "dbname": os.environ.get("POSTGRES_DB", "fintech"),
        "user": os.environ.get("POSTGRES_USER", "fintech"),
        "password": os.environ.get("POSTGRES_PASSWORD", "fintech_dev_change_me"),
    }
