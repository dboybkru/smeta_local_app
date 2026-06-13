"""Тип JSON, дающий JSONB на Postgres и обычный JSON на SQLite (тесты)."""
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# Использовать в mapped_column для JSONB-полей: contacts, utp, cases, proposal.
JSONType = JSON().with_variant(JSONB(), "postgresql")
