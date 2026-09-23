/** Helpers for the HTML job description returned by the backend. */

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
