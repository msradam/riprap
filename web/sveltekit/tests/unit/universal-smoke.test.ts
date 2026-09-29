/**
 * Universal smoke — every component listed below must mount and emit
 * non-empty rendered output under happy-dom without throwing. Catches
 * the class of bug where a Svelte 5 rune or import path crash makes a
 * whole region of the UI dark; the per-component tests assert
 * content, this one is the floor.
 *
 * Adding a new component to src/lib/components/ should mean adding a
 * row here too. The test list is intentionally maintained by hand:
 * each entry pins what the minimal valid props look like, which is
 * itself a contract.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render } from '@testing-library/svelte';
import type { Component } from 'svelte';
import { resetStores, seedForCity } from './helpers/stores';
import { BOSTON } from './fixtures/cities';

// Shell
import AppHeader from '$lib/components/shell/AppHeader.svelte';
import AppFooter from '$lib/components/shell/AppFooter.svelte';
import StatusPill from '$lib/components/shell/StatusPill.svelte';
import RipMark from '$lib/components/shell/RipMark.svelte';
import SkipLink from '$lib/components/shell/SkipLink.svelte';
// Briefing
import AnswerProse from '$lib/components/briefing/AnswerProse.svelte';
import SourceNotes from '$lib/components/briefing/SourceNotes.svelte';
import SourceList from '$lib/components/briefing/SourceList.svelte';
import SourcesChecked from '$lib/components/briefing/SourcesChecked.svelte';
import MapFigure from '$lib/components/briefing/MapFigure.svelte';
import EvidenceTable from '$lib/components/briefing/EvidenceTable.svelte';
import HowMade from '$lib/components/briefing/HowMade.svelte';
import ProvenanceTrace from '$lib/components/findings/ProvenanceTrace.svelte';
import { RunState } from '$lib/client/runState.svelte';
import { briefingModel } from '$lib/client/briefingModel';
// States
import ErrorCard from '$lib/components/states/ErrorCard.svelte';
import SkeletonBriefing from '$lib/components/states/SkeletonBriefing.svelte';
// Glyphs
import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
import EvidenceMark from '$lib/components/glyphs/EvidenceMark.svelte';

const CITATION = {
  id: 'sandy', n: 1, tier: 'empirical' as const, source: 'Open Data', title: 'Inundation extent',
  docId: 'sandy', url: 'https://example.org', vintage: '2015-11-09', retrieved: '2026-01-01'
};

interface SmokeCase {
  name: string;
  Component: Component<any>;  // eslint-disable-line @typescript-eslint/no-explicit-any
  props: Record<string, unknown>;
}

const CASES: SmokeCase[] = [
  // Shell
  { name: 'AppHeader',         Component: AppHeader,         props: { queryId: 'test-q' } },
  { name: 'AppFooter',         Component: AppFooter,         props: {} },
  { name: 'StatusPill',        Component: StatusPill,        props: {} },
  { name: 'RipMark',           Component: RipMark,           props: {} },
  { name: 'SkipLink',          Component: SkipLink,          props: {} },

  // Briefing
  { name: 'AnswerProse',       Component: AnswerProse,
    props: { parts: [{ text: 'Outside the extent.', cite: 'sandy' }], citations: { sandy: CITATION } } },
  { name: 'SourceNotes',       Component: SourceNotes,
    props: { citations: [CITATION], label: 'Sources for the answer' } },
  { name: 'SourceList',        Component: SourceList,
    props: { citations: [CITATION], noted: [] } },
  { name: 'SourcesChecked',    Component: SourcesChecked,
    props: { lists: { consulted: [], hasConsultedList: true, noData: [], notChecked: [] } } },
  { name: 'MapFigure',         Component: MapFigure,
    props: { run: new RunState() } },
  { name: 'EvidenceTable',     Component: EvidenceTable,
    props: { groups: [], findings: new Map(), citations: {}, notRun: [], labelledby: 'x' } },
  { name: 'HowMade',           Component: HowMade,
    props: { model: briefingModel(new RunState(), 'test'), stones: [] } },
  { name: 'ProvenanceTrace',   Component: ProvenanceTrace,
    props: { members: [{ id: 'sandy', name: 'Sandy extent', status: 'fired' as const }] } },

  // States
  { name: 'ErrorCard',         Component: ErrorCard,
    props: { state: 'geocoder' } },
  { name: 'SkeletonBriefing',  Component: SkeletonBriefing,  props: {} },

  // Glyphs
  { name: 'TierGlyph',         Component: TierGlyph,
    props: { tier: 'empirical' as const, size: 11, color: 'var(--tier-empirical)' } },
  { name: 'EvidenceMark',      Component: EvidenceMark,
    props: { tier: 'empirical' as const, size: 11 } },
];

beforeEach(() => {
  resetStores();
  // Most components read from the stores (deployment, pebbleManifest);
  // seeding Boston is the strictest test — non-NYC + non-trivial
  // manifest means a component reaching for a hardcoded NYC string
  // is more likely to fail.
  seedForCity(BOSTON);
});

describe('Universal smoke: every shipped component mounts under happy-dom', () => {
  it.each(CASES.map((c) => [c.name, c] as const))(
    '%s mounts without throwing',
    (_name, c) => {
      let result = null as { container: HTMLElement } | null;
      expect(() => {
        result = render(c.Component, { props: c.props });
      }).not.toThrow();
      // Even an "empty" component should produce SOME DOM (a wrapping
      // element, an aria-live region, etc.). Catches the case where a
      // component throws silently and renders nothing.
      expect(result?.container?.firstChild,
        `${c.name} rendered no DOM`,
      ).not.toBeNull();
    },
  );
});
