# Meal Planner – Iterative Build Instructions (AI Agent)

## Purpose

This document defines **how to build the Meal Planner in three structured iterations**, with a strong emphasis on:

- **Data-first modeling**
- **Rules-driven portions and meal constraints**
- **Hard constraints correctness**
- **Incremental solver complexity**
- **UI built last, against stable contracts**

You should treat this as the *authoritative implementation guide* for any AI agent or engineer working on the project.

The system goal is to generate **weekly meal plans** that strictly respect dietary and planning constraints, using **constraint programming (CP-SAT)**, deployed as a **static site via GitHub Pages**.

---

## Core Modeling Principles (IMPORTANT)

1. **All measurements are RAW (uncooked)** - simplifies shopping and preparation
2. **Recipes describe structure, not quantities**
3. **Portion sizes are global rules, not recipe-specific**
4. **Meal rules (e.g. no carbs at dinner) live in rules, not in recipes**
5. **Hard constraints are enforced in the solver, never approximated**
6. **If data + rules are valid but infeasible, the solver must fail**

This is a constraint system, not a suggestion engine.

---

# Iteration 1 — Data Model & Validation (NO SOLVER YET)

## Goal

Establish a **clean, validated, future-proof data model** that represents:

- meals and week structure
- proteins and global portion rules
- carbohydrates and their limits
- recipe structure and ingredient roles
- planning constraints (but not yet solved)

No planning logic yet. Only **data + validation + contracts**.

---

## Files to Create

Create only what is needed for a **data-first foundation**. Planner code exists only to **load + validate** data at this stage (no solver yet).

### Iteration 1 files (data + validation tooling)

```
data/
  rules.yml                 # week structure, meal_rules, protein portions, constraints
  ingredients.yml           # canonical ingredient IDs + metadata + kind (protein/carb/other) + optional restrictions
  pantry.yml                # ingredients to exclude from shopping list
  recipes/
    *.yml                   # recipe structure (primary_protein + carb strategy + ingredients)

planner/
  pyproject.toml            # pinned deps: pyyaml + pydantic (ortools NOT required yet)
  mealplanner/
    __init__.py
    config.py               # pydantic models for ALL YAML schemas
    load.py                 # load/normalize/validate YAML -> typed objects
  cli.py                    # `validate-data` command (and optional `dump-contracts`)
```

### Files explicitly deferred (do NOT create in Iteration 1)

These are created in later iterations once contracts are stable:

- **Iteration 2 (planner/solver + CI outputs):**
  - `planner/mealplanner/model.py`
  - `planner/mealplanner/solve.py`
  - `planner/mealplanner/variants.py` (optional: recipe carb-variant expansion helper)
  - `planner/mealplanner/shopping.py`
  - `planner/mealplanner/render.py` (writes `public/*`)
  - `.github/workflows/build_and_deploy.yml`
  - `public/` (generated)

- **Iteration 3 (UI):**
  - `site/*` (static UI sources)
  - any UI build tooling (only if needed)

---

## Data Model

### `data/ingredients.yml`
Canonical ingredient definitions. **This is the single source of truth** for:
- ingredient display/unit/section
- ingredient kind: `protein | carb | other`
- carb restrictions (e.g. max times per week, default serving qty)
- (optional) protein metadata (not portions; portions live in `rules.yml`)

```yaml
chicken:
  display: "Pollo"
  unit: g
  section: protein
  kind: protein

beef:
  display: "Carne de res"
  unit: g
  section: protein
  kind: protein

pork:
  display: "Cerdo"
  unit: g
  section: protein
  kind: protein

fish_salmon:
  display: "Salmón"
  unit: g
  section: protein
  kind: protein

egg:
  display: "Huevo"
  unit: units
  section: protein
  kind: protein

rice:
  display: "Arroz"
  unit: g
  section: carb
  kind: carb
  default_qty_g: 90
  max_times_week: 2

potato:
  display: "Papa"
  unit: g
  section: carb
  kind: carb
  default_qty_g: 120
  max_times_week: 2

platano_verde:
  display: "Plátano verde"
  unit: g
  section: carb
  kind: carb
  default_qty_g: 40
  max_times_week: 2

platano_maduro:
  display: "Plátano maduro"
  unit: g
  section: carb
  kind: carb
  default_qty_g: 45
  max_times_week: 0.5

yuca:
  display: "Yuca"
  unit: g
  section: carb
  kind: carb
  default_qty_g: 70
  max_times_week: 1

arepa:
  display: "Arepa de maíz"
  unit: units
  section: carb
  kind: carb
  default_qty_g: 0.5
  max_times_week: 1

corn:
  display: "Maíz tierno"
  unit: g
  section: carb
  kind: carb
  default_qty_g: 100
  max_times_week: 2

pasta:
  display: "Pasta"
  unit: g
  section: carb
  kind: carb
  default_qty_g: 100
  max_times_week: 1

lentils:
  display: "Lentejas"
  unit: g
  section: carb
  kind: carb
  default_qty_g: 60
  max_times_week: 1

lettuce:
  display: "Lechuga"
  unit: g
  section: veg
  kind: other

tomato:
  display: "Tomate"
  unit: g
  section: veg
  kind: other

olive_oil:
  display: "Aceite de oliva"
  unit: ml
  section: fat
  kind: other
```

