import os

def conn_str():
    return os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/audit")