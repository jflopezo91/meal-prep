from pathlib import Path

import pytest
import yaml

from mealplanner.load import load_data, validate_recipe_file


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


def test_validate_data_passes_for_repo_data() -> None:
    loader = load_data(DATA_DIR)

    assert loader.recipes
    assert loader.ingredients
    assert loader.rules is not None


def test_validate_recipe_file_accepts_valid_recipe() -> None:
    recipe_path = DATA_DIR / "recipes" / "pollo_asiatico.yml"

    loader, recipe = validate_recipe_file(recipe_path)

    assert loader.data_dir == DATA_DIR
    assert recipe.id == "pollo_asiatico"


def test_validate_recipe_file_rejects_filename_mismatch(tmp_path: Path) -> None:
    source_path = DATA_DIR / "recipes" / "pollo_asiatico.yml"
    bad_path = tmp_path / "bad_name.yml"
    bad_path.write_text(source_path.read_text())

    with pytest.raises(ValueError, match="filename 'bad_name.yml' must match id"):
        validate_recipe_file(bad_path, DATA_DIR)


def test_validate_recipe_file_rejects_invalid_role(tmp_path: Path) -> None:
    source_path = DATA_DIR / "recipes" / "pollo_asiatico.yml"
    recipe_data = yaml.safe_load(source_path.read_text())
    recipe_data["ingredients"][0]["role"] = "unknown_role"

    bad_path = tmp_path / "pollo_asiatico.yml"
    bad_path.write_text(yaml.safe_dump(recipe_data, sort_keys=False))

    with pytest.raises(ValueError, match="role must be one of"):
        validate_recipe_file(bad_path, DATA_DIR)


def test_validate_recipe_file_rejects_multiple_quantity_fields(tmp_path: Path) -> None:
    source_path = DATA_DIR / "recipes" / "pollo_asiatico.yml"
    recipe_data = yaml.safe_load(source_path.read_text())
    recipe_data["ingredients"][0]["qty_g"] = 200

    bad_path = tmp_path / "pollo_asiatico.yml"
    bad_path.write_text(yaml.safe_dump(recipe_data, sort_keys=False))

    with pytest.raises(ValueError, match="exactly one of qty, qty_g, qty_ml, or qty_units"):
        validate_recipe_file(bad_path, DATA_DIR)
