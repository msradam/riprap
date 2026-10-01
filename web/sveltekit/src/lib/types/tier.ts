export type Tier = 'empirical' | 'modeled' | 'proxy' | 'synthetic';

/** The tier in reader's words (DESIGN.md: source notes and tables). */
export const TIER_WORDS: Record<Tier, string> = {
  empirical: 'Measured',
  modeled: 'Modeled',
  proxy: 'Proxy',
  synthetic: 'Synthetic'
};

/**
 * Map a Riprap doc_id (e.g. "mta_entrance_56", "nycha_dev_239",
 * "dep_extreme", "sandy", "syn_sar_20250914") to its epistemic tier.
 *
 * Empirical = direct measurement. Modeled = scenario predictions.
 * Proxy = indirect indicator. Synthetic = generated/not observed.
 */
export function tierForDocId(docId: string): Tier {
  const id = docId.toLowerCase();
  if (id.startsWith('syn') || id.includes('synthetic')) return 'synthetic';
  if (id.startsWith('sandy') || id.startsWith('floodnet') || id.startsWith('usgs') ||
      id.startsWith('mta_entrance') || id.startsWith('nycha_dev') ||
      id.startsWith('doe_school') || id.startsWith('doh_hospital') ||
      id.startsWith('ida_hwm') || id.startsWith('hwm') || id.startsWith('noaa') ||
      id.startsWith('nws_obs') || id.startsWith('dcp_floodplain')) return 'empirical';
  if (id.startsWith('dep') || id.startsWith('fema_firm') || id.startsWith('npcc') ||
      id.startsWith('wrp') || id.includes('scenario') || id.includes('forecast') ||
      id.startsWith('nws_alert')) return 'modeled';
  if (id.startsWith('nyc311') || id.startsWith('311') || id.startsWith('nfip') ||
      id.startsWith('dob') || id.startsWith('hand') ||
      id.startsWith('twi') || id.startsWith('microtopo')) return 'proxy';
  return 'proxy';
}
