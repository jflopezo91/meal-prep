"""Solver constraint implementation."""

from typing import Optional
from ortools.sat.python import cp_model
from pydantic import BaseModel

from .config import Rules, MealType, ProteinType, IngredientKind, Ingredient
from .model import PlannerModel, Slot, create_model
from .variants import RecipeVariant, expand_variants
from .load import DataLoader


class MealPlanSolution(BaseModel):
    """A valid meal plan solution."""
    
    # Map slot ID -> Chosen Variant
    assignments: dict[str, RecipeVariant]
    
    class Config:
        arbitrary_types_allowed = True


def add_weekly_protein_constraints(model: PlannerModel, rules: Rules) -> None:
    """Implement constraint 1: Weekly protein counts."""
    # Sum of all slots for each protein type must equal the configured count
    
    for protein_type, count in rules.constraints.weekly_protein_counts.items():
        relevant_vars = []
        
        for slot in model.slots:
            slot_vars = model.vars[slot.id]
            for variant in model.variants:
                if variant.variant_id in slot_vars:
                    # check if this variant uses this protein
                    if variant.recipe.tags.primary_protein == protein_type:
                        relevant_vars.append(slot_vars[variant.variant_id])
                        
        if relevant_vars:
            model.model.Add(sum(relevant_vars) == count)


def add_consecutive_protein_constraints(model: PlannerModel, rules: Rules) -> None:
    """Implement constraint 2: No consecutive same protein."""
    if not rules.constraints.no_consecutive_same_protein:
        return
        
    for protein_type in ProteinType:
        # Check per meal type (planning doc says "Applied per meal type")
        for meal in rules.week.meals:
            # For each day d and d+1
            for day_idx in range(len(rules.week.days) - 1):
                # Get vars for (day, meal) and (day+1, meal)
                current_slot = model.slots[day_idx * len(rules.week.meals) + rules.week.meals.index(meal)]
                next_slot = model.slots[(day_idx + 1) * len(rules.week.meals) + rules.week.meals.index(meal)]
                
                # Verify we got the right slots (sanity check)
                assert current_slot.day_index == day_idx and current_slot.meal == meal
                assert next_slot.day_index == day_idx + 1 and next_slot.meal == meal
                
                current_vars = []
                next_vars = []
                
                # Collect vars for this protein type
                for variant in model.variants:
                    if variant.recipe.tags.primary_protein == protein_type:
                        if variant.variant_id in model.vars[current_slot.id]:
                            current_vars.append(model.vars[current_slot.id][variant.variant_id])
                        if variant.variant_id in model.vars[next_slot.id]:
                            next_vars.append(model.vars[next_slot.id][variant.variant_id])
                            
                # Constraint: term1 + term2 <= 1
                # If both have protein P, sum is 2, which is > 1 -> disallowed
                if current_vars and next_vars:
                    # We sum all variants of protein P for the slot (should only be 1 selected anyway)
                    # Let A = sum(current_vars), B = sum(next_vars)
                    # A + B <= 1
                    model.model.Add(sum(current_vars) + sum(next_vars) <= 1)


def add_fish_dinner_constraints(model: PlannerModel, rules: Rules) -> None:
    """Implement constraints 3 & 4: Fish dinner limits."""
    
    # Collect all fish dinner variables by day
    fish_vars_by_day = []
    
    for day_idx in range(len(rules.week.days)):
        # Find dinner slot for this day
        # Assumes meals are ordered and dinner is last, but safe way is to find it
        dinner_slot = next(s for s in model.slots if s.day_index == day_idx and s.meal == MealType.DINNER)
        
        day_fish_vars = []
        for variant in model.variants:
            if variant.recipe.tags.primary_protein == ProteinType.FISH:
                if variant.variant_id in model.vars[dinner_slot.id]:
                    day_fish_vars.append(model.vars[dinner_slot.id][variant.variant_id])
        
        fish_vars_by_day.append(sum(day_fish_vars))
        
    # Constraint 3: Max total fish dinners
    model.model.Add(sum(fish_vars_by_day) <= rules.constraints.fish_dinner_max_per_week)
    
    # Constraint 4: Max consecutive fish dinners (sliding window)
    window_size = 3 # d, d+1, d+2 (max 2 means sum <= 2)
    # The requirement is "max 2 consecutive", meaning NO 3 in a row.
    # So sum of any 3 consecutive days <= 2
    
    for i in range(len(fish_vars_by_day) - 2):
        model.model.Add(
            fish_vars_by_day[i] + 
            fish_vars_by_day[i+1] + 
            fish_vars_by_day[i+2] 
            <= rules.constraints.fish_dinner_max_consecutive
        )


