import { memo, useMemo } from 'react';
import { htmlToBlocks } from '../../../utils/html';
import { highlightText } from '../../../utils/highlight';
import './Prose.scss';

interface ProseProps {
  /** Backend HTML or flattened text - never rendered as markup. */
  content: string | null | undefined;
  className?: string;
  /**
   * Tint the important parts of the text - money green, dates accent,
   * action words amber - through utils/highlight.tsx (real <mark> nodes,
   * no DOM mutation). Off by default so the Superset notice screen keeps
   * its current, already-approved look.
   */
  highlight?: boolean;
}

/**
 * Safe rich-text renderer for notice / description bodies.
 *
 * Content is parsed into blocks first, so bullet lines always become real
 * `<ul><li>` (and numbered lines `<ol><li>`) instead of a "- " prefix inside
 * a paragraph.  `Prose.scss` gives every item a fixed marker column, which is
 * what makes a wrapped bullet line up under its own text - a hanging indent -
 * rather than under the marker.
 *
 * Paragraphs keep their line breaks (`white-space: pre-line`), so `<br>`-fed
 * address/date lines in a Superset notice survive intact.
 *
 * Exported memoized: the e-mail "Read more" panel re-renders on every
 * student-search keystroke, and this body can be 60,000 characters of
 * highlighted text - props are all primitives, so memo skips it cleanly.
 */
export const Prose = memo(function Prose({ content, className, highlight = false }: ProseProps) {
  const blocks = useMemo(() => htmlToBlocks(content), [content]);

  if (blocks.length === 0) return null;

  return (
    <div className={['prose', className].filter(Boolean).join(' ')}>
      {blocks.map((block, index) => {
        if (block.kind === 'p') {
          return (
            <p key={index} className="prose__p">
              {highlight ? highlightText(block.text, `p${index}`) : block.text}
            </p>
          );
        }
        const ListTag: 'ul' | 'ol' = block.kind;
        return (
          <ListTag key={index} className={`prose__list prose__list--${block.kind}`}>
            {block.items.map((item, itemIndex) => (
              <li key={itemIndex} className="prose__li">
                {highlight ? highlightText(item, `l${index}-${itemIndex}`) : item}
              </li>
            ))}
          </ListTag>
        );
      })}
    </div>
  );
});
