"""Common helpers for FastAPI route groups."""


def normalize_filter_values(values: list[str] | None) -> list[str] | None:
    """Normalize repeated or comma-separated query values into a unique list."""
    if not values:
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        for key in item.split(","):
            clean_key = key.strip()
            if clean_key and clean_key not in seen:
                seen.add(clean_key)
                normalized.append(clean_key)

    return normalized or None
