"""Slug helpers shared by the product and category services."""

import re
import unicodedata
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

SLUG_BASE_MAX_LENGTH = 100


def slugify(value: str) -> str:
    """'Corsair Vengeance RGB 32GB' -> 'corsair-vengeance-rgb-32gb'."""
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:SLUG_BASE_MAX_LENGTH].strip("-") or "item"


def unique_slug(db: Session, model: Any, base: str) -> str:
    """Return `base`, or `base-2`, `base-3`, ... until no row of `model` uses it."""
    candidate, counter = base, 2
    while db.scalar(select(model.id).where(model.slug == candidate)) is not None:
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate
