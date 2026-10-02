/** Runnable example queries, one per kind of input the backend accepts.
 *  All four are in New York City, the production deployment. Districts
 *  are written QN12; the resolver also accepts "QN 12" and other forms.
 *  Shared by the landing Try list and the error card. */
export const SAMPLE_ADDRESS = '90-01 183rd Street, Queens';

export const EXAMPLES = [
  { kind: 'Address', q: SAMPLE_ADDRESS },
  { kind: 'Question', q: 'How many flooding complaints near 2017 East 17th Street, Brooklyn?' },
  { kind: 'District', q: 'QN12' },
  { kind: 'Heat', q: 'heat QN12' },
];
