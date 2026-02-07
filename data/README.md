# Data Directory Structure

This directory contains all the configuration and recipe data for the meal planner.

## Overview

All measurements are for **RAW (uncooked) ingredients** unless otherwise specified.

## Files

### `rules.yml`
Global planning rules and constraints:
- **Week structure**: 7 days, 3 meals (breakfast, lunch, dinner)
- **Meal rules**: Carb policies per meal type
- **Protein portions**: Fixed portions by protein type and meal (in grams, raw)
- **Carb portions**: Fixed portions by meal with specific overrides (in grams, raw)
- **Constraints**: Weekly protein distribution, consecutive protein rules, fish limits, recipe frequency

### `ingredients.yml`
Canonical ingredient definitions (single source of truth):
- **Ingredient ID**: Lowercase canonical identifier (e.g., `chicken`, `rice`, `platano_verde`)
- **Display name**: Human-readable name in Spanish
- **Unit**: g, ml, or units
- **Section**: protein, carb, vegetable, dairy, fat, condiment, spice, other
- **Kind**: `protein`, `carb`, or `other`
- **Carb-specific fields**:
  - `default_qty_g`: Default serving size
  - `max_times_week`: Maximum weekly frequency

### `pantry.yml`
List of staple ingredients to exclude from shopping lists (always in stock).

### `recipes/*.yml`
Individual recipe definitions:
- **id**: Unique recipe identifier
- **name**: Display name
- **meal_types**: Allowed meals (breakfast, lunch, dinner)
- **tags.primary_protein**: Protein type (chicken, beef, pork, fish, egg)
- **carbs.strategy**: `none`, `fixed`, or `optional`
  - `none`: No carbs (typically for dinner)
  - `fixed`: Always includes a specific carb
  - `optional`: Solver chooses from allowed carbs
- **ingredients**: List with roles (protein, veg, fat, etc.)
  - Use `qty: "@portion"` for protein to resolve at planning time
  - Use `qty_g`, `qty_ml`, or `qty_units` for fixed quantities

## Recipe Naming Convention

For recipes that can be used at multiple meals with different carb strategies:
- Create **separate recipe files** for each variant
- Naming: `{recipe_name}_{meal_type}.yml`
- Examples:
  - `pollo_asiatico_lunch.yml` (with optional carbs)
  - `pollo_asiatico_dinner.yml` (no carbs)

## Current Recipes

Based on Excel data (R001-R014):

1. **pollo_toscano_lunch.yml** - Pollo toscano (optional carbs)
2. **pollo_guiso_habichuelas_dinner.yml** - Pollo con guiso (no carbs)
3. **pollo_asiatico_lunch.yml** - Pollo asiático (optional carbs)
4. **pollo_asiatico_dinner.yml** - Pollo asiático (no carbs)
5. **arroz_con_pollo.yml** - Arroz con pollo (fixed: rice)
6. **salmon_horneado_lunch.yml** - Salmón horneado (optional carbs)
7. **salmon_horneado_dinner.yml** - Salmón horneado (no carbs)

## TODO: Remaining Recipes to Create

From your Excel data (R006-R014):
- R006: Atún a la JuanFe (lunch/dinner variants)
- R008: Arroz salteado con cerdo (lunch, fixed rice)
- R009: Carne encebollada (lunch/breakfast variants)
- R010: Sudado de carne (lunch, fixed potato)
- R011: Lentejas (lunch, fixed lentils)
- R012: Atún con guisito (dinner, no carbs)
- R013: Pasta Tefy (lunch, fixed pasta)
- R014: Pescado encocado (lunch, optional carbs)
- R004: Chicken Fricassée (lunch/dinner variants)

## Key Design Decisions

1. **All measurements are RAW**: Simplifies shopping and preparation
2. **Separate files for meal variants**: Clearer than conditional logic
3. **Protein portions resolved at planning time**: Using `@portion` sentinel
4. **Carb portions from global rules**: Consistent across all recipes
5. **Canonical ingredient IDs**: Lowercase with underscores for consistency

## Validation

Before running the planner, validate the data structure:

```bash
python -m planner.cli validate-data
```

This will check:
- Unique recipe IDs
- Valid ingredient references
- Correct carb strategies
- Protein portion rules
- Constraint consistency
