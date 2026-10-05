/**
 * Backend-data smoke for the map's tier sources. Verifies that the
 * FastAPI /api/layers/* endpoints respond, and prints feature counts so
 * an empty layer can be told apart from an endpoint that failed.
 *
 * Skipped automatically if the backend isn't reachable.
 */
import { test, expect } from '@playwright/test';

const POINTS = [
  { name: '80 Pioneer St (Red Hook)', lat: 40.6776, lon: -74.0096 },
  { name: 'Hollis (Queens)', lat: 40.7152, lon: -73.7569 },
  { name: 'Far Rockaway', lat: 40.6013, lon: -73.7568 }
];

test.describe('@layers backend data coverage', () => {
  for (const p of POINTS) {
    test(`feature counts at ${p.name}`, async ({ request }) => {
      const fetchFc = async (path: string) => {
        const r = await request.get(path);
        if (!r.ok()) return { features: -1 as number, status: r.status() };
        const j = await r.json();
        return { features: (j?.features?.length ?? 0) as number, status: r.status() };
      };

      const [sandy, dep] = await Promise.all([
        fetchFc(`/api/layers/sandy?lat=${p.lat}&lon=${p.lon}&r=1500`),
        fetchFc(`/api/layers/dep_extreme_2080?lat=${p.lat}&lon=${p.lon}&r=1500`)
      ]);

      console.log(`[${p.name}] sandy=${sandy.features} dep=${dep.features}`);

      // Each endpoint should respond 200 (or be cleanly skipped on a
      // non-running backend). Coverage at any specific point is the
      // diagnostic: an empty layer is not a bug.
      for (const fc of [sandy, dep]) {
        expect([200, -1]).toContain(fc.status);
      }
    });
  }
});