Rules:
- **All measurements are RAW (uncooked)** for simplicity
- Ingredient IDs are canonical and lowercase with underscores (e.g., `fish_salmon`, `platano_verde`)
- Recipes MUST reference ingredients by ID only
- Only `kind: carb` ingredients may define `max_times_week` / `default_qty_g`
- Protein portion sizes are **not** stored here; they are configured in `rules.yml` (`protein_portions_g`)
- Carb serving quantities are resolved using `rules.yml` (`carb_portions_g`) first; `default_qty_g` in `ingredients.yml` is only a fallback/metadata
- Protein types: `chicken`, `beef`, `pork`, `fish`, `egg`
- 9 carb types: `rice`, `potato`, `platano_verde`, `platano_maduro`, `yuca`, `arepa`, `corn`, `pasta`, `lentils`

---

### `data/recipes/*.yml`

Recipes describe **structure**, not variable quantities.

```yaml
id: pollo_toscano_lunch
name: "Pollo toscano"
meal_types: [lunch]

tags:
  primary_protein: chicken

carbs:
  strategy: none | fixed | optional
  allowed: [rice, potato, yuca, platano_verde]   # ingredient IDs where kind==carb (only if optional)
  default: rice             # ingredient ID where kind==carb (only if fixed/optional)

ingredients:
  - item: chicken
    role: protein
    qty: "@portion"

  - item: spinach
    role: veg
    qty_g: 80

  - item: olive_oil
    role: fat
    qty_ml: 10
```

Rules:
- Exactly **one ingredient must have `role: protein`**
- `qty: "@portion"` is a sentinel meaning:
  > use global portion rules for this protein and meal
- Carb ingredients are **not hard-coded** here if `strategy != fixed`

---

### `data/rules.yml`

Defines global rules and constraints. **Portions are global and fixed** by meal type.

```yaml
week:
  days: [mon, tue, wed, thu, fri, sat, sun]
  meals: [breakfast, lunch, dinner]

meal_rules:
  breakfast:
    allow_carbs: true
  lunch:
    allow_carbs: true
  dinner:
    allow_carbs: false          # hard rule: dinner has NO carbs

# Global fixed portions by protein type and meal.
# These amounts do NOT vary per recipe.
# All measurements are RAW (uncooked)
protein_portions_g:
  chicken:
    breakfast: 170
    lunch: 210
    dinner: 140
  beef:
    breakfast: 190
    lunch: 230
    dinner: 230
  pork:
    lunch: 235
    dinner: 200
  fish:
    breakfast: 190
    lunch: 235
    dinner: 235
  egg:
    breakfast: 3  # units, not grams

# Global carb portions by meal (and optional overrides per carb id).
# Dinner is 0g (because allow_carbs=false), but keep it explicit for clarity.
# All measurements are RAW (uncooked)
carb_portions_g:
  breakfast_default: 90
  lunch_default: 90
  dinner_default: 0
  overrides:
    potato: 120
    yuca: 70
    platano_verde: 40
    platano_maduro: 45
    arepa: 0.5  # units (half arepa)
    lentils: 60
    pasta: 100
    corn: 100

constraints:
  # Weekly protein distribution (total across all meals)
  # Total: 21 meals (3 meals × 7 days)
  weekly_protein_counts:
    chicken: 10
    fish: 4
    beef: 3
    pork: 2
    egg: 2

  no_consecutive_same_protein: true

  fish_dinner_max_per_week: 2  # Total fish dinners per week
  fish_dinner_max_consecutive: 2  # Max consecutive days with fish at dinner
  
  max_recipe_uses_per_week: 1  # Each recipe can only be used once per week
```


---

## Validation Requirements (Iteration 1)

The following MUST be validated:

