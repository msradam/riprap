/**
 * Landing copy that quotes the gallery. Every quote is the snapshot's own
 * text with its `[doc_id]` markers removed; tests/unit/landing.test.ts
 * fails when a gallery rebuild changes one, so the card is updated from
 * the new snapshot instead of going stale.
 */

/** A question chip: the label is shortened, the live query is the
 *  entry's own question (or its place, after "heat" for a bare heat
 *  entry: `liveQuery`), so the live app answers what the gallery shows. */
export interface Chip {
  label: string;
  slug: string;
}

export const CHIPS: Chip[] = [
  { label: 'Has 90-01 183rd Street, Queens flooded since Ida?', slug: 'hollis-since-ida' },
  { label: 'How many street flooding complaints has QN12 had?', slug: 'qn12-complaints' },
  { label: 'Which NYCHA developments in BK06 lie in the Sandy extent?', slug: 'bk06-nycha' },
  { label: 'A whole district: QN12', slug: 'qn12' },
  { label: 'Will it be dangerously hot this week at 90-01 183rd Street, Queens?', slug: 'hollis-heat-week' },
  { label: 'Heat in a whole district: QN12', slug: 'qn12-heat' }
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
  /** Riprap's own words about the entry, set under the quotes and outside
   *  the quotation: what the place is, when the figure could mislead. */
  note?: string;
}

/** The proof cards, the district card first. The heat quotes are
 *  sentences a gallery rebuild keeps: figures from fixed files (the
 *  Landsat images, the 2023 index) and phrases set by code. */
