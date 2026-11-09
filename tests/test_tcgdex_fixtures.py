"""The real TCGdex fixtures still show the quirks they were picked for, and the real-shaped
factories match them (issue #108)."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.ingest import run_ingest
from app.catalog.models import Card, RawCard
from tests.factories import (
    make_tcgdex_basic_energy,
    make_tcgdex_pokemon,
    make_tcgdex_special_energy,
    make_tcgdex_trainer,
)
from tests.stubs import StubCatalogClient
from tests.tcgdex_fixtures import FIXTURE_PRINTING_IDS, fixture_snapshot, load_printing, load_set


# --- The committed fixtures show TCGdex's real quirks ---------------------------------------


def test_basic_energy_is_labelled_normal_with_no_effect() -> None:
    fire = load_printing("sve-002")

    assert fire["name"] == "Fire Energy"
    assert fire["category"] == "Energy"
    assert fire["energyType"] == "Normal"
    assert "effect" not in fire


def test_special_energies_are_also_labelled_normal() -> None:
    for printing_id in ("me02-124", "sv04-266"):
        special = load_printing(printing_id)

        assert special["category"] == "Energy"
        assert special["energyType"] == "Normal"
        assert special["effect"]


def test_stage_2_is_written_without_a_space_and_local_id_is_zero_padded() -> None:
    charizard = load_printing("me02-013")

    assert charizard["stage"] == "Stage2"
    assert charizard["localId"] == "013"


def test_promo_pair_shares_one_series_wide_release_date_and_one_has_no_image() -> None:
    with_image, without_image = load_printing("svp-101"), load_printing("svp-190")

    assert with_image["name"] == without_image["name"] == "Pikachu"
    assert with_image["set"]["id"] == without_image["set"]["id"] == "svp"
    assert fixture_snapshot("svp").release_date == date(2023, 3, 31)
    assert "image" in with_image
    assert "image" not in without_image


def test_drift_pair_writes_the_same_energy_symbol_two_ways() -> None:
    promo, set_printing = load_printing("mep-023"), load_printing("me02-013")

    assert promo["name"] == set_printing["name"] == "Mega Charizard X ex"
    assert "[R] Energy" in promo["attacks"][0]["effect"]
    assert "{R} Energy" in set_printing["attacks"][0]["effect"]


def test_textless_printing_is_a_trainer_with_no_english_effect() -> None:
    ultra_ball = load_printing("30th-128")

    assert ultra_ball["category"] == "Trainer"
    assert "effect" not in ultra_ball


def test_odd_regulation_marks_and_rarity() -> None:
    assert load_printing("mep-051")["regulationMark"] == "j"
    potion = load_printing("mfb-33")
    assert potion["regulationMark"] == "None"
    assert potion["rarity"] == "None"


def test_no_fixture_carries_volatile_pricing() -> None:
    for printing_id in FIXTURE_PRINTING_IDS:
        printing = load_printing(printing_id)
        assert "pricing" not in printing
        assert all("pricing" not in variant for variant in printing.get("variants_detailed", []))


def test_load_printing_returns_a_fresh_copy() -> None:
    load_printing("sve-002")["name"] = "Changed"

    assert load_printing("sve-002")["name"] == "Fire Energy"


def test_fixture_snapshot_carries_the_real_set_metadata() -> None:
    snapshot = fixture_snapshot("me02")

    assert snapshot.set_id == "me02"
    assert snapshot.name == "Phantasmal Flames"
    assert snapshot.release_date == date.fromisoformat(load_set("me02")["releaseDate"])
    assert snapshot.official_abbreviation == "PFL"
    assert sorted(card["id"] for card in snapshot.cards) == ["me02-013", "me02-124"]


def test_fixture_snapshot_can_be_limited_to_named_printings() -> None:
    snapshot = fixture_snapshot("svp", ["svp-190"])

    assert [card["id"] for card in snapshot.cards] == ["svp-190"]


async def test_every_fixture_printing_ingests(db_session: AsyncSession) -> None:
    set_ids = sorted({load_printing(printing_id)["set"]["id"] for printing_id in FIXTURE_PRINTING_IDS})
    catalog_client = StubCatalogClient({set_id: fixture_snapshot(set_id) for set_id in set_ids})

    for set_id in set_ids:
        await run_ingest(db_session, catalog_client, set_id)

    raw_ids = set(await db_session.scalars(select(RawCard.id)))
    card_ids = set(await db_session.scalars(select(Card.id)))
    assert raw_ids == card_ids == set(FIXTURE_PRINTING_IDS)


# --- The factories build TCGdex's real shapes -----------------------------------------------


def _assert_same_shape(made: dict, *real_printing_ids: str) -> None:
    """Every key the factory sets is one TCGdex sends on these printings, with the same JSON type."""
    real: dict = {}
    for printing_id in real_printing_ids:
        real |= load_printing(printing_id)
    assert set(made) <= set(real), set(made) - set(real)
    for key, value in made.items():
        assert type(value) is type(real[key]), key


def test_pokemon_factory_matches_a_real_pokemon() -> None:
    made = make_tcgdex_pokemon()

    _assert_same_shape(made, "mep-051", "svp-101")
    assert set(made["attacks"][0]) == set(load_printing("mep-051")["attacks"][0])
    assert "abilities" not in made


def test_pokemon_factory_derives_a_zero_padded_local_id_and_set_from_the_id() -> None:
    made = make_tcgdex_pokemon(id="me02-013")

    assert made["localId"] == "013"
    assert made["set"]["id"] == "me02"


def test_pokemon_factory_writes_evolution_stages_as_tcgdex_does() -> None:
    made = make_tcgdex_pokemon(stage="Stage2", evolveFrom="Charmeleon")

    _assert_same_shape(made, "me02-013")
    assert made["stage"] == "Stage2"


def test_trainer_factory_matches_a_real_trainer() -> None:
    made = make_tcgdex_trainer()

    _assert_same_shape(made, "mfb-33", "30th-128")
    assert made["category"] == "Trainer"
    assert made["effect"]


def test_basic_energy_factory_matches_real_basic_energy() -> None:
    made = make_tcgdex_basic_energy()

    _assert_same_shape(made, "sve-002", "me02-124")
    assert made["name"] == "Fire Energy"
    assert made["energyType"] == "Normal"
    assert "effect" not in made


def test_basic_energy_factory_names_the_energy_after_its_type() -> None:
    assert make_tcgdex_basic_energy(energy="Water")["name"] == "Water Energy"


def test_special_energy_factory_matches_real_special_energy() -> None:
    made = make_tcgdex_special_energy()

    _assert_same_shape(made, "me02-124")
    assert made["energyType"] == "Normal"
    assert "{C}" in made["effect"]


def test_factory_fields_are_overridable() -> None:
    made = make_tcgdex_pokemon(name="Bulbasaur", regulationMark="j", hp=70)

    assert (made["name"], made["regulationMark"], made["hp"]) == ("Bulbasaur", "j", 70)


def test_overriding_a_field_with_none_leaves_it_out_as_tcgdex_does() -> None:
    made = make_tcgdex_trainer(effect=None, image=None)

    assert "effect" not in made
    assert "image" not in made
