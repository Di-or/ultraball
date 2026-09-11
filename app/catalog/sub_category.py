def derive_sub_category(*, name: str, rarity: str | None) -> list[str]:
    """The `sub_category` array (CONTEXT.md: sub_category, mega ⊂ ex).

    Encodes mega ⊂ ex in the data itself: a Mega card carries `["ex", "mega"]`, so
    filtering `ex` also returns Mega-ex cards with no special-case gate logic.
    Derived from the printed name (the `ex`/`Mega` markers TCGdex bakes into it)
    and rarity (the only signal for the separate Ace Spec sub-category).
    """
    is_mega = "Mega " in name
    is_ex = is_mega or name.rstrip().endswith(" ex")

    categories = []
    if is_ex:
        categories.append("ex")
    if is_mega:
        categories.append("mega")
    if rarity and "ace spec" in rarity.lower():
        categories.append("ace-spec")
    return categories
