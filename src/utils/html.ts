/** Helpers for the HTML job description returned by the backend. */

/**
 * Converts backend notice content into plain text that can be rendered as
 * text nodes (never as markup). Plain text is kept as-is, including its line
 * breaks; HTML has its block boundaries turned into newlines first so the
 * structure survives without a single tag in the output.
 */
export function htmlToPlainText(value: string | null | undefined): string {
  if (!value) return '';

  const looksLikeHtml = /<[a-z][^>]*>/i.test(value);
  if (!looksLikeHtml) return value.replace(/\r\n?/g, '\n').trim();

  const prepared = value
    .replace(/<\s*br\s*\/?\s*>/gi, '\n')
    .replace(/<\s*\/\s*(p|div|li|h[1-6]|tr|blockquote|section|ul|ol|table)\s*>/gi, '\n')
    .replace(/<\s*li[^>]*>/gi, '- ');

  let text: string;
  try {
    const doc = new DOMParser().parseFromString(prepared, 'text/html');
    text = doc.body?.textContent ?? '';
  } catch {
    text = prepared.replace(/<[^>]*>/g, ' ');
  }

  return text
    .replace(/\r\n?/g, '\n')
    .replace(/\u00A0/g, ' ')
    .split('\n')
    .map((line) => line.trim())
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/** Converts backend HTML into plain text (safe, executed in an isolated document). */
export function stripHtml(html: string | null | undefined): string {
  if (!html) return '';
  try {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    return (doc.body.textContent ?? '').replace(/\s+/g, ' ').trim();
  } catch {
    return html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
  }
}

// --------------------------------------------------------------------------- #
// Structured blocks — so a bullet list is always <ul><li>, never a "- " prefix
// --------------------------------------------------------------------------- #

export type NoticeBlock =
  | { kind: 'p'; text: string }
  | { kind: 'ul'; items: string[] }
  | { kind: 'ol'; items: string[] };

const HAS_TAG = /<[a-z][^>]*>/i;
const BULLET_PREFIX = /^\s*(?:[-*•▪◦·]|\d+[.)])\s+/;
const BLOCK_TAGS = new Set([
  'ADDRESS', 'ARTICLE', 'ASIDE', 'BLOCKQUOTE', 'DD', 'DETAILS', 'DIV', 'DL',
  'DT', 'FIELDSET', 'FIGCAPTION', 'FIGURE', 'FOOTER', 'FORM', 'H1', 'H2',
  'H3', 'H4', 'H5', 'H6', 'HEADER', 'HR', 'LI', 'MAIN', 'NAV', 'OL', 'P',
  'PRE', 'SECTION', 'TABLE', 'TD', 'TH', 'TR', 'UL',
]);

function flushParagraph(buffer: string[], out: NoticeBlock[]): void {
  const text = buffer
    .join('')
    .replace(/\u00A0/g, ' ')
    .split('\n')
    .map((line) => line.replace(/[ \t]+/g, ' ').trim())
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  buffer.length = 0;
  if (text) out.push({ kind: 'p', text });
}

/** Plain text: blank lines break paragraphs, "- "/"1." lines form lists. */
function blocksFromText(value: string): NoticeBlock[] {
  const blocks: NoticeBlock[] = [];
  let paragraph: string[] = [];
  let bullets: string[] = [];
  let ordered = false;

  const flushParagraphRun = () => {
    flushParagraph(paragraph, blocks);
  };
  const flushList = () => {
    if (bullets.length) {
      blocks.push({ kind: ordered ? 'ol' : 'ul', items: bullets });
      bullets = [];
      ordered = false;
    }
  };

  for (const line of value.replace(/\r\n?/g, '\n').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed) {
      flushList();
      flushParagraphRun();
      continue;
    }
    const bullet = BULLET_PREFIX.exec(trimmed);
    if (bullet) {
      flushParagraphRun();
      const nextOrdered = /^\s*\d+[.)]/.test(trimmed);
      if (bullets.length && nextOrdered !== ordered) flushList();
      ordered = nextOrdered;
      bullets.push(trimmed.slice(bullet[0].length).trim());
      continue;
    }
    flushList();
    paragraph.push(line);
  }
  flushList();
  flushParagraphRun();
  return blocks;
}

