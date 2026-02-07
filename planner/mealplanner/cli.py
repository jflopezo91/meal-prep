"""Command-line interface for meal planner."""

import sys
import json
from pathlib import Path

from .load import load_data
from .solve import solve_plan
from .shopping import generate_shopping_list
from .render import render_plan


def validate_data(data_dir: Path) -> int:
    """Validate all data files."""
    try:
        print(f"Loading data from {data_dir}...")
        loader = load_data(data_dir)

        print(f"✓ Loaded {len(loader.ingredients)} ingredients")
        print(f"✓ Loaded {len(loader.recipes)} recipes")
        print(f"✓ Loaded rules with {len(loader.rules.week.days)} days, {len(loader.rules.week.meals)} meals")
        print(f"✓ Loaded {len(loader.pantry)} pantry items")
        print("\n✓ All validation passed!")
        return 0

    except Exception as e:
        print(f"\n✗ Validation failed: {e}", file=sys.stderr)
        return 1


def generate_plan(data_dir: Path, output_dir: Path, seed: int) -> int:
    """Generate plan and shopping list."""
    try:
        # 1. Load data
        print(f"Loading data from {data_dir}...")
        loader = load_data(data_dir)
        
        # 2. Solve
        print(f"Generating plan with seed {seed}...")
        solution = solve_plan(loader, seed)
        print("✓ Solution found!")
        
        # 3. Generate shopping list
        print("Generating shopping list...")
        shopping_list = generate_shopping_list(solution, loader)
        
        # 4. Render output
        print(f"Rendering output to {output_dir}...")
        render_plan(solution, loader, seed, output_dir)
        
        # Write shopping list
        with open(output_dir / "shopping_list.json", "w") as f:
            f.write(shopping_list.model_dump_json(indent=2))
        print(f"✓ Wrote shopping_list.json to {output_dir}")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Plan generation failed: {e}", file=sys.stderr)
        return 1


def main() -> None:
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: mealplanner <command> [args]")
        print("\nCommands:")
        print("  validate-data <data_dir>")
        print("  generate-plan <data_dir> <output_dir> [--seed SEED]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "validate-data":
        if len(sys.argv) < 3:
            print("Usage: mealplanner validate-data <data_dir>")
            sys.exit(1)
        data_dir = Path(sys.argv[2])
        sys.exit(validate_data(data_dir))

    elif command == "generate-plan":
        if len(sys.argv) < 4:
            print("Usage: mealplanner generate-plan <data_dir> <output_dir> [--seed SEED]")
            sys.exit(1)
            
        data_dir = Path(sys.argv[2])
        output_dir = Path(sys.argv[3])
        
        seed = 42
        if "--seed" in sys.argv:
            idx = sys.argv.index("--seed")
            if idx + 1 < len(sys.argv):
                seed = int(sys.argv[idx + 1])
                
        sys.exit(generate_plan(data_dir, output_dir, seed))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
