import { useMemo } from 'react';
import { htmlToBlocks } from '../../../utils/html';
import './Prose.scss';

interface ProseProps {
  /** Backend HTML or flattened text - never rendered as markup. */
  content: string | null | undefined;
  className?: string;
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
 */
export function Prose({ content, className }: ProseProps) {
  const blocks = useMemo(() => htmlToBlocks(content), [content]);

  if (blocks.length === 0) return null;

  return (
    <div className={['prose', className].filter(Boolean).join(' ')}>
      {blocks.map((block, index) => {
        if (block.kind === 'p') {
          return (
            <p key={index} className="prose__p">
              {block.text}
            </p>
          );
        }
        const ListTag: 'ul' | 'ol' = block.kind;
        return (
          <ListTag key={index} className={`prose__list prose__list--${block.kind}`}>
            {block.items.map((item, itemIndex) => (
              <li key={itemIndex} className="prose__li">
                {item}
              </li>
            ))}
          </ListTag>
        );
      })}
    </div>
  );
}
