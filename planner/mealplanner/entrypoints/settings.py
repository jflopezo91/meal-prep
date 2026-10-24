"""Settings read from the environment, shared by the CLIs and the HTTP app."""

import os


def dinner_enabled() -> bool:
    """MEALPLANNER_DINNER_ENABLED: unset or 1 plans dinner, 0 plans lunch only."""
    raw = (os.environ.get("MEALPLANNER_DINNER_ENABLED") or "1").strip()
    if raw not in ("0", "1"):
        raise ValueError("MEALPLANNER_DINNER_ENABLED must be 0 or 1")
    return raw == "1"
