"""Dinner can be left out of planning (MEALPLANNER_DINNER_ENABLED=0) and everything stays consistent."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from auth_helpers import logged_in_client
from mealplanner.adapters.ortools import OrToolsPlanGenerator
from mealplanner.adapters.yaml_inputs import YamlPlannerInputReader
from mealplanner.application.generation import DinnerScopedInputReader, generate
from mealplanner.domain.catalog import MealType, Recipe
from mealplanner.domain.planner_inputs import PlannerInputs
from mealplanner.domain.snapshot import normalize_snapshot
from mealplanner.domain.weekly_rules import check_weekly_rules
from mealplanner.entrypoints.db_cli import import_inputs
from mealplanner.entrypoints.http.app import create_app
from mealplanner.entrypoints.settings import dinner_enabled

ROOT = Path(__file__).resolve().parents[2]
INPUTS = YamlPlannerInputReader(ROOT / "data").read()
LUNCH_ONLY = INPUTS.without_meal(MealType.DINNER)
WEEK = date(2026, 10, 26)


def snapshot(inputs: PlannerInputs, seed: int):
    result = generate(inputs, OrToolsPlanGenerator(), seed)
    return result, normalize_snapshot(
        result.plan.model_dump(), result.shopping_list.model_dump(), set(inputs.pantry), WEEK, "America/Bogota"
    )


def per_meal_proteins(plan: dict) -> dict[str, Counter]:
    counts: dict[str, Counter] = {}
    for slot in plan["slots"]:
        counts.setdefault(slot["meal"], Counter())[slot["protein"]] += 1
    return counts


def expected_counts(inputs: PlannerInputs) -> dict[str, Counter]:
    counts = inputs.rules.constraints.weekly_protein_counts
    return {
        meal.value: Counter({p.value: n for p, n in counts[meal].items() if n})
        for meal in inputs.rules.week.meals
    }


@pytest.mark.parametrize("seed", [1, 7, 42])
def test_lunch_only_generation_satisfies_every_specification(seed: int) -> None:
    result, snap = snapshot(LUNCH_ONLY, seed)
    assert {slot["meal"] for slot in snap.plan["slots"]} == {"lunch"}
    assert len(snap.plan["slots"]) == len(LUNCH_ONLY.rules.week.days)
    assert check_weekly_rules(snap, LUNCH_ONLY) == []
    assert per_meal_proteins(snap.plan) == expected_counts(LUNCH_ONLY)
    assert not any(slot["extended_from_lunch"] or slot["linked_assignment_id"] for slot in snap.plan["slots"])
    shopped = {row.item for rows in result.shopping_list.sections.values() for row in rows}
    variants = result.solution.assignments.values()
    planned = {ing.item for v in variants for ing in v.recipe.ingredients} | {v.carb_ingredient_id for v in variants}
    assert shopped <= planned


@pytest.mark.parametrize("seed", [1, 42])
def test_dinner_enabled_keeps_each_meals_protein_counts(seed: int) -> None:
    _, snap = snapshot(INPUTS, seed)
    assert check_weekly_rules(snap, INPUTS) == []
    assert per_meal_proteins(snap.plan) == expected_counts(INPUTS)


def test_a_week_with_dinners_breaks_lunch_only_rules() -> None:
    _, snap = snapshot(INPUTS, 1)
    assert "slot_coverage" in {v.rule for v in check_weekly_rules(snap, LUNCH_ONLY)}


def test_without_meal_keeps_the_dinner_settings_for_later() -> None:
    assert LUNCH_ONLY.rules.week.meals == [MealType.LUNCH]
    assert MealType.DINNER in LUNCH_ONLY.rules.constraints.weekly_protein_counts
    assert INPUTS.rules.week.meals == [MealType.LUNCH, MealType.DINNER]


def with_counts(meal: MealType, counts: dict) -> dict:
    rules = INPUTS.rules.model_dump(mode="json")
    rules["constraints"]["weekly_protein_counts"][meal.value] = counts
    return rules


def rebuild(rules: dict) -> PlannerInputs:
    return PlannerInputs(
        recipes=INPUTS.recipes, ingredients=INPUTS.ingredients,
        rules=type(INPUTS.rules).model_validate(rules), pantry=INPUTS.pantry,
    )


def test_each_planned_meal_counts_must_fill_its_days() -> None:
    with pytest.raises(ValueError, match="Dinner protein counts sum to 4"):
        rebuild(with_counts(MealType.DINNER, {"chicken": 2, "fish": 2}))


def test_unplanned_meal_counts_are_not_checked() -> None:
    rules = with_counts(MealType.DINNER, {"chicken": 1})  # would not fill five dinners
    rules["week"]["meals"] = ["lunch"]
    assert rebuild(rules).rules.week.meals == [MealType.LUNCH]


def test_a_planned_meal_needs_counts() -> None:
    rules = INPUTS.rules.model_dump(mode="json")
    del rules["constraints"]["weekly_protein_counts"]["lunch"]
    with pytest.raises(ValueError, match="No weekly protein counts for lunch"):
        rebuild(rules)


def test_protein_portion_override_must_name_a_known_ingredient() -> None:
    rules = INPUTS.rules.model_dump(mode="json")
    rules["protein_portion_overrides_g"]["fish_salmn"] = {"lunch": 200}
    with pytest.raises(ValueError, match="override references unknown ingredient: fish_salmn"):
        rebuild(rules)


def test_a_second_protein_row_must_be_protein_extra() -> None:
    recipe = INPUTS.recipes["bistec_a_caballo"].model_dump(mode="json")
    next(ing for ing in recipe["ingredients"] if ing["item"] == "egg")["role"] = "protein"
    with pytest.raises(ValueError, match="protein_extra"):
        Recipe.model_validate(recipe)


@pytest.mark.parametrize("raw,expected", [(None, True), ("", True), ("1", True), ("0", False), (" 0 ", False)])
def test_dinner_enabled_setting(monkeypatch, raw, expected) -> None:
    if raw is None:
        monkeypatch.delenv("MEALPLANNER_DINNER_ENABLED", raising=False)
    else:
        monkeypatch.setenv("MEALPLANNER_DINNER_ENABLED", raw)
    assert dinner_enabled() is expected


def test_dinner_enabled_rejects_other_values(monkeypatch) -> None:
    monkeypatch.setenv("MEALPLANNER_DINNER_ENABLED", "no")
    with pytest.raises(ValueError, match="must be 0 or 1"):
        dinner_enabled()


def test_scoped_reader_only_drops_dinner_when_disabled() -> None:
    class Reader:
        def read(self) -> PlannerInputs:
            return INPUTS

    assert DinnerScopedInputReader(Reader(), True).read() is INPUTS
    assert DinnerScopedInputReader(Reader(), False).read().rules.week.meals == [MealType.LUNCH]


def test_http_app_generates_lunch_only_weeks_when_dinner_is_disabled(tmp_path) -> None:
    db = tmp_path / "plans.db"
    import_inputs(db, ROOT / "data")
    now = datetime(2026, 10, 21, 15, 0, tzinfo=timezone.utc)
    client = logged_in_client(create_app(db_path=db, clock=lambda: now, dinner_enabled=False))
    response = client.post("/api/v1/plans", json={"week_start": WEEK.isoformat(), "seed": 1})
    assert response.status_code == 201, response.get_data(as_text=True)
    assert {slot["meal"] for slot in response.get_json()["slots"]} == {"lunch"}
