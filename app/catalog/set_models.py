from datetime import date

from pydantic import BaseModel


class SetSummary(BaseModel):
    """One distinct set for the Filter panel's set dropdown, labelled by `code`."""

    id: str
    code: str
    release_date: date
