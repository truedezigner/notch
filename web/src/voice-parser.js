export const VOICE_CATEGORIES = [
  'Clothing',
  'Toiletries',
  'Electronics',
  'Kids',
  'Food',
  'Documents',
  'Medicine',
  'Other'
];

const CATEGORY_RULES = [
  ['Clothing', /\b(shirts?|pants|jeans|shorts|socks?|underwear|bras?|dresses|dress|skirts?|jackets?|coats?|sweaters?|hoodies?|shoes?|boots?|hats?|pajamas?|swimsuits?|clothes|clothing)\b/i],
  ['Toiletries', /\b(toothbrush(?:es)?|toothpaste|floss|shampoo|conditioner|soaps?|deodorant|razors?|lotions?|sunscreen|makeup|toiletr\w*|hairbrush(?:es)?|combs?|towels?)\b/i],
  ['Electronics', /\b(phones?|tablets?|ipads?|laptops?|computers?|chargers?|charging|cables?|cords?|adapters?|batter(?:y|ies)|headphones?|earbuds?|cameras?|kindle|watches|watch)\b/i],
  ['Kids', /\b(kid|kids|child|children|baby|babies|diapers?|wipes|strollers?|car seats?|toys?|school|lunchboxes?|bottles?|formula)\b/i],
  ['Food', /\b(food|snacks?|drinks?|water|milk|bread|fruits?|vegetables?|grocery|groceries|coffee|tea|juice|sandwiches|sandwich)\b/i],
  ['Documents', /\b(passports?|licenses?|id cards?|tickets?|reservations?|documents?|paperwork|insurance cards?|boarding passes?)\b/i],
  ['Medicine', /\b(medicine|medications?|prescriptions?|pills?|vitamins?|inhalers?|epipens?|first aid|bandages?|tylenol|ibuprofen)\b/i]
];

const ACTION_VERBS = [
  'ask', 'arrange', 'book', 'bring', 'buy', 'call', 'cancel', 'charge', 'check',
  'clean', 'collect', 'confirm', 'contact', 'drop off', 'email', 'find', 'fix',
  'follow up', 'get', 'look up', 'make', 'order', 'pack', 'pay', 'pick up',
  'print', 'refill', 'replace', 'request', 'research', 'reserve', 'return',
  'schedule', 'send', 'submit', 'take', 'text', 'wash'
];

const ACTION_PATTERN = ACTION_VERBS
  .sort((a, b) => b.length - a.length)
  .map((verb) => verb.replace(/ /g, '\\s+'))
  .join('|');

function cleanItem(value) {
  return value
    .replace(/^\s*(?:please\s+)?(?:add|remember|remind me)\s+(?:that\s+)?/i, '')
    .replace(/^\s*(?:i|we)\s+(?:also\s+)?(?:need|want|have)\s+(?:to\s+)?/i, '')
    .replace(/^\s*(?:also|then|and then|and|plus)\s+/i, '')
    .replace(/^\s*(?:to|the)\s+(?=\w)/i, '')
    .replace(/\s+please\s*$/i, '')
    .replace(/[\s.]+$/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function categoryFor(text) {
  for (const [category, rule] of CATEGORY_RULES) {
    if (rule.test(text)) return category;
  }
  return 'Other';
}

export function parseTodoSpeech(transcript) {
  const normalized = String(transcript || '')
    .replace(/\b(?:next|new)\s+(?:item|thing)\b/gi, ';')
    .replace(/\b(?:first|second|third|fourth|fifth)\s+(?:item|thing)\b/gi, ';')
    .replace(/\s+(?:and|also|plus)\s+(?=(?:i|we)\s+(?:also\s+)?(?:need|want|have)\b)/gi, ';')
    .replace(new RegExp(`\\b(?:and\\s+then|then)\\s+(?=(?:please\\s+)?(?:${ACTION_PATTERN})\\b)`, 'gi'), ';')
    .replace(new RegExp(`\\s+(?:and|also|plus)\\s+(?=(?:please\\s+)?(?:${ACTION_PATTERN})\\b)`, 'gi'), ';')
    .replace(/[\n,;•]+/g, ';')
    .replace(/[!?]+(?:\s+|$)/g, ';')
    .replace(/\.(?:\s+|$)/g, ';');

  const seen = new Set();
  return normalized
    .split(';')
    .map(cleanItem)
    .filter(Boolean)
    .filter((title) => {
      const key = title.toLocaleLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map((title) => ({ title, category: categoryFor(title) }));
}

export function needsCategoryOrganization(items) {
  const ranks = items.map((item) => VOICE_CATEGORIES.indexOf(item.category));
  const unique = new Set(ranks.filter((rank) => rank >= 0));
  if (unique.size < 2) return false;
  return ranks.some((rank, index) => index > 0 && rank < ranks[index - 1]);
}

export function organizeByCategory(items) {
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => {
      const categoryDelta = VOICE_CATEGORIES.indexOf(a.item.category) - VOICE_CATEGORIES.indexOf(b.item.category);
      return categoryDelta || a.index - b.index;
    })
    .map(({ item }) => item);
}

export function encodedTodoTitle(item, includeCategory) {
  const title = cleanItem(item.title);
  if (!includeCategory || item.category === 'Other') return title;
  return `[${item.category}] ${title}`;
}

export function parseSpokenNote(transcript) {
  const text = String(transcript || '').replace(/\s+/g, ' ').trim();
  const titled = text.match(/^(?:note\s+)?title\s+(.+?)\s+(?:body|content|says?)\s+(.+)$/i);
  if (titled) return { title: cleanItem(titled[1]), body: titled[2].trim() };

  const firstSentence = text.split(/[.!?](?:\s|$)/)[0].trim();
  const words = firstSentence.split(/\s+/).filter(Boolean);
  const title = words.slice(0, 8).join(' ') + (words.length > 8 ? '…' : '');
  return { title: title || 'Voice note', body: text };
}
