"""Recipe variant expansion."""

from typing import Optional
from pydantic import BaseModel

from .config import Recipe, CarbStrategy, IngredientKind, Ingredient


class RecipeVariant(BaseModel):
    """A specific variant of a recipe with a chosen carb option."""

    base_recipe_id: str
    variant_id: str
    recipe: Recipe
    carb_ingredient_id: Optional[str]  # None if no carb
    
    @property
    def is_carb_variant(self) -> bool:
        """Return True if this variant has a carb."""
        return self.carb_ingredient_id is not None


def expand_variants(
    recipes: dict[str, Recipe], ingredients: dict[str, Ingredient]
) -> list[RecipeVariant]:
    """Expand recipes into variants based on carb strategy.
    
    Returns a list of all possible recipe variants.
    """
    variants: list[RecipeVariant] = []

    for recipe_id, recipe in recipes.items():
        strategy = recipe.carbs.strategy
        
        if strategy == CarbStrategy.NONE:
            # Single variant: no carb
            variants.append(
                RecipeVariant(
                    base_recipe_id=recipe_id,
                    variant_id=f"{recipe_id}__carb_none",
                    recipe=recipe,
                    carb_ingredient_id=None,
                )
            )
            
        elif strategy == CarbStrategy.FIXED:
            # Single variant: fixed default carb
            carb_id = recipe.carbs.default
            if not carb_id:
                 # Should be caught by validation, but safe fallback
                 continue
                 
            variants.append(
                RecipeVariant(
                    base_recipe_id=recipe_id,
                    variant_id=f"{recipe_id}__carb_{carb_id}",
                    recipe=recipe,
                    carb_ingredient_id=carb_id,
                )
            )
            
        elif strategy == CarbStrategy.OPTIONAL:
            # Multiple variants: one for each allowed carb + one for no carb (if desired?)
            # Usually optional means "pick one of these". 
            # If "no carb" is also an option for an optional strategy, it should probably be explicit?
            # For now, let's assume optional means "must pick one from allowed".
            # If "none" is valid, it should be in allowed list? No, allowed is list of *ingredients*.
            # Based on Planning doc: "Meals with optional carbs are expanded into internal variants"
            
            # Let's create a variant for each allowed carb
            for carb_id in recipe.carbs.allowed:
                variants.append(
                    RecipeVariant(
                        base_recipe_id=recipe_id,
                        variant_id=f"{recipe_id}__carb_{carb_id}",
                        recipe=recipe,
                        carb_ingredient_id=carb_id,
                    )
                )

    return variants
