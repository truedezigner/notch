import assert from 'node:assert/strict';
import {
  categoryFor,
  encodedTodoTitle,
  needsCategoryOrganization,
  organizeByCategory,
  parseSpokenNote,
  parseTodoSpeech
} from './voice-parser.js';

const packing = parseTodoSpeech('Phone charger and cable, kids snacks, shirts, toothbrush and toothpaste');
assert.deepEqual(packing, [
  { title: 'Phone charger and cable', category: 'Electronics' },
  { title: 'kids snacks', category: 'Kids' },
  { title: 'shirts', category: 'Clothing' },
  { title: 'toothbrush and toothpaste', category: 'Toiletries' }
]);
assert.equal(needsCategoryOrganization(packing), true);
assert.deepEqual(organizeByCategory(packing).map((item) => item.category), [
  'Clothing', 'Toiletries', 'Electronics', 'Kids'
]);
assert.equal(encodedTodoTitle({ title: 'shirts', category: 'Clothing' }, true), '[Clothing] shirts');
assert.equal(encodedTodoTitle({ title: 'call dentist', category: 'Other' }, true), 'call dentist');

const actions = parseTodoSpeech('I need to call the dentist and then buy toothpaste, call the school');
assert.deepEqual(actions.map((item) => item.title), ['call the dentist', 'buy toothpaste', 'call the school']);
assert.equal(categoryFor('pack the passports'), 'Documents');

const screenshotPhrase = parseTodoSpeech("I want a mattress topper and ask Royal Caribbean about the cribs available on board if they're just packing please");
assert.deepEqual(screenshotPhrase.map((item) => item.title), [
  'a mattress topper',
  "ask Royal Caribbean about the cribs available on board if they're just packing"
]);

assert.deepEqual(
  parseTodoSpeech('Get milk and call the pharmacy').map((item) => item.title),
  ['Get milk', 'call the pharmacy']
);
assert.deepEqual(
  parseTodoSpeech('I need diapers and I need sunscreen').map((item) => item.title),
  ['diapers', 'sunscreen']
);
assert.deepEqual(
  parseTodoSpeech('Phone charger and cable. Toothbrush and toothpaste.').map((item) => item.title),
  ['Phone charger and cable', 'Toothbrush and toothpaste']
);
assert.equal(parseTodoSpeech('toothbrush and toothpaste').length, 1);

assert.deepEqual(parseSpokenNote('Title Summer plans body Book the hotel and reserve a car'), {
  title: 'Summer plans',
  body: 'Book the hotel and reserve a car'
});
assert.deepEqual(parseSpokenNote('A short note about tomorrow.'), {
  title: 'A short note about tomorrow',
  body: 'A short note about tomorrow.'
});

console.log('voice parser tests passed');
