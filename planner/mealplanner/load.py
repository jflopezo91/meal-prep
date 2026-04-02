"""Data loading and validation module."""

from pathlib import Path
from typing import Any

import yaml

from .config import (
    Ingredient,
    IngredientsConfig,
    MealType,
    Recipe,
    Rules,
    PantryConfig,
    ProteinType,
    IngredientKind,
)


class DataLoader:
    """Loads and validates YAML configuration files."""

    def __init__(self, data_dir: Path):
        """Initialize with data directory path."""
        self.data_dir = data_dir
        self.ingredients: dict[str, Ingredient] = {}
        self.recipes: dict[str, Recipe] = {}
        self.rules: Rules | None = None
        self.pantry: list[str] = []

    def load_all(self) -> None:
        """Load and validate all configuration files."""
        self.load_ingredients()
        self.load_rules()
        self.load_pantry()
        self.load_recipes()
        self.cross_validate()

    def load_ingredients(self) -> None:
        """Load ingredients.yml."""
        path = self.data_dir / "ingredients.yml"
        with open(path) as f:
            data = yaml.safe_load(f)

        # Validate each ingredient
        self.ingredients = {}
        for ing_id, ing_data in data.items():
            self.ingredients[ing_id] = Ingredient(**ing_data)

    def load_rules(self) -> None:
        """Load rules.yml."""
        path = self.data_dir / "rules.yml"
        with open(path) as f:
            data = yaml.safe_load(f)

        self.rules = Rules(**data)

        # Validate protein counts sum to total meals
        total_meals = len(self.rules.week.days) * len(self.rules.week.meals)
        protein_sum = sum(self.rules.constraints.weekly_protein_counts.values())
        if protein_sum != total_meals:
            raise ValueError(
                f"Protein counts sum to {protein_sum} but should equal "
                f"{total_meals} ({len(self.rules.week.days)} days × "
                f"{len(self.rules.week.meals)} meals)"
            )

    def load_pantry(self) -> None:
        """Load pantry.yml."""
        path = self.data_dir / "pantry.yml"
        with open(path) as f:
            data = yaml.safe_load(f)

        self.pantry = data if isinstance(data, list) else []

    def load_recipes(self) -> None:
        """Load all recipe files from recipes/ directory."""
        recipes_dir = self.data_dir / "recipes"
        if not recipes_dir.exists():
            raise FileNotFoundError(f"Recipes directory not found: {recipes_dir}")

        self.recipes = {}
        for recipe_file in recipes_dir.glob("*.yml"):
            recipe = self.load_recipe_file(recipe_file)

            # Check for duplicate IDs
            if recipe.id in self.recipes:
                raise ValueError(f"Duplicate recipe ID: {recipe.id}")

            self.recipes[recipe.id] = recipe

    def load_recipe_file(self, recipe_file: Path) -> Recipe:
        """Load and schema-validate a single recipe file."""
        with open(recipe_file) as f:
            data = yaml.safe_load(f)

        recipe = Recipe(**data)
        self.validate_recipe_filename(recipe_file, recipe)
        return recipe

    def validate_recipe_filename(self, recipe_file: Path, recipe: Recipe) -> None:
        """Validate filename conventions for contributor-submitted recipes."""
        if recipe_file.suffix != ".yml":
            raise ValueError(f"Recipe {recipe.id}: file must use .yml extension")

        if recipe_file.stem != recipe.id:
            raise ValueError(
                f"Recipe {recipe.id}: filename '{recipe_file.name}' must match id '{recipe.id}.yml'"
            )

    def cross_validate(self) -> None:
        """Cross-validate references between files."""
        if not self.rules:
            raise ValueError("Rules must be loaded before cross-validation")

        # Validate pantry ingredient IDs
        for ing_id in self.pantry:
            if ing_id not in self.ingredients:
                raise ValueError(f"Pantry references unknown ingredient: {ing_id}")

        # Validate recipes
        for recipe_id, recipe in self.recipes.items():
            self.validate_recipe(recipe_id, recipe)

    def validate_recipe(self, recipe_id: str, recipe: Recipe) -> None:
        """Validate a single recipe against loaded ingredients and rules."""
        if not self.rules:
            raise ValueError("Rules must be loaded before recipe validation")

        # Validate ingredient references
        for ing in recipe.ingredients:
            if ing.item not in self.ingredients:
                raise ValueError(
                    f"Recipe {recipe_id} references unknown ingredient: {ing.item}"
                )

            # Validate @portion is only on protein
            if ing.qty == "@portion":
                ingredient = self.ingredients[ing.item]
                if ingredient.kind != IngredientKind.PROTEIN:
                    raise ValueError(
                        f"Recipe {recipe_id}: @portion can only be used on protein "
                        f"ingredients, but {ing.item} is {ingredient.kind}"
                    )

        # Validate carb strategy
        if recipe.carbs.strategy.value == "none":
            # No carbs allowed
            if recipe.carbs.allowed or recipe.carbs.default:
                raise ValueError(
                    f"Recipe {recipe_id}: strategy 'none' cannot have allowed or default carbs"
                )
        elif recipe.carbs.strategy.value == "fixed":
            # Must have default carb
            if not recipe.carbs.default:
                raise ValueError(
                    f"Recipe {recipe_id}: strategy 'fixed' requires default carb"
                )
            # Validate default is a carb
            if recipe.carbs.default not in self.ingredients:
                raise ValueError(
                    f"Recipe {recipe_id}: default carb {recipe.carbs.default} not found"
                )
            if self.ingredients[recipe.carbs.default].kind != IngredientKind.CARB:
                raise ValueError(
                    f"Recipe {recipe_id}: default {recipe.carbs.default} is not a carb"
                )
        elif recipe.carbs.strategy.value == "optional":
            # Must have allowed list and default
            if not recipe.carbs.allowed:
                raise ValueError(
                    f"Recipe {recipe_id}: strategy 'optional' requires allowed carbs list"
                )
            if not recipe.carbs.default:
                raise ValueError(
                    f"Recipe {recipe_id}: strategy 'optional' requires default carb"
                )
            # Validate all allowed are carbs
            for carb_id in recipe.carbs.allowed:
                if carb_id not in self.ingredients:
                    raise ValueError(
                        f"Recipe {recipe_id}: allowed carb {carb_id} not found"
                    )
                if self.ingredients[carb_id].kind != IngredientKind.CARB:
                    raise ValueError(
                        f"Recipe {recipe_id}: allowed {carb_id} is not a carb"
                    )
            # Validate default is in allowed
            if recipe.carbs.default not in recipe.carbs.allowed:
                raise ValueError(
                    f"Recipe {recipe_id}: default carb must be in allowed list"
                )

        # Validate protein portions exist
        protein_type = recipe.tags.primary_protein
        if protein_type not in self.rules.protein_portions_g:
            raise ValueError(
                f"Recipe {recipe_id}: protein type {protein_type.value} not found in rules"
            )

        # Validate protein portions for allowed meals
        portions = self.rules.protein_portions_g[protein_type]
        for meal_type in recipe.meal_types:
            portion_value = getattr(portions, meal_type.value, None)
            if portion_value is None:
                raise ValueError(
                    f"Recipe {recipe_id}: no portion defined for {protein_type.value} "
                    f"at {meal_type.value}"
                )

        # Validate extend_to_dinner flag
        if recipe.extend_to_dinner:
            if (
                MealType.LUNCH not in recipe.meal_types
                or MealType.DINNER not in recipe.meal_types
            ):
                raise ValueError(
                    f"Recipe {recipe_id}: extend_to_dinner requires both lunch and "
                    "dinner in meal_types"
                )


