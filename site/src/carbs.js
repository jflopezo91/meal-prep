// Carb names and choices. Shared by the read-only views (week cards, stats) and the editing UI, so it
// imports nothing from editing/ and stays in the static (Pages) build.

// Display names from data/ingredients.yml, for places that only have the carb id.
export const CARB_NAMES = {
  rice: 'Arroz',
  potato: 'Papa',
  yuca: 'Yuca',
  platano_verde: 'Plátano verde',
  platano_maduro: 'Plátano maduro',
  arepa: 'Arepa de maíz',
  corn: 'Maíz tierno',
  pasta: 'Pasta',
  lentils: 'Lentejas',
};

// The order carbs are offered in; unknown ids go last, alphabetically.
const ORDER = Object.keys(CARB_NAMES);

export function carbLabel(carb) {
  if (!carb || carb === 'none') return 'No carb';
  const name = CARB_NAMES[carb] ?? carb.replace(/_/g, ' ');
  return name.charAt(0).toUpperCase() + name.slice(1);
}

// The name a slot shows for its carb: its carb ingredient row when present, else the id's name.
export function slotCarbName(slot) {
  const row = slot?.ingredients?.find(ingredient => ingredient.role === 'carb');
  return row?.display ?? carbLabel(slot?.carb);
}

export function compareCarbs(a, b) {
  const rank = carb => { const index = ORDER.indexOf(carb); return index === -1 ? ORDER.length : index; };
  return rank(a) - rank(b) || String(a).localeCompare(String(b));
}

// Whether a catalog variant fits a meal: a lunch always has a carb, a dinner never does.
export function fitsMeal(variant, meal) {
  return meal === 'lunch' ? variant.carb != null : variant.carb == null;
}

// recipe_id -> its lunch carb ids in offer order, from the catalog variants.
export function lunchCarbsByRecipe(variants) {
  const byRecipe = new Map();
  for (const variant of variants ?? []) {
    if (!fitsMeal(variant, 'lunch')) continue;
    if (!byRecipe.has(variant.recipe_id)) byRecipe.set(variant.recipe_id, []);
    byRecipe.get(variant.recipe_id).push(variant.carb);
  }
  for (const carbs of byRecipe.values()) carbs.sort(compareCarbs);
  return byRecipe;
}
