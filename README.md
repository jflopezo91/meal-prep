# Meal Prep Planner

An automated meal planning system that generates optimal weekly menus based on nutritional constraints, ingredient availability, and variety rules. It includes a modern web interface for viewing your plan and shopping list.

## Features

-   **Constraint-Based Planning**: Uses Google OR-Tools to ensure nutritional balance (protein targets, carb limits) and variety (no consecutive proteins, recipe repetition limits).
-   **Data-First Configuration**: Define everything in YAML (`data/recipes/*.yml`, `data/ingredients.yml`, `data/rules.yml`).
-   **Automated Shopping List**: Aggregates ingredients from the generated plan, grouping them by category (Protein, Produce, Pantry, etc.).
-   **Modern UI**: A responsive React + Tailwind CSS web application to view your weekly schedule and check off grocery items.
-   **Dark Mode**: Sleek Slate-900 based dark theme with persistent user preference.
-   **Flexible**: Supports fixed vs. optional carbs and custom dietary rules.

## Prerequisites

-   **Python 3.10+** (for the planner)
-   **Node.js 18+** (for the UI)

## Installation

### 1. Setup the Planner (Python)
```bash
# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e planner
```

### 2. Setup the UI (React)
```bash
cd site
npm install
cd ..
```

## Workflow: How to Generate a Weekly Plan

### Step 1: Generate the Plan
Run the planner command to solve for a new week. This will write the data directly to the UI's public folder.

```bash
# Generate a plan using a seed for reproducibility
.venv/bin/mealplanner generate-plan data site/public --seed 123
```

This command will:
1.  Read configuration from `data/`.
2.  Solve for a valid schedule satisfying all rules in `data/rules.yml`.
3.  Output `plan.json` and `shopping_list.json` directly to `site/public/`.

### Step 2: View the Plan
Start the local development server to view your meal plan and shopping list.

```bash
cd site
npm run dev
```
Open the URL shown (usually `http://localhost:5173`) in your browser.

## Configuration

-   **`data/rules.yml`**: Define global constraints (e.g., "no carbs at dinner", protein targets per week).
-   **`data/ingredients.yml`**: Master list of ingredients with units and categories.
-   **`data/pantry.yml`**: Items you already have (excluded from shopping list).
-   **`data/recipes/*.yml`**: Individual recipe definitions (ingredients, tags, meal types).

## Troubleshooting

-   **Optimization Failed**: If the solver cannot find a solution, try relaxing constraints in `data/rules.yml` (e.g., increase `max_recipe_uses_per_week` or `fish_dinner_max_per_week`).
-   **UI Not Updating**: Ensure you pointed the `generate-plan` command to `site/public` correctly in Step 1.