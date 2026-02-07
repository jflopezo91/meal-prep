"""Plan rendering and output generation."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from pydantic import BaseModel

from .solve import MealPlanSolution
from .shopping import ShoppingList
from .load import DataLoader
from .config import ProteinType, IngredientKind


class PlanSlot(BaseModel):
    """Output format for a single slot."""
    day: str
    meal: str
    recipeId: str
    recipeName: str
    variantId: str
    protein: str
    carb: str # "none" or carb_id


class PlanDerivedStats(BaseModel):
    """Derived statistics from the plan."""
    protein_counts: dict[str, int]
    carb_counts: dict[str, int]


class PlanOutput(BaseModel):
    """Final JSON output structure."""
    seed: int
    generated_at: str
    slots: list[PlanSlot]
    derived: PlanDerivedStats


def render_plan(
    solution: MealPlanSolution, 
    loader: DataLoader, 
    seed: int,
    output_dir: Path
) -> None:
    """Render plan and shopping list to JSON files."""
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Convert slots to output format
    slots: list[PlanSlot] = []
    
    # Stats tracking
    protein_counts = {pt.value: 0 for pt in ProteinType}
    carb_counts = {}
    
    # Sort slots by day then meal
    sorted_slots = sorted(
        solution.assignments.keys(),
        key=lambda s: (
            loader.rules.week.days.index(s.split('_')[0]), 
            loader.rules.week.meals.index(s.split('_')[1])
        )
    )
    
    for slot_id in sorted_slots:
        variant = solution.assignments[slot_id]
        parts = slot_id.split('_')
        day = parts[0]
        meal = parts[1]
        
        # Track protein
        pt = variant.recipe.tags.primary_protein
        protein_counts[pt.value] += 1
        
        # Track carb
        carb = "none"
        if variant.carb_ingredient_id:
            carb = variant.carb_ingredient_id
            carb_counts[carb] = carb_counts.get(carb, 0) + 1
            
        slots.append(PlanSlot(
            day=day,
            meal=meal,
            recipeId=variant.base_recipe_id,
            recipeName=variant.recipe.name,
            variantId=variant.variant_id,
            protein=pt.value,
            carb=carb
        ))
        
    # 2. Create Plan object
    plan = PlanOutput(
        seed=seed,
        generated_at=datetime.now().isoformat(),
        slots=slots,
        derived=PlanDerivedStats(
            protein_counts=protein_counts,
            carb_counts=carb_counts
        )
    )
    
    # 3. Write plan.json
    with open(output_dir / "plan.json", "w") as f:
        f.write(plan.model_dump_json(indent=2))
        
    print(f"✓ Wrote plan.json to {output_dir}")
    
    # 4. Write stats summary to console
    print("\nPlan Statistics:")
    print("Protein Counts:")
    for pt, count in protein_counts.items():
        print(f"  {pt}: {count}")
        
    print("\nCarb Counts:")
    for carb, count in carb_counts.items():
        print(f"  {carb}: {count}")
