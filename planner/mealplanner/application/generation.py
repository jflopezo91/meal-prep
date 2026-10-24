"""Pure generation services shared by command-line and other input adapters."""

from dataclasses import dataclass

from ..domain.catalog import MealType
from ..domain.planner_inputs import PlannerInputs
from ..domain.solution import MealPlanSolution
from .plan_output import PlanOutput, build_plan_output
from .ports import PlanGenerator, PlannerInputReader
from .shopping import ShoppingList, generate_shopping_list


class DinnerScopedInputReader:
    """PlannerInputReader that leaves dinner out of planning when dinner is disabled.

    The stored inputs keep their dinner settings, so enabling dinner again needs no import.
    """

    def __init__(self, reader: PlannerInputReader, dinner_enabled: bool) -> None:
        self._reader = reader
        self._dinner_enabled = dinner_enabled

    def read(self) -> PlannerInputs:
        inputs = self._reader.read()
        return inputs if self._dinner_enabled else inputs.without_meal(MealType.DINNER)


@dataclass(frozen=True)
class GeneratedPlan:
    """In-memory result of one complete plan generation request."""

    solution: MealPlanSolution
    plan: PlanOutput
    shopping_list: ShoppingList


def generate(
    inputs: PlannerInputs,
    generator: PlanGenerator,
    seed: int = 42,
    generated_at: str | None = None,
) -> GeneratedPlan:
    """Generate a solution through the port and construct all output DTOs without writing files."""
    solution = generator.generate(inputs, seed)
    shopping_list = generate_shopping_list(solution, inputs)
    plan = build_plan_output(solution, inputs, seed, generated_at=generated_at)
    return GeneratedPlan(solution=solution, plan=plan, shopping_list=shopping_list)
