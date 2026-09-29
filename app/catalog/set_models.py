from datetime import date

from pydantic import BaseModel


class SetSummary(BaseModel):
    """One distinct set, derived from the cards table (there is no sets table)."""

    id: str
    code: str
    release_date: date
