import test from 'node:test';
import assert from 'node:assert/strict';
import { createPlanEditor } from '../src/editing/planEditor.js';
import { lunchCarbsByRecipe, slotCarbName, fitsMeal } from '../src/carbs.js';
import { filterVariants, proteinOptions, groupRecipes, defaultVariant, carbLabel, carbSummary, changeLabels, canSwapSlot, groupGroceryDelta, formatDifference, tripImpactMessage, tripImpactMessages, replacedSwapsWarning, swapErrorMessage, swapNeedsReload } from '../src/editing/swapModel.js';

const json = (body, status = 200, headers = {}) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json', ...headers } });
function mockFetch(handler) {
  const original = globalThis.fetch; const calls = [];
  globalThis.fetch = async (input, init = {}) => {
    const call = { url: new URL(input), method: init.method, headers: init.headers, body: init.body ? JSON.parse(init.body) : undefined };
    calls.push(call); return handler(call, calls.length);
  };
  return { calls, restore: () => { globalThis.fetch = original; } };
}
const err = (code, status) => json({ error: { code, message: code, details: [] } }, status);
const swap = { slotId: 'slot_2026-10-21_lunch', variantId: 'pollo__carb_rice', scope: 'pair', expectedRevision: 2 };
const plan = { plan_id: 'plan_2026_10_19', revision: 3 };

test('getCatalogVariants returns items', async () => {
  const mock = mockFetch(() => json({ items: [{ recipe_id: 'a', variant_id: 'a__b', name: 'A', protein: 'fish', carb: null }] }));
  try {
    const items = await createPlanEditor().getCatalogVariants();
    assert.equal(items.length, 1);
    assert.equal(mock.calls[0].url.pathname, '/api/v1/catalog/variants');
    assert.equal(mock.calls[0].method, 'GET');
  } finally { mock.restore(); }
  const bad = mockFetch(() => json({}));
  try { await assert.rejects(createPlanEditor().getCatalogVariants(), { code: 'source_invalid' }); } finally { bad.restore(); }
});

test('previewSwap posts the documented body without an idempotency key', async () => {
  const preview = { plan_id: plan.plan_id, base_revision: 2, changes: [], grocery_delta: [], rule_warnings: [], trip: null };
  const mock = mockFetch(() => json(preview));
  try {
    assert.deepEqual(await createPlanEditor().previewSwap(plan.plan_id, swap), preview);
    assert.equal(mock.calls[0].url.pathname, `/api/v1/plans/${plan.plan_id}/swaps/preview`);
    assert.deepEqual(mock.calls[0].body, { slot_id: swap.slotId, variant_id: swap.variantId, scope: 'pair', expected_revision: 2 });
    assert.equal(mock.calls[0].headers['Idempotency-Key'], undefined);
  } finally { mock.restore(); }
});

test('applySwap reuses its Idempotency-Key on retry, then rotates', async () => {
  const mock = mockFetch((call, n) => {
    if (n === 1) throw new TypeError('network down');
    if (n === 2) return err('unavailable', 503);
    return json({ plan, rule_warnings: [{ rule: 'r', message: 'm' }] }, 201);
  });
  try {
    const editor = createPlanEditor();
    await assert.rejects(editor.applySwap(plan.plan_id, swap), { code: 'source_unavailable' });
    await assert.rejects(editor.applySwap(plan.plan_id, swap));
    const result = await editor.applySwap(plan.plan_id, swap);
    assert.equal(mock.calls[2].body.scope, 'pair');
    const [k1, k2] = mock.calls.map(c => c.headers['Idempotency-Key']);
    assert.ok(k1); assert.equal(k1, k2);
    assert.deepEqual(result, { plan, ruleWarnings: [{ rule: 'r', message: 'm' }] });
    assert.equal(mock.calls[2].headers['Idempotency-Key'], k1);
    await editor.applySwap(plan.plan_id, swap);
    assert.notEqual(mock.calls[3].headers['Idempotency-Key'], k1);
  } finally { mock.restore(); }
});

test('applySwap treats a 200 no-op as success and maps errors', async () => {
  const noop = mockFetch(() => json({ plan, rule_warnings: [] }, 200));
  try { assert.equal((await createPlanEditor().applySwap(plan.plan_id, swap)).plan.revision, 3); } finally { noop.restore(); }
  for (const [code, status] of [['stale_revision', 409], ['slot_not_editable', 409], ['slot_not_found', 404], ['variant_not_found', 404], ['forbidden', 403]]) {
    const mock = mockFetch(() => err(code, status));
    try { await assert.rejects(createPlanEditor().applySwap(plan.plan_id, swap), error => error.code === code && error.status === status); } finally { mock.restore(); }
  }
});

