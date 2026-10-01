/**
 * Landing components. These are exempted from the NYC-leak audit because
 * they intentionally name shipped cities as features. These tests assert
 * they mount and render the city list, the Stones, the official sources and
 * the plain statements, with no stat row, badge row or numbered cards.
 */
import { describe, it, expect } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import LandHero from '$lib/components/landing/LandHero.svelte';
import LandProof from '$lib/components/landing/LandProof.svelte';
import LandStones from '$lib/components/landing/LandStones.svelte';
import LandFor from '$lib/components/landing/LandFor.svelte';
import LandDevelopers from '$lib/components/landing/LandDevelopers.svelte';
import LandFrontier from '$lib/components/landing/LandFrontier.svelte';
import LandCollab from '$lib/components/landing/LandCollab.svelte';
import UseBand from '$lib/components/landing/UseBand.svelte';
import { load } from '../../../src/routes/+page.server';

const data = await load();
const heroProps = { chips: data.chips, specimen: data.specimen, count: data.count };
const text = (el: Element) => (el.textContent ?? '').replace(/\s+/g, ' ');

describe('Landing smoke', () => {
  it('LandHero links each chip to the live query the gallery entry answers', () => {
    const { getByRole } = render(LandHero, heroProps);
    const chips = getByRole('list', { name: 'Try a real question' });
    const hrefs = [...chips.querySelectorAll('a')].map((a) => decodeURIComponent(a.getAttribute('href') ?? ''));
    expect(hrefs).toEqual([
      '/q/Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?',
      '/q/How many street flooding complaints has community district QN12 had?',
      '/q/Which NYCHA developments in Brooklyn Community District 6 lie inside the 2012 Sandy inundation area?',
      '/q/QN12'
    ]);
  });

  it('LandHero has one h1, and sets the specimen as a figure after the form, with its citation mark linked to its source note', () => {
    const { container } = render(LandHero, heroProps);
    expect([...container.querySelectorAll('h1')].map((h) => h.textContent)).toEqual([
      'The flood record for any New York City block, cited line by line.'
    ]);
    const form = container.querySelector('form[role=search]')!;
    const figure = container.querySelector('figure')!;
    expect(form.compareDocumentPosition(figure) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // The question is a paragraph, not a heading.
    expect(figure.querySelector('h1, h2, h3')).toBeNull();
    expect(text(figure)).toContain('Yes.');
    const mark = figure.querySelector('a.inline-cite')!;
    expect(mark.getAttribute('href')).toBe('#cite-floodnet');
    expect(figure.querySelector('#cite-floodnet')).not.toBeNull();
    expect(figure.querySelectorAll('.source-note')).toHaveLength(3);
    expect(figure.querySelector('a[href="/gallery/hollis-since-ida/"]')?.textContent).toBe('Read the full briefing');
  });

  it('LandProof sets the district card first, then each question as a linked h3 with its quote and date', () => {
    const { container } = render(LandProof, { cards: data.proof, count: data.count });
    expect(container.querySelector('h2')?.textContent).toBe('Real questions, answered from the record');
    const cards = [...container.querySelectorAll('li.land-card')];
    expect(cards).toHaveLength(5);
    expect(cards[0].classList).toContain('is-wide');
    expect(text(cards[0])).toContain('17 of 36');
    const heads = cards.map((c) => c.querySelector('h3 a')!);
    expect(heads.map((a) => a.getAttribute('href'))).toEqual([
      '/gallery/qn12/',
      '/gallery/bk06-nycha/',
      '/gallery/hunts-point-311/',
      '/gallery/gowanus-2050/',
      '/gallery/brooklyn-heights-sensors/'
    ]);
    expect(text(heads[1])).toBe(
      'Which NYCHA developments in Brooklyn Community District 6 lie inside the 2012 Sandy inundation area?'
    );
    expect(text(cards[1])).toContain('Inside the 2012 Sandy extent: RED HOOK EAST, RED HOOK WEST');
    for (const c of cards) expect(c.querySelector('time')?.getAttribute('datetime')).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(text(container)).toContain(`See all ${data.count} briefings in the gallery`);
  });

  it('LandCollab names every shipped city and links one sample address each on the live build', () => {
    const { container } = render(LandCollab);
    for (const city of ['NYC', 'Chicago', 'Seattle', 'Albany']) {
      expect(text(container), `LandCollab missing ${city}`).toContain(city);
    }
    expect(container.querySelectorAll('a[href^="/q/"]')).toHaveLength(4);
    const email = [...container.querySelectorAll('a')].filter((a) => a.textContent === 'Email the author');
    expect(email.map((a) => a.getAttribute('href'))).toEqual([
      'mailto:msrahmanadam@gmail.com?subject=Riprap',
      'mailto:msrahmanadam@gmail.com?subject=Riprap'
    ]);
    expect(container.querySelector('a[href="https://github.com/msradam/riprap/issues/new/choose"]')?.textContent).toBe('Open an issue');
  });

  it('UseBand says evidence, not advice, and links the official sources it works alongside', () => {
    const { container } = render(UseBand);
    expect([...container.querySelectorAll('h2')].map((h) => h.textContent)).toEqual([
      'Riprap reports evidence, not advice.'
    ]);
    expect([...container.querySelectorAll('dd a')].map((a) => a.getAttribute('href'))).toEqual([
      'https://dataviz.floodnet.nyc/',
      'https://www.weather.gov/okx/',
      'https://a858-nycnotify.nyc.gov/',
      'https://msc.fema.gov/portal/home',
      'https://www.floodhelpny.org/',
      'https://communityprofiles.planning.nyc.gov/',
      'https://rebuildbydesign.org/rainproof-nyc-map/'
    ]);
    expect(text(container)).toContain('Not affiliated with FEMA, NOAA, USGS or the City of New York.');
  });

  it('LandFor names four readers, each with an example', () => {
    const { container } = render(LandFor);
    expect(container.querySelector('h2')?.textContent).toBe('Made for people who have to cite it');
    expect([...container.querySelectorAll('h3')].map((h) => h.textContent)).toEqual([
      'Reporters and data desks',
      'Community boards and council offices',
      'Resilience analysts and planners',
      'Researchers and civic technologists'
    ]);
    expect([...container.querySelectorAll('a')].map((a) => a.getAttribute('href'))).toEqual([
      '/gallery/hollis-since-ida/',
      '/gallery/qn12/',
      '/gallery/bk06-nycha/',
      '#developers'
    ]);
  });

  it('says the three experimental models are there, labelled experimental, each with a baseline', () => {
    const { container } = render(LandFrontier);
    expect(text(container)).toContain('labelled experimental, with their tested accuracy in every sentence');
    expect(container.querySelectorAll('h3')).toHaveLength(3);
    expect([...container.querySelectorAll('.exp-badge')].map((b) => b.textContent)).toEqual([
      'Experimental',
      'Experimental',
      'Experimental'
    ]);
    expect([...container.querySelectorAll('dt')].filter((d) => d.textContent === 'The open problem')).toHaveLength(3);
  });

  it('LandDevelopers has the anchor the reader cards use, a keyboard-scrollable code block and the seven MCP tools', () => {
    const { container } = render(LandDevelopers);
    expect(container.querySelector('section')?.id).toBe('developers');
    const pre = container.querySelector('pre')!;
    expect(pre).toHaveAttribute('tabindex', '0');
    expect(pre).toHaveAttribute('aria-label', 'Commands to run Riprap and query it');
    expect(pre.textContent).toContain('uv run riprap-mcp');
    expect(container.querySelectorAll('.dev-tools li')).toHaveLength(7);
  });

  it('LandStones names all five Stones, with its sources, at #methodology', () => {
    const { container } = render(LandStones);
    expect(container.querySelector('section')?.id).toBe('methodology');
    expect(container.querySelector('h2')?.textContent).toBe('Built on 23 public sources');
    const t = text(container);
    for (const name of ['Cornerstone', 'Touchstone', 'Keystone', 'Lodestone', 'Capstone']) {
      expect(t).toContain(name);
    }
    expect(container.querySelectorAll('dt')).toHaveLength(5);
    expect(t).toContain('USGS Hurricane Ida high-water marks');
  });
});

describe('LandHero empty submit', () => {
  const HINT = 'Type an address, a community district such as QN12, or a question.';

  it('focuses the input and shows the hint in a status region, then clears it on typing', async () => {
    const { container, getByRole } = render(LandHero, heroProps);
    const input = getByRole('textbox') as HTMLInputElement;
    const status = container.querySelector('#land-query-hint');
    expect(status).toHaveAttribute('role', 'status');
    expect(status).toBeEmptyDOMElement();

    await fireEvent.submit(container.querySelector('form[role=search]')!);
    expect(status).toHaveTextContent(HINT);
    expect(document.activeElement).toBe(input);
    expect(input).toHaveAttribute('aria-describedby', 'land-query-hint');
    expect(input).not.toHaveAttribute('required');
    expect(getByRole('button', { name: 'Get the briefing' })).toBeEnabled();

    await userEvent.type(input, 'Q');
    expect(status).toBeEmptyDOMElement();
    expect(input).not.toHaveAttribute('aria-describedby');
  });
});
