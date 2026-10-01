/**
 * Landing copy that quotes the gallery. Every quote is the snapshot's own
 * text with its `[doc_id]` markers removed; tests/unit/landing.test.ts
 * fails when a gallery rebuild changes one, so the card is updated from
 * the new snapshot instead of going stale.
 */

/** A question chip: the label is shortened, the live query is the
 *  entry's own question (or address), so the live app answers what the
 *  gallery shows. */
export interface Chip {
  label: string;
  slug: string;
}

export const CHIPS: Chip[] = [
  { label: 'Has 90-01 183rd Street, Queens flooded since Ida?', slug: 'hollis-since-ida' },
  { label: 'How many street flooding complaints has QN12 had?', slug: 'qn12-complaints' },
  { label: 'Which NYCHA developments in BK06 lie in the Sandy extent?', slug: 'bk06-nycha' },
  { label: 'A whole district: QN12', slug: 'qn12' }
];

/** A figure set large on a card, with the snapshot text it is read from:
 *  `from` appears verbatim in the briefing and holds every number in
 *  `text` (or, for a word such as "No.", starts with it). */
export interface ProofFigure {
  text: string;
  label?: string;
  from: string;
}

export interface Proof {
  slug: string;
  kind: string;
  quotes: string[];
  figure?: ProofFigure;
}

/** The proof cards, the district card first. */
export const PROOF: Proof[] = [
  {
    slug: 'qn12',
    kind: 'A whole district, named',
    figure: {
      text: '17 of 36',
      label: "QN12 subway entrances inside the city's 2080 extreme stormwater scenario",
      from: '36 MTA subway entrances in this area: 0 inside the 2012 Sandy inundation extent and 17 inside the DEP extreme stormwater scenario (2080 sea-level rise).'
    },
    quotes: [
      '36 MTA subway entrances in this area: 0 inside the 2012 Sandy inundation extent and 17 inside the DEP extreme stormwater scenario (2080 sea-level rise).',
      'Jamaica Center-Parsons/Archer (E J Z), Jamaica-179 St (F), Parsons Blvd (F), Sutphin Blvd (F), Sutphin Blvd-Archer Av-JFK Airport (E J Z)',
      'Inside the DEP extreme scenario (2080 sea-level rise): I.S. 059 Springfield Gardens'
    ]
  },
  {
    slug: 'bk06-nycha',
    kind: 'Public housing, by name',
    quotes: ['Inside the 2012 Sandy extent: RED HOOK EAST, RED HOOK WEST']
  },
  {
    slug: 'hunts-point-311',
    kind: 'A yes or no, from the record',
    figure: { text: 'No.', from: 'No. 0 NYC 311 flood-related complaints' },
    quotes: [
      '0 NYC 311 flood-related complaints filed within 200 m of this location in the last 5 years (the 311 service answered and none matched).'
    ]
  },
  {
    slug: 'gowanus-2050',
    kind: 'A city scenario for 2050',
    quotes: [
      "This address is inside the future high tide area of the NYC DEP stormwater scenario (2.13 in/hr, 2050 SLR): coastal tidal inundation projected for 2050, not the scenario's rainfall flooding."
    ]
  },
  {
    slug: 'brooklyn-heights-sensors',
    kind: 'Silence, stated',
    quotes: ['No FloodNet sensors deployed within 600 m of this address.']
  }
];

/** The gallery entry the hero sets as its specimen answer. */
export const SPECIMEN_SLUG = 'hollis-since-ida';