- Unique recipe IDs
- Exactly one primary protein per recipe
- Valid protein types: `chicken`, `beef`, `pork`, `fish`, `egg`
- Valid ingredient IDs (must exist in `ingredients.yml`)
- Valid carb strategies: `none`, `fixed`, `optional`
- Valid meal types: `breakfast`, `lunch`, `dinner`
- Carb ingredients in `allowed` list must have `kind: carb` in `ingredients.yml`
- No carb ingredients when recipe has `strategy: none`
- `@portion` only used on protein ingredient
- No unknown fields
- All measurements are for RAW ingredients

CLI command:

```bash
python -m planner.cli validate-data
```

Fail hard on error.

---

## Definition of Done (Iteration 1)

- All data validates successfully
- Schema is stable and documented
- Output JSON contracts are defined (even if stubbed)

---

# Iteration 2 — Planner & Hard Constraints (NO UI)

## Goal

Build the **constraint solver** that consumes Iteration-1 data and produces valid plans.

---

## Core Modeling Decisions

### Slots
- Slot = (day, meal)
- Exactly one recipe per slot

Recipes with optional carbs are **expanded into internal variants**:

```
chicken_bowl__carb_none
chicken_bowl__carb_rice
chicken_bowl__carb_potato
```

Each variant:
- maps to one base recipe
- has exactly one carb choice (or none)

---

## Hard Constraints (MANDATORY)

### 1. Weekly protein counts
Applies to all meals (breakfast + lunch + dinner).

```
Σ slots where primary_protein == chicken == rules.constraints.weekly_protein_counts.chicken
```

Total must equal 21 (3 meals × 7 days).

---

### 2. No same protein on consecutive days
Applied per meal type (dinner first).

For each protein `p`:

```
D[d,p] + D[d+1,p] ≤ 1
```

Where `D[d,p] = 1` if dinner on day d uses protein p.

---

### 3. Fish dinner: max per week
Limit total fish dinners per week:

```
Σ dinners where primary_protein == fish ≤ 2
```

---

### 4. Fish dinner: max 2 consecutive days
Allow:
- fish–fish
Disallow:
- fish–fish–fish

Sliding window constraint:

```
F[d] + F[d+1] + F[d+2] ≤ 2
```

Where `F[d] = 1` if dinner on day d is fish.

---

### 5. Meal carb rules
From `meal_rules`:

- Dinner slots MUST NOT select variants with carbs
- Lunch slots MAY select carb or no-carb variants

---

### 6. Carb frequency constraints
From `ingredients.yml` (only items with `kind: carb`):

```
Σ slots where carb == rice ≤ rice.max_times_week
```

---

### 7. Max once per week per base recipe

```
Σ variants of base_recipe R ≤ 1
```

This ensures variety in the meal plan.

---

## Portion Resolution (IMPORTANT)

### Protein portions
Protein quantities are resolved **after solving**, during shopping list generation:

For each slot:
- determine `primary_protein`
- lookup `rules.protein_portions_g[protein][meal]`
- substitute grams for `@portion` on the protein ingredient line

### Carb portions
Carb quantities are also resolved via global rules:

For each slot variant with a chosen carb `c`:
- if `meal_rules[meal].allow_carbs == false` then `carb = none` (enforced as a hard constraint)
- otherwise:
  - use `rules.carb_portions_g.overrides[c]` if present
  - else use `rules.carb_portions_g.<meal>_default` (typically lunch_default)
- add that carb quantity to the shopping list (carb can be represented as a synthetic ingredient line, not necessarily present in recipe ingredients)

---

## Outputs

### `public/plan.json`

```json
{
  "seed": 123,
  "slots": [
    {
      "day": "mon",
      "meal": "dinner",
      "recipeId": "steak_salad",
      "carb": "none"
    }
  ],
  "derived": {
    "protein_counts": { "meat": 2 },
    "carb_counts": { "rice": 2 }
  }
}
```

### `public/shopping_list.json`
Aggregated ingredients with resolved quantities, pantry excluded.

---

## Definition of Done (Iteration 2)

- CI generates plan + shopping list
- All hard constraints enforced
- Infeasible data causes CI failure with explanation
- Deterministic output with seed

---

# Iteration 3 — UI & Planning Workflow

## Goal

Make the system usable by non-technical users.

---

## Scope

### UI
- Weekly grid (B/L/D)
- Recipe detail (ingredients + steps)
- Shopping list grouped by section
- Constraint summary panel

### Steering
- `data/locks.yml` to lock slots to recipes
- Locks treated as hard constraints