/**
 * Turns notice/description content into renderable blocks.
 *
 * The backend hands us HTML *or* pre-flattened text in which list items have
 * already been reduced to a dash prefix.  Either way the result is real
 * `<ul><li>` / `<ol><li>` structure, so `Prose` can lay every item out with a
 * hanging indent - a wrapped bullet lines up under its text instead of
 * sliding back under the marker.
 */
export function htmlToBlocks(value: string | null | undefined): NoticeBlock[] {
  if (!value) return [];
  const source = value.trim();
  if (!source) return [];
  if (!HAS_TAG.test(source)) return blocksFromText(source);

  const prepared = source
    .replace(/<\s*br\s*\/?\s*>/gi, '\n')
    .replace(/<\s*\/\s*(p|div|li|h[1-6]|tr|blockquote|section|table)\s*>/gi, '\n');

  let doc: Document | null = null;
  try {
    doc = new DOMParser().parseFromString(prepared, 'text/html');
  } catch {
    doc = null;
  }
  if (!doc?.body) return blocksFromText(source.replace(/<[^>]*>/g, '\n'));

  const blocks: NoticeBlock[] = [];
  let buffer: string[] = [];

  const walk = (node: Node): void => {
    if (node.nodeType === Node.TEXT_NODE) {
      if (node.textContent) buffer.push(node.textContent);
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const element = node as HTMLElement;

    if (element.tagName === 'UL' || element.tagName === 'OL') {
      flushParagraph(buffer, blocks);
      const items = Array.from(element.children)
        .filter((child) => child.tagName === 'LI')
        .map((child) => (child.textContent || '').replace(/\s+/g, ' ').trim())
        .filter(Boolean);
      if (items.length) {
        blocks.push({ kind: element.tagName === 'UL' ? 'ul' : 'ol', items });
      } else {
        // An empty <ul> still carries its text somewhere - fall through.
        Array.from(element.childNodes).forEach(walk);
      }
      return;
    }

    const isBlock = BLOCK_TAGS.has(element.tagName);
    if (isBlock) flushParagraph(buffer, blocks);
    Array.from(element.childNodes).forEach(walk);
    if (isBlock) flushParagraph(buffer, blocks);
  };

  Array.from(doc.body.childNodes).forEach(walk);
  flushParagraph(buffer, blocks);
  return blocks.length ? blocks : blocksFromText(source.replace(/<[^>]*>/g, '\n'));
}

/**
 * Forces external links inside rendered description HTML to open safely in a
 * new tab. Called after render via ref — avoids mutating backend content.
 */
export function hardenHtmlLinks(container: HTMLElement | null): void {
  if (!container) return;
  container.querySelectorAll('a[href]').forEach((anchor) => {
    anchor.setAttribute('target', '_blank');
    anchor.setAttribute('rel', 'noopener noreferrer');
  });
}

/** Money words surfaced in the description (spec: yellow highlight). */
const MONEY_TERMS = ['stipend', 'package', 'salary', 'ctc', 'compensation', 'bonus', 'incentive', 'remuneration'];

/**
 * Wraps whole money-related words in <mark> inside the rendered description
 * so stipend/package figures pop (styled via .job-description__prose mark).
 * Text already inside a <mark> is skipped, so re-running is safe.
 */
export function highlightMoneyTerms(container: HTMLElement | null): void {
  if (!container) return;
  const pattern = new RegExp(`\\b(?:${MONEY_TERMS.join('|')})\\b`, 'gi');

  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const targets: Text[] = [];
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const textNode = node as Text;
    if (textNode.parentElement?.tagName === 'MARK') continue;
    pattern.lastIndex = 0;
    if (textNode.nodeValue && pattern.test(textNode.nodeValue)) targets.push(textNode);
  }

  for (const textNode of targets) {
    const source = textNode.nodeValue ?? '';
    const fragment = document.createDocumentFragment();
    let cursor = 0;
    pattern.lastIndex = 0;
    for (let match = pattern.exec(source); match; match = pattern.exec(source)) {
      if (match.index > cursor) fragment.appendChild(document.createTextNode(source.slice(cursor, match.index)));
      const mark = document.createElement('mark');
      mark.textContent = match[0];
      fragment.appendChild(mark);
      cursor = match.index + match[0].length;
    }
    if (cursor < source.length) fragment.appendChild(document.createTextNode(source.slice(cursor)));
    textNode.parentNode?.replaceChild(fragment, textNode);
  }
}
