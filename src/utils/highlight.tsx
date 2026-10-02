import type { ReactNode } from 'react';

/**
 * Semantic highlighter for placement-email bodies ("Read more" panel).
 *
 * Text is split into plain chunks and tinted <mark> elements - pure React
 * nodes, never DOM mutation - so the output stays memoizable, testable and
 * impossible to inject markup through. Three tints carry three meanings:
 *
 *   money  - rupee figures, LPA, salary words  -> green
 *   date   - dates, times, weekdays            -> accent (blue)
 *   action - deadlines, registration, interview -> amber
 *
 * One combined pattern alternates in that order, so at any position the
 * most specific meaning wins (JS alternation tries alternatives in order at
 * the leftmost match position). The shared module-level regex is safe
 * because every scan resets `lastIndex` first (JS is single-threaded).
 *
 * Backgrounds/inks come from the contrast-checked `--ui-tint-*` pairs in
 * _ui.scss (4.84-5.06:1), so a paragraph full of marks still passes AA.
 */
export type HighlightKind = 'money' | 'date' | 'action';

const MONTHS =
  'Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|' +
  'Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?';

const MONEY_SOURCE = [
  '₹\\s?\\d[\\d,]*(?:\\.\\d+)?', // ₹1,20,000 / ₹500
  '\\b(?:Rs\\.?|INR)\\s?\\d[\\d,]*(?:\\.\\d+)?', // Rs. 5000 / INR 4.5
  '\\b\\d+(?:\\.\\d+)?\\s?(?:LPA|Lakhs?|lakhs?)\\b', // 12.5 LPA / 6 Lakhs
  '\\b(?:stipend(?:s)?|package(?:s)?|salaries|salary|CTC|compensation|' +
    'bonus(?:es)?|incentive(?:s)?|remuneration|cost to company)\\b',
].join('|');

const DATE_SOURCE = [
  `\\b\\d{1,2}(?:st|nd|rd|th)?\\s+(?:${MONTHS})\\.?,?\\s+\\d{4}\\b`, // 15 March 2026
  `\\b(?:${MONTHS})\\.?\\s+\\d{1,2}(?:st|nd|rd|th)?,?\\s+\\d{4}\\b`, // March 15, 2026
  `\\b\\d{1,2}(?:st|nd|rd|th)?\\s+(?:${MONTHS})\\.?\\b`, // 13 March (no year)
  '\\b\\d{4}-\\d{2}-\\d{2}(?:[T ]\\d{2}:\\d{2}(?::\\d{2})?)?', // 2026-06-02T09:00
  '\\b\\d{1,2}/\\d{1,2}/\\d{2,4}\\b', // 28/09/2026
  '\\b\\d{1,2}:\\d{2}\\s?(?:AM|PM|am|pm)\\b', // 9:50 AM
  '\\b\\d{1,2}\\s?(?:AM|PM|am|pm)\\b', // 10 AM
  '\\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\\b',
].join('|');

const ACTION_SOURCE = [
  '\\b(?:shortlist(?:ed|ing|s)?|interview(?:s|ed|ing)?|registration|registered|' +
    'register(?:ed|ing|s)?|deadline(?:s)?|last\\s+date|attend(?:ance|ed|ing)?|' +
    'report(?:ing|ed)?|confirm(?:ed|ation)?|appear(?:ing)?|submit(?:ted|ting)?|' +
    'selected|selection|offer(?:ed)?|postpon(?:e|ed|ement)|cancel(?:led|ation|ing)?|' +
    'venue|online\\s+test|assessment(?:s)?)\\b',
].join('|');

const SCANNER = new RegExp(
  `(?<money>${MONEY_SOURCE})|(?<date>${DATE_SOURCE})|(?<action>${ACTION_SOURCE})`,
  'gi',
);

/**
 * Splits `text` into plain strings and semantic <mark> nodes.
 * `keyPrefix` keeps React keys unique inside one parent.
 */
export function highlightText(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  if (!text) return nodes;

  SCANNER.lastIndex = 0;
  let cursor = 0;
  let index = 0;
  let match: RegExpExecArray | null;

  while ((match = SCANNER.exec(text)) !== null) {
    if (match.index > cursor) nodes.push(text.slice(cursor, match.index));
    const groups = match.groups;
    const kind: HighlightKind = groups?.money ? 'money' : groups?.date ? 'date' : 'action';
    nodes.push(
      <mark key={`${keyPrefix}-h${index}`} className={`ui-mark ui-mark--${kind}`}>
        {match[0]}
      </mark>,
    );
    cursor = match.index + match[0].length;
    index += 1;
    if (match[0].length === 0) SCANNER.lastIndex += 1; // defensive: never spin
  }
  if (cursor < text.length) nodes.push(text.slice(cursor));
  return nodes;
}

/**
 * Gmail plain-text bodies wrap emphasis in single asterisks (*like this*).
 * Same-line pairs are unwrapped before rendering so the body reads like a
 * written notice instead of raw text. A star bullet ("* " at line start)
 * never opens a pair (the opener must be followed by a non-space), and a
 * pair that crosses a newline is left untouched rather than guessed at.
 */
const EMPHASIS = /\*([^*\s](?:[^*\n]*[^*\s])?)\*/g;

export function stripEmphasis(text: string): string {
  if (!text || !text.includes('*')) return text;
  return text.replace(EMPHASIS, '$1');
}
