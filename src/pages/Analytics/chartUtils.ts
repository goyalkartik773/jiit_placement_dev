import { useEffect, useRef, useState, type RefObject } from 'react';

/**
 * Tiny dependency-free chart maths for the Analytics screen.
 *
 * Nothing here knows about branches or packages — it only turns numbers into
 * coordinates, so both chart components share one set of scales and one set of
 * axis conventions.
 */

export interface Point {
  x: number;
  y: number;
}

/**
 * Measure a container so the SVG can be drawn at 1:1 pixels instead of being
 * scaled through a `viewBox` (which would scale the axis text with it and leave
 * it at 8px on a phone). Falls back to `minWidth` before the first observation,
 * and never reports narrower than `minWidth` — the wrapper scrolls instead.
 */
export function useMeasuredWidth(minWidth: number): [RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(minWidth);

  useEffect(() => {
    const element = ref.current;
    if (!element) return undefined;
    const apply = () => setWidth(Math.max(minWidth, Math.round(element.clientWidth)));
    apply();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(apply);
    observer.observe(element);
    return () => observer.disconnect();
  }, [minWidth]);

  return [ref, width];
}

/** Round a domain top up to 1/2/2.5/5 × 10ⁿ so the grid lands on round numbers. */
export function niceCeil(value: number, stepCount = 4): number {
  if (!Number.isFinite(value) || value <= 0) return 1;
  const rough = value / stepCount;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rough)));
  const normalised = rough / magnitude;
  const step =
    (normalised <= 1 ? 1 : normalised <= 2 ? 2 : normalised <= 2.5 ? 2.5 : normalised <= 5 ? 5 : 10) * magnitude;
  return Math.round(step * Math.ceil(value / step) * 1000) / 1000;
}

/** `stepCount + 1` evenly spaced ticks from 0 → max, rounded for display. */
export function ticksUpTo(max: number, stepCount = 4): number[] {
  if (!Number.isFinite(max) || max <= 0) return [0];
  const step = max / stepCount;
  return Array.from({ length: stepCount + 1 }, (_, index) => {
    // Kill float dust like 149.99999999999997 before it reaches a label.
    return Math.round(step * index * 1000) / 1000;
  });
}

/**
 * Polyline `d` for a series whose values may contain nulls ("no data here").
 * A null breaks the pen so the line resumes with a fresh `M` instead of
 * dropping to zero and inventing a dip.
 */
export function linePath(points: (Point | null)[]): string {
  let path = '';
  let penDown = false;
  for (const point of points) {
    if (!point) {
      penDown = false;
      continue;
    }
    path += `${penDown ? ' L ' : ' M '}${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
    penDown = true;
  }
  return path.trim();
}

/** Closed area under a (null-free) series, back down to `baselineY`. */
export function areaPath(points: Point[], baselineY: number): string {
  if (points.length === 0) return '';
  const first = points[0];
  const last = points[points.length - 1];
  const line = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(' ');
  return `${line} L ${last.x.toFixed(2)} ${baselineY.toFixed(2)} L ${first.x.toFixed(2)} ${baselineY.toFixed(2)} Z`;
}

/**
 * Keep an axis readable when a lot of buckets would collide: show every
 * `stride`-th label. Returns 1 (all labels) when the series is short.
 */
export function labelStride(count: number, maxLabels: number): number {
  if (count <= maxLabels) return 1;
  return Math.ceil(count / maxLabels);
}