test('swap calls validate input before fetching', async () => {
  const mock = mockFetch(() => json({}));
  try {
    const editor = createPlanEditor();
    await assert.rejects(editor.previewSwap(plan.plan_id, { ...swap, scope: 'both' }), { code: 'invalid_request' });
    await assert.rejects(editor.applySwap(plan.plan_id, { ...swap, expectedRevision: 0 }), { code: 'invalid_request' });
    assert.equal(mock.calls.length, 0);
  } finally { mock.restore(); }
});

test('variant search and protein filter', () => {
  const items = [
    { variant_id: 'a', name: 'Pollo toscano', protein: 'chicken', carb: 'rice' },
    { variant_id: 'b', name: 'Salmón al horno', protein: 'fish', carb: null },
    { variant_id: 'c', name: 'Pollo al curry', protein: 'chicken', carb: null },
  ];
  assert.deepEqual(filterVariants(items, 'salmon').map(i => i.variant_id), ['b']);
  assert.deepEqual(filterVariants(items, 'pollo cur').map(i => i.variant_id), ['c']);
  assert.deepEqual(filterVariants(items, '', 'chicken').map(i => i.variant_id), ['a', 'c']);
  assert.deepEqual(filterVariants(items, 'toscano', 'fish'), []);
  assert.deepEqual(proteinOptions(items), ['chicken', 'fish']);
});

test('only slots dated today or later can be swapped', () => {
  assert.equal(canSwapSlot({ date: '2026-10-21' }, '2026-10-21'), true);
  assert.equal(canSwapSlot({ date: '2026-10-20' }, '2026-10-21'), false);
});

test('grocery delta grouping and formatting', () => {
  const groups = groupGroceryDelta([
    { ingredient_id: 'x', display: 'Zeta', unit: 'g', section: 'veg', before: 10, after: 10, difference: 0 },
    { ingredient_id: 'a', display: 'Arroz', unit: 'g', section: 'pantry', before: 0, after: 70, difference: 70 },
    { ingredient_id: 'p', display: 'Pollo', unit: 'g', section: 'meat', before: 500, after: 240, difference: -260 },
    { ingredient_id: 'l', display: 'Limón', unit: 'units', section: 'meat', before: 1, after: 1.5, difference: 0.5 },
  ]);
  assert.deepEqual(groups.map(g => g.section), ['meat', 'pantry']);
  assert.deepEqual(groups[0].items.map(i => i.text), ['+0.5 units', '−260 g']);
  assert.equal(groups[0].items[1].direction, 'less');
  assert.equal(formatDifference(70, 'g'), '+70 g');
});

test('trip impact messages', () => {
  assert.equal(tripImpactMessage(null), null);
  assert.equal(tripImpactMessage({ name: 'Semana 1', status: 'open', extra_needed: [] }).text, "Shopping list 'Semana 1' will update automatically.");
  const done = tripImpactMessage({ name: 'Semana 1', status: 'done', extra_needed: [{ ingredient_id: 'a', display: 'Arroz', unit: 'g', quantity: 70 }, { ingredient_id: 'b', display: 'Limón', unit: 'units', quantity: 2 }] });
  assert.equal(done.text, "'Semana 1' is already done — you'll need: Arroz 70 g, Limón 2 units.");
});

test('trip impact lists every list and names the group when a list holds only one', () => {
  assert.deepEqual(tripImpactMessages(null), []);
  assert.deepEqual(tripImpactMessages(undefined), []);
  assert.equal(tripImpactMessages({ name: 'A', status: 'open', extra_needed: [] })[0].text, "Shopping list 'A' will update automatically.");
  const texts = tripImpactMessages([
    { trip_id: 'a', name: 'Month', status: 'done', groups: ['long_lasting'], extra_needed: [{ display: 'Arroz', unit: 'g', quantity: 70 }] },
    { trip_id: 'b', name: 'Mid-month', status: 'open', groups: ['fresh'], extra_needed: [] },
    { trip_id: 'c', name: 'Both', status: 'open', groups: ['long_lasting', 'fresh'], extra_needed: [] },
  ]).map(m => m.text);
  assert.deepEqual(texts, [
    "'Month' (Long-lasting) is already done — you'll need: Arroz 70 g.",
    "Shopping list 'Mid-month' (Fresh) will update automatically.",
    "Shopping list 'Both' will update automatically.",
  ]);
});

test('replaced_swaps produces the regenerate warning', () => {
  assert.equal(replacedSwapsWarning({ replaced_swaps: 0 }), null);
  assert.equal(replacedSwapsWarning({}), null);
  assert.equal(replacedSwapsWarning({ replaced_swaps: 1 }), 'This will replace 1 meal you swapped.');
  assert.equal(replacedSwapsWarning({ replaced_swaps: 3 }), 'This will replace 3 meals you swapped.');
});

test('swap error messages', () => {
  assert.match(swapErrorMessage({ code: 'stale_revision' }), /changed/);
  assert.match(swapErrorMessage({ code: 'slot_not_editable' }), /past/);
  assert.equal(swapErrorMessage({ code: 'other', message: 'boom' }), 'boom');
  assert.equal(swapNeedsReload({ code: 'stale_revision' }), true);
  assert.equal(swapNeedsReload({ code: 'variant_not_found' }), false);
});

