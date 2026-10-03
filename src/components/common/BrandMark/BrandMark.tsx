import './BrandMark.scss';

interface BrandMarkProps {
  /** 40 = sidebar rail, 30 = mobile bar, 24 = compact/nav-in-header. */
  size?: 'sm' | 'md' | 'lg';
}

/**
 * The JIIT Placement product mark: a single geometric "JP" monogram.
 *
 * One vertical stroke does three jobs at once — it is the spine of the P,
 * it is the descender of the J, and it is the line the two letters are
 * hung off. The bowl sits on its upper right, the hook leaves its foot to
 * the left, so J and P are not two glyphs sat next to each other but one
 * mark read two ways. Nothing else is drawn: no counters, no serifs, no
 * decoration, so it survives at 24px and at favicon size.
 *
 * Set as strokes rather than type so it is never dependent on the font
 * being loaded or present — the shape is the identity, not the letters.
 *
 * Decorative by design: the product name is printed in full beside it, so
 * it is hidden from assistive tech rather than double-announced.
 */
export function BrandMark({ size = 'lg' }: BrandMarkProps) {
  return (
    <span className={`brand-mark brand-mark--${size}`} aria-hidden="true">
      <svg
        className="brand-mark__glyph"
        viewBox="0 0 32 32"
        fill="none"
        stroke="currentColor"
        strokeWidth={3.6}
        strokeLinecap="round"
        strokeLinejoin="round"
        focusable="false"
      >
        {/* Shared stem + the J's leftward hook at its foot. */}
        <path d="M12.5 5v16c0 4-2.5 6.2-6 5.7" />
        {/* The P's bowl, springing from the stem's head and returning to it. */}
        <path d="M12.5 5H19c4 0 6.5 2.3 6.5 6s-2.5 6-6.5 6h-6.5" />
      </svg>
    </span>
  );
}