export const PROOF: Proof[] = [
  {
    slug: 'qn12',
    kind: 'A whole district',
    figure: {
      text: '17 of 36',
      label: 'QN12 subway entrances in a rainfall flooding category of the city\'s modelled stormwater map "Extreme Flood (3.66 inches/hr) with 2080 Sea Level Rise"',
      from: '36 MTA subway entrances in this area (each entrance read at its own point on the maps, with no buffer): 0 inside the 2012 Sandy inundation extent and 17 inside the DEP stormwater map "Extreme Flood (3.66 inches/hr) with 2080 Sea Level Rise", a modelled scenario (17 in a rainfall flooding category and 0 in its future high tides category, which is coastal tidal inundation projected for 2080 and not rainfall flooding).'
    },
    quotes: [
      '36 MTA subway entrances in this area (each entrance read at its own point on the maps, with no buffer): 0 inside the 2012 Sandy inundation extent and 17 inside the DEP stormwater map "Extreme Flood (3.66 inches/hr) with 2080 Sea Level Rise", a modelled scenario (17 in a rainfall flooding category and 0 in its future high tides category, which is coastal tidal inundation projected for 2080 and not rainfall flooding).',
      'Jamaica Center-Parsons/Archer (E J Z), Jamaica-179 St (F), Parsons Blvd (F), Sutphin Blvd (F), Sutphin Blvd-Archer Av-JFK Airport (E J Z)',
      'In a rainfall flooding category of the modelled "Extreme Flood (3.66 inches/hr) with 2080 Sea Level Rise" map: I.S. 059 Springfield Gardens'
    ]
  },
  {
    slug: 'bk06-nycha',
    kind: 'Public housing in a district',
    figure: {
      text: '2',
      label: 'BK06 public housing developments inside the 2012 Sandy inundation extent',
      from: '2 inside the 2012 Sandy inundation extent and 0 inside the DEP stormwater map "Extreme Flood (3.66 inches/hr) with 2080 Sea Level Rise", a modelled scenario'
    },
    quotes: [
      '2 inside the 2012 Sandy inundation extent and 0 inside the DEP stormwater map "Extreme Flood (3.66 inches/hr) with 2080 Sea Level Rise", a modelled scenario',
      'Inside the 2012 Sandy extent: RED HOOK EAST, RED HOOK WEST'
    ]
  },
  {
    slug: 'hunts-point-311',
    kind: 'A No about reports, not about flooding',
    figure: {
      text: 'No.',
      label: 'No complaint was filed. That is not a finding that the place stays dry.',
      from: 'No. 0 NYC 311 flood and sewer complaints'
    },
    quotes: [
      '0 NYC 311 flood and sewer complaints filed within 200 m of this location in the last 5 years (since 2021-10-06; the 311 service answered and none matched).',
      'A count of complaints is a count of reports filed, not of floods: a low count can mean under-reporting and not the absence of flooding, because the propensity to file a 311 request varies with income, language and demographics'
    ],
    note: 'The address is in the Hunts Point wholesale food markets, not on a residential block.'
  },
  {
    slug: 'gowanus-2050',
    kind: 'A city scenario for 2050',
    quotes: [
      'The city\'s stormwater flood map "Moderate Flood (2.13 inches/hr) with 2050 Sea Level Rise" shows the category "Future High Tides 2050" (coastal tidal inundation, not rainfall flooding; at the edge of the mapped flooding (within about 3 m)) at the point mapped for this address.'
    ]
  },
  {
    slug: 'brooklyn-heights-sensors',
    kind: 'When the record is empty',
    quotes: ['No FloodNet sensors deployed within 600 m of this address.']
  },
  {
    slug: 'hunts-point-heat',
    kind: 'Heat at a wholesale market address',
    figure: {
      text: '12.4°F',
      label: "warmer than the city's land average within 150 m of 355 Food Center Drive: the surface of the ground, not the air",
      from: "The surface of the ground within 150 m of this address ran 12.4°F warmer than the city's land average over 18 clear summer Landsat images (surface temperature, not air temperature)."
    },
    quotes: [
      "The surface of the ground within 150 m of this address ran 12.4°F warmer than the city's land average over 18 clear summer Landsat images (surface temperature, not air temperature).",
      "Its neighbourhood, Hunts Point, scores 5 out of 5 on the Health Department's Heat Vulnerability Index, a rank among neighbourhoods and not a measurement."
    ],
    note: 'The address is in the Hunts Point wholesale food markets, where most of the ground is paved or roofed. The figure is for that ground, not for the neighbourhood where people live.'
  },
  {
    slug: 'hollis-heat-week',
    kind: "A forecast, quoted as the Weather Service's",
    quotes: [
      'From the National Weather Service, as issued for the next 7 days; Riprap predicts nothing itself',
      'The Weather Service wrote this for an area; it is not a prediction for a building.'
    ]
  }
];

/** The gallery entry the hero sets as its specimen answer. */
export const SPECIMEN_SLUG = 'hollis-since-ida';

/** A briefing's Answer section as the hero shows it: `lead` is a yes, no
 *  or partly that opens it (or null), and `paras` holds the sentences with
 *  their `[doc_id]` markers removed, one paragraph per run of sentences
 *  from one source. Words after the last marker are kept. */
export function specimenAnswer(paragraph: string): { lead: string | null; paras: string[] } {
  const answer = /\*\*Answer\.\*\*\s*([^]*?)(?:\n\n|$)/.exec(paragraph)?.[1] ?? '';
  const lead = /^(Yes|No|Partly)\.\s+/.exec(answer);
  const bits = answer.slice(lead?.[0].length ?? 0).split(/ \[([a-z][a-z0-9_, ]*)\]\./);
  const paras: string[] = [];
  let last: string | undefined;
  for (let i = 0; i < bits.length; i += 2) {
    const text = bits[i].trim();
    if (!text) continue;
    const id = bits[i + 1];
    const sentence = id ? `${text}.` : text;
    if (paras.length && (id ?? last) === last) paras[paras.length - 1] += ` ${sentence}`;
    else paras.push(sentence);
    last = id ?? last;
  }
  return { lead: lead?.[1] ? `${lead[1]}.` : null, paras };
}
