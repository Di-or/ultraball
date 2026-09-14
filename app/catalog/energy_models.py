from pydantic import BaseModel

from app.catalog.models import Card


class EnergyBasic(BaseModel):
    """One basic-Energy type in the tray palette (CONTEXT.md: Basic-Energy tray)."""

    model_config = {"from_attributes": True}

    printing_id: str
    name: str
    energy_type: str | None
    types: list[str]
    image: str | None

    @classmethod
    def from_card(cls, card: Card) -> "EnergyBasic":
        return cls(
            printing_id=card.id,
            name=card.name,
            energy_type=card.energy_type,
            types=card.types,
            image=card.image,
        )


class EnergyBasicsResponse(BaseModel):
    palette: list[EnergyBasic]
