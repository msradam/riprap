/** Runnable example queries, one per kind of input the backend accepts.
 *  All three are in New York City, the production deployment. "QN 12"
 *  keeps its space: without it the no-LLM resolver does not match the
 *  district. Shared by the landing Try list and the error card. */
export const SAMPLE_ADDRESS = '90-01 183rd Street, Queens';

export const EXAMPLES = [
  { kind: 'Address', q: SAMPLE_ADDRESS },
  { kind: 'Question', q: 'How many flooding complaints near 2017 East 17th Street, Brooklyn?' },
  { kind: 'District', q: 'QN 12' },
];