def add_meal_carb_rules(model: PlannerModel, rules: Rules) -> None:
    """Implement constraint 5: Meal carb rules (no carbs at dinner)."""
    
    for meal_type, rule in rules.meal_rules.items():
        if not rule.allow_carbs:
            # Find all slots of this meal type
            for slot in model.slots:
                if slot.meal == meal_type:
                    # Ensure NO variant with carbs is selected
                    carb_vars = []
                    for variant in model.variants:
                        if variant.is_carb_variant:
                            if variant.variant_id in model.vars[slot.id]:
                                carb_vars.append(model.vars[slot.id][variant.variant_id])
                                
                    if carb_vars:
                         model.model.Add(sum(carb_vars) == 0)


def add_carb_frequency_constraints(
    model: PlannerModel, ingredients: dict[str, Ingredient]
) -> None:
    """Implement constraint 6: Carb frequency limits."""
    
    # Identify all limited carbs
    limited_carbs = {
        ing_id: ing.max_times_week 
        for ing_id, ing in ingredients.items() 
        if ing.kind == IngredientKind.CARB and ing.max_times_week is not None
    }
    
    for carb_id, limit in limited_carbs.items():
        relevant_vars = []
        
        for slot in model.slots:
            slot_vars = model.vars[slot.id]
            for variant in model.variants:
                if variant.carb_ingredient_id == carb_id:
                    if variant.variant_id in slot_vars:
                        relevant_vars.append(slot_vars[variant.variant_id])
                        
        if relevant_vars:
            model.model.Add(sum(relevant_vars) <= int(limit))


def add_recipe_frequency_constraints(model: PlannerModel, rules: Rules) -> None:
    """Implement constraint 7: Max once per week per base recipe."""
    
    # Group variants by base recipe
    variants_by_recipe = {}
    for variant in model.variants:
        if variant.base_recipe_id not in variants_by_recipe:
            variants_by_recipe[variant.base_recipe_id] = []
        variants_by_recipe[variant.base_recipe_id].append(variant)
        
    for recipe_id, variants in variants_by_recipe.items():
        relevant_vars = []
        for slot in model.slots:
            slot_vars = model.vars[slot.id]
            for variant in variants:
                if variant.variant_id in slot_vars:
                    relevant_vars.append(slot_vars[variant.variant_id])
                    
        if relevant_vars:
            model.model.Add(sum(relevant_vars) <= rules.constraints.max_recipe_uses_per_week)


def solve_plan(loader: DataLoader, seed: int = 42) -> MealPlanSolution:
    """Generate a meal plan."""
    
    # 1. Expand variants
    variants = expand_variants(loader.recipes, loader.ingredients)
    
    # 2. Create model
    planner_model = create_model(loader.rules, variants)
    
    # 3. Add constraints
    add_weekly_protein_constraints(planner_model, loader.rules)
    add_consecutive_protein_constraints(planner_model, loader.rules)
    add_fish_dinner_constraints(planner_model, loader.rules)
    add_meal_carb_rules(planner_model, loader.rules)
    add_carb_frequency_constraints(planner_model, loader.ingredients)
    add_recipe_frequency_constraints(planner_model, loader.rules)
    
    # 4. Solve
    solver = cp_model.CpSolver()
    solver.parameters.random_seed = seed
    
    status = solver.Solve(planner_model.model)
    
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assignments = {}
        for slot in planner_model.slots:
            slot_vars = planner_model.vars[slot.id]
            for variant in planner_model.variants:
                 if variant.variant_id in slot_vars:
                     if solver.Value(slot_vars[variant.variant_id]) == 1:
                         assignments[slot.id] = variant
                         break
                         
        return MealPlanSolution(assignments=assignments)
        
    else:
        raise RuntimeError("No feasible solution found")