### Explainability
- Surface active constraints
- Diagnostics artifact on infeasibility

---

## Definition of Done (Iteration 3)

- Locked meals respected
- Regeneration via CI manual dispatch
- Clear feedback on why plans succeed or fail

---

## Final Rule

If a choice must be made between:
- convenience
- correctness

Always choose correctness.

---

# Implementation Summary

## Data Files Created

The following data files have been implemented based on the Excel template:

### Core Configuration Files
- **`data/rules.yml`**: Week structure, meal rules, protein/carb portions, and constraints
- **`data/ingredients.yml`**: 60+ canonical ingredients organized by category
- **`data/pantry.yml`**: Staple ingredients to exclude from shopping lists

### Recipe Files (19 total)
All recipes from Excel data (R001-R014) have been implemented:

1. `pollo_toscano_lunch.yml` - Pollo toscano (optional carbs)
2. `pollo_guiso_habichuelas_dinner.yml` - Pollo con guiso (no carbs)
3. `pollo_asiatico_lunch.yml` - Pollo asiático (optional carbs)
4. `pollo_asiatico_dinner.yml` - Pollo asiático (no carbs)
5. `arroz_con_pollo.yml` - Arroz con pollo (fixed: rice)
6. `chicken_fricassee_lunch.yml` - Chicken Fricassée (optional carbs)
7. `chicken_fricassee_dinner.yml` - Chicken Fricassée (no carbs)
8. `atun_juanfe_lunch.yml` - Atún a la JuanFe (optional carbs)
9. `atun_juanfe_dinner.yml` - Atún a la JuanFe (no carbs)
10. `salmon_horneado_lunch.yml` - Salmón horneado (optional carbs)
11. `salmon_horneado_dinner.yml` - Salmón horneado (no carbs)
12. `arroz_salteado_cerdo.yml` - Arroz salteado con cerdo (fixed: rice)
13. `carne_encebollada_lunch.yml` - Carne encebollada (optional carbs)
14. `carne_encebollada_breakfast.yml` - Carne encebollada (no carbs)
15. `sudado_carne.yml` - Sudado de carne (fixed: potato)
16. `lentejas.yml` - Lentejas (fixed: lentils)
17. `atun_guisito_dinner.yml` - Atún con guisito (no carbs)
18. `pasta_tefy.yml` - Pasta Tefy (fixed: pasta)
19. `pescado_encocado.yml` - Pescado encocado (optional carbs)

## Key Data Model Decisions

### 1. All Measurements Are RAW
- Simplifies shopping (buy exactly what's listed)
- Simplifies meal prep (no conversion needed)
- Consistent across all ingredients

### 2. Three Meal Types
- **Breakfast**: Allows carbs
- **Lunch**: Allows carbs
- **Dinner**: NO carbs (hard constraint)

### 3. Five Protein Types
- `chicken`: 10 meals/week
- `fish`: 4 meals/week
- `beef`: 3 meals/week
- `pork`: 2 meals/week
- `egg`: 2 meals/week
- **Total**: 21 meals (3 meals × 7 days)

### 4. Nine Carb Types
All with frequency limits:
- `rice`: max 2/week, 90g default
- `potato`: max 2/week, 120g
- `platano_verde`: max 2/week, 40g
- `platano_maduro`: max 0.5/week, 45g
- `yuca`: max 1/week, 70g
- `arepa`: max 1/week, 0.5 units
- `corn`: max 2/week, 100g
- `pasta`: max 1/week, 100g
- `lentils`: max 1/week, 60g

### 5. Recipe Variants for Meal-Specific Carb Rules
Instead of conditional logic, recipes with different carb strategies for different meals are split into separate files:
- `pollo_asiatico_lunch.yml` (optional carbs)
- `pollo_asiatico_dinner.yml` (no carbs)

This makes the solver logic simpler and constraints clearer.

### 6. Seven Hard Constraints
1. Weekly protein counts (must total 21)
2. No consecutive same protein
3. Fish dinner max 2 per week
4. Fish dinner max 2 consecutive days
5. Meal carb rules (no carbs at dinner)
6. Carb frequency limits
7. Max once per week per recipe

## Next Steps (Iteration 2)

With the data model complete and validated, the next iteration will:
1. Create Pydantic models in `planner/mealplanner/config.py`
2. Implement data loading/validation in `planner/mealplanner/load.py`
3. Build the CP-SAT solver in `planner/mealplanner/solve.py`
4. Generate shopping lists in `planner/mealplanner/shopping.py`
5. Set up CI/CD pipeline for automated plan generation
