"""Pydantic models for YAML configuration schemas."""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, RootModel


# ============================================================================
# Enums
# ============================================================================


class ProteinType(str, Enum):
    """Valid protein types."""

    CHICKEN = "chicken"
    BEEF = "beef"
    PORK = "pork"
    FISH = "fish"
    EGG = "egg"


class MealType(str, Enum):
    """Valid meal types."""

    LUNCH = "lunch"
    DINNER = "dinner"


class IngredientKind(str, Enum):
    """Ingredient classification."""

    PROTEIN = "protein"
    CARB = "carb"
    OTHER = "other"


class CarbStrategy(str, Enum):
    """Recipe carb strategy."""

    NONE = "none"
    FIXED = "fixed"
    OPTIONAL = "optional"


# ============================================================================
# Ingredient Models
# ============================================================================


class Ingredient(BaseModel):
    """Ingredient definition from ingredients.yml."""

    display: str
    unit: str
    section: str
    kind: IngredientKind
    default_qty_g: Optional[float] = None
    max_times_week: Optional[float] = None
    notes: Optional[str] = None

    @field_validator("max_times_week", "default_qty_g")
    @classmethod
    def carb_fields_only_for_carbs(cls, v: Optional[float], info) -> Optional[float]:
        """Validate that carb-specific fields are only set for carbs."""
        if v is not None and info.data.get("kind") != IngredientKind.CARB:
            raise ValueError(f"{info.field_name} can only be set for carb ingredients")
        return v


class IngredientsConfig(RootModel):
    """Root model for ingredients.yml."""

    root: dict[str, Ingredient]


# ============================================================================
# Recipe Models
# ============================================================================


class RecipeIngredient(BaseModel):
    """Individual ingredient in a recipe."""

    item: str  # Ingredient ID
    role: str
    qty: Optional[str] = None  # "@portion" for protein
    qty_g: Optional[float] = None
    qty_ml: Optional[float] = None
    qty_units: Optional[float] = None
    notes: Optional[str] = None
    optional: bool = False

    @field_validator("qty")
    @classmethod
    def validate_portion_sentinel(cls, v: Optional[str]) -> Optional[str]:
        """Validate @portion sentinel."""
        if v is not None and v != "@portion":
            raise ValueError("qty field must be '@portion' or None")
        return v


class RecipeTags(BaseModel):
    """Recipe tags."""

    primary_protein: ProteinType


class RecipeCarbs(BaseModel):
    """Recipe carb configuration."""

    strategy: CarbStrategy
    allowed: list[str] = Field(default_factory=list)  # Carb ingredient IDs
    default: Optional[str] = None  # Carb ingredient ID

    @field_validator("allowed")
    @classmethod
    def allowed_only_for_optional(cls, v: list[str], info) -> list[str]:
        """Validate allowed is only set for optional strategy."""
        if v and info.data.get("strategy") != CarbStrategy.OPTIONAL:
            raise ValueError("allowed can only be set for optional strategy")
        return v

    @field_validator("default")
    @classmethod
    def default_for_fixed_or_optional(cls, v: Optional[str], info) -> Optional[str]:
        """Validate default is set for fixed/optional strategies."""
        strategy = info.data.get("strategy")
        if strategy in (CarbStrategy.FIXED, CarbStrategy.OPTIONAL) and not v:
            raise ValueError(f"default must be set for {strategy} strategy")
        if strategy == CarbStrategy.NONE and v:
            raise ValueError("default cannot be set for none strategy")
        return v


class Recipe(BaseModel):
    """Recipe definition from recipes/*.yml."""

    id: str
    name: str
    meal_types: list[MealType]
    tags: RecipeTags
    carbs: RecipeCarbs
    ingredients: list[RecipeIngredient]
    notes: Optional[str] = None

    @field_validator("ingredients")
    @classmethod
    def exactly_one_protein(cls, v: list[RecipeIngredient]) -> list[RecipeIngredient]:
        """Validate exactly one protein ingredient with @portion."""
        protein_count = sum(1 for ing in v if ing.qty == "@portion")
        if protein_count != 1:
            raise ValueError(f"Recipe must have exactly one protein with qty='@portion', found {protein_count}")
        return v


# ============================================================================
# Rules Models
# ============================================================================


class WeekConfig(BaseModel):
    """Week structure."""

    days: list[str]
    meals: list[MealType]


class MealRules(BaseModel):
    """Meal-specific rules."""

    allow_carbs: bool


class ProteinPortions(BaseModel):
    """Protein portions by meal type."""

    lunch: Optional[float] = None
    dinner: Optional[float] = None


class CarbPortions(BaseModel):
    """Carb portion configuration."""

    lunch_default: float
    dinner_default: float
    overrides: dict[str, float] = Field(default_factory=dict)


class Constraints(BaseModel):
    """Planning constraints."""

    weekly_protein_counts: dict[ProteinType, int]
    no_consecutive_same_protein: bool
    fish_dinner_max_per_week: int
    fish_dinner_max_consecutive: int
    max_recipe_uses_per_week: int


class Rules(BaseModel):
    """Root model for rules.yml."""

    week: WeekConfig
    meal_rules: dict[MealType, MealRules]
    protein_portions_g: dict[ProteinType, ProteinPortions]
    carb_portions_g: CarbPortions
    constraints: Constraints




# ============================================================================
# Pantry Model
# ============================================================================


class PantryConfig(RootModel):
    """Root model for pantry.yml (list of ingredient IDs)."""

    root: list[str]