def infer_data_dir(recipe_file: Path) -> Path:
    """Infer the data directory for a recipe file from its location."""
    candidate_dirs = [recipe_file.parent.parent, recipe_file.parent]
    for candidate in candidate_dirs:
        if (candidate / "ingredients.yml").exists() and (candidate / "rules.yml").exists():
            return candidate
    raise FileNotFoundError(
        f"Could not infer data directory for recipe file: {recipe_file}"
    )


def validate_recipe_file(
    recipe_file: Path | str, data_dir: Path | str | None = None
) -> tuple[DataLoader, Recipe]:
    """Load and validate a single recipe file against the shared data definitions."""
    recipe_path = Path(recipe_file)
    resolved_data_dir = infer_data_dir(recipe_path) if data_dir is None else Path(data_dir)

    loader = DataLoader(resolved_data_dir)
    loader.load_ingredients()
    loader.load_rules()
    loader.load_pantry()

    recipe = loader.load_recipe_file(recipe_path)
    loader.validate_recipe(recipe.id, recipe)
    return loader, recipe


def load_data(data_dir: Path | str) -> DataLoader:
    """Load and validate all data files.

    Args:
        data_dir: Path to data directory

    Returns:
        DataLoader instance with loaded data

    Raises:
        ValueError: If validation fails
        FileNotFoundError: If required files are missing
    """
    if isinstance(data_dir, str):
        data_dir = Path(data_dir)

    loader = DataLoader(data_dir)
    loader.load_all()
    return loader
