/** Cross-component highlight state — Svelte 5 rune-based store. */
class CitationState {
  active = $state<string | null>(null);
  highlightDocId = $state<string | null>(null);
}

export const citations = new CitationState();

/** A citation mark was followed: mark the source entry active (opening
 *  a closed list around it), focus it
 *  (tabindex -1) so the next Tab reaches its source link, and bring it
 *  into view with one instant scroll (preventScroll stops the focus jump;
 *  a smooth scroll would run past the 150 ms motion budget). */
export function activateCitation(e: MouseEvent, id: string): void {
  e.preventDefault();
  citations.active = id;
  const el = document.getElementById(`cite-${id}`);
  if (!el) return;
  // A long source list starts closed; open it so the entry can show.
  const list = el.closest('details');
  if (list && !list.open) list.open = true;
  el.focus({ preventScroll: true });
  el.scrollIntoView({ block: 'nearest' });
}