const CATALOG = [
  { variant_id: 's_yuca', recipe_id: 's', name: 'Sudado', protein: 'chicken', carb: 'yuca', default: false },
  { variant_id: 's_potato', recipe_id: 's', name: 'Sudado', protein: 'chicken', carb: 'potato', default: true },
  { variant_id: 's_none', recipe_id: 's', name: 'Sudado', protein: 'chicken', carb: null, default: false },
  { variant_id: 's_arepa', recipe_id: 's', name: 'Sudado', protein: 'chicken', carb: 'arepa', default: false },
  { variant_id: 'a_rice', recipe_id: 'a', name: 'Arroz con pollo', protein: 'chicken', carb: 'rice', default: true },
  { variant_id: 'h_none', recipe_id: 'h', name: 'Hamburguesas', protein: 'chicken', carb: null, default: true },
];

test('groupRecipes for a lunch offers only carbs, in offer order, and drops no-carb recipes', () => {
  const recipes = groupRecipes(CATALOG, 'lunch');
  assert.deepEqual(recipes.map(r => r.recipe_id), ['s', 'a']);
  assert.deepEqual(recipes[0].variants.map(v => v.carb), ['potato', 'yuca', 'arepa']);
  assert.equal(carbSummary(recipes[0]), '3 carb options');
  assert.equal(carbSummary(recipes[1]), 'Only Arroz');
});

test('groupRecipes for a dinner offers only the no-carb variants', () => {
  const recipes = groupRecipes(CATALOG, 'dinner');
  assert.deepEqual(recipes.map(r => [r.recipe_id, r.variants.map(v => v.variant_id)]), [['s', ['s_none']], ['h', ['h_none']]]);
  assert.equal(carbSummary(recipes[0]), 'No carb');
});

test('defaultVariant keeps the current carb, else starts on the recipe default (never no carb at lunch)', () => {
  const [sudado] = groupRecipes(CATALOG, 'lunch');
  assert.equal(defaultVariant(sudado, 'yuca').variant_id, 's_yuca');
  assert.equal(defaultVariant(sudado, 'rice').variant_id, 's_potato');
  assert.equal(defaultVariant(sudado, null).variant_id, 's_potato');
});

test('fitsMeal: a lunch needs a carb and a dinner has none', () => {
  assert.equal(fitsMeal({ carb: 'rice' }, 'lunch'), true);
  assert.equal(fitsMeal({ carb: null }, 'lunch'), false);
  assert.equal(fitsMeal({ carb: null }, 'dinner'), true);
  assert.equal(fitsMeal({ carb: 'rice' }, 'dinner'), false);
});

test('lunchCarbsByRecipe lists each recipe\'s lunch carbs; one carb means a fixed recipe', () => {
  const byRecipe = lunchCarbsByRecipe(CATALOG);
  assert.deepEqual(byRecipe.get('s'), ['potato', 'yuca', 'arepa']);
  assert.deepEqual(byRecipe.get('a'), ['rice']);
  assert.equal(byRecipe.has('h'), false);
});

test('carbLabel uses the ingredient display names', () => {
  assert.equal(carbLabel(null), 'No carb');
  assert.equal(carbLabel('none'), 'No carb');
  assert.equal(carbLabel('platano_maduro'), 'Plátano maduro');
  assert.equal(carbLabel('rice'), 'Arroz');
  assert.equal(carbLabel('corn'), 'Maíz tierno');
  assert.equal(carbLabel('something_new'), 'Something new');
});

test('slotCarbName prefers the slot\'s carb ingredient row', () => {
  assert.equal(slotCarbName({ carb: 'arepa', ingredients: [{ role: 'carb', display: 'Arepa de maíz' }] }), 'Arepa de maíz');
  assert.equal(slotCarbName({ carb: 'rice', ingredients: [] }), 'Arroz');
});

test('swap errors for the carb rules read clearly', () => {
  assert.match(swapErrorMessage({ code: 'carb_required' }), /lunch always needs a carb/);
  assert.match(swapErrorMessage({ code: 'carb_not_allowed' }), /Dinner has no carb/);
});

test('changeLabels shows only the carbs when the recipe stays the same', () => {
  const before = { recipe_id: 'e', recipe_name: 'Ensalada', carb: 'platano_maduro' };
  assert.deepEqual(changeLabels({ before, after: { ...before, carb: 'rice' } }), { before: 'Plátano maduro', after: 'Arroz', carbOnly: true });
  assert.deepEqual(changeLabels({ before, after: { recipe_id: 'a', recipe_name: 'Arroz con pollo', carb: 'rice' } }), { before: 'Ensalada', after: 'Arroz con pollo', carbOnly: false });
  assert.deepEqual(changeLabels({ before: null, after: null }), { before: '(none)', after: '(removed)', carbOnly: false });
});
