/**
 * Some manifests (e.g. sandy.yaml) author narration.short and
 * narration.template to say almost the same thing — cardAdapter's
 * 'headline' variant then renders both as headline + body, and the card
 * visibly repeats itself ("This address is within the empirical 2012
 * Hurricane Sandy inundation footprint." immediately followed by "This
 * address sits within the empirical 2012 Hurricane Sandy inundation
 * footprint (NYC OEM)."). A manifest-content fix only covers the
 * manifests we've noticed; this is the systemic backstop.
 *
 * Word-overlap ratio rather than exact match — real duplicates paraphrase
 * ("is within" vs "sits within") rather than repeat verbatim.
 */
const REDUNDANCY_THRESHOLD = 0.75;

function normalize(s: string): string {
  return s
    .toLowerCase()
    .replace(/\([^)]*\)/g, '')
    .replace(/[^\w\s]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function isRedundantBody(headline: string, body: string): boolean {
  const a = normalize(headline);
  const b = normalize(body);
  if (!a || !b) return false;
  if (a === b) return true;
  const wordsA = new Set(a.split(' '));
  const wordsB = new Set(b.split(' '));
  const smaller = Math.min(wordsA.size, wordsB.size);
  if (smaller === 0) return false;
  let overlap = 0;
  for (const w of wordsA) if (wordsB.has(w)) overlap++;
  return overlap / smaller > REDUNDANCY_THRESHOLD;
}
