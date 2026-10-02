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
    const chips = getByRole('list', { name: 'Try a real question or place' });
    const hrefs = [...chips.querySelectorAll('a')].map((a) => decodeURIComponent(a.getAttribute('href') ?? ''));
    expect(hrefs).toEqual([
      '/q/Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?',
      '/q/How many street flooding complaints has community district QN12 had?',
      '/q/Which NYCHA developments in Brooklyn Community District 6 lie inside the 2012 Sandy inundation area?',
      '/q/QN12',
      '/q/Will it be dangerously hot this week at 90-01 183rd Street, Queens?',
      // A bare heat entry runs as "heat <place>"; the place alone is the flood briefing.
      '/q/heat QN12'
    ]);
  });

  it('LandHero has one h1, and sets the specimen as a figure after the form: one link to the briefing, its question as text', () => {
    const { container, getByRole } = render(LandHero, heroProps);
    expect([...container.querySelectorAll('h1')].map((h) => h.textContent)).toEqual([
      'The flood and heat record for any New York City block, cited line by line.'
    ]);
    const form = container.querySelector('form[role=search]')!;
    const figure = container.querySelector('figure')!;
    expect(form.compareDocumentPosition(figure) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // The question is text, not a heading.
    expect(figure.querySelector('h1, h2, h3')).toBeNull();
    // The window is one link to the briefing; its image has a fixed size and no fetch priority,
    // so on phones, where it sits below the actions, it does not jump ahead of the fonts.
    const win = figure.querySelector('a.window')!;
    expect(win.getAttribute('href')).toBe('/gallery/hollis-since-ida/');
    const img = win.querySelector('img')!;
    expect(img.getAttribute('src')).toBe('/landing/hero-briefing.webp');
    expect(img.getAttribute('srcset')).toBe('/landing/hero-briefing-712.webp 712w, /landing/hero-briefing.webp 1424w');
    expect(img.getAttribute('alt')).toMatch(/^The Riprap briefing for this question: the answer Yes\./);
    expect([img.getAttribute('width'), img.getAttribute('height')]).toEqual(['712', '1400']);
    expect(img.hasAttribute('fetchpriority')).toBe(false);
    expect(img.getAttribute('decoding')).toBe('async');
    // The first frame, as prerendered: the bar reads riprap and the box is empty.
    expect(text(win.querySelector('.window-bar')!)).toBe('riprap');
    // The typed question is a picture; the link's name carries the question and the image alt.
    const search = win.querySelector('.search')!;
    expect(search).toHaveAttribute('aria-hidden', 'true');
    expect(text(search.querySelector('.typed')!)).toBe('');
    expect(search.querySelector('a, button, input, [tabindex]')).toBeNull();
    const link = getByRole('link', { name: new RegExp(`^${data.specimen.question.replace(/[?.]/g, '\\$&')} The Riprap briefing for this question`) });
    expect(link).toBe(win);
    // The caption is the link alone.
    const caption = figure.querySelector('figcaption')!;
    expect([...caption.children].map((c) => [c.tagName, c.classList.contains('land-link'), c.getAttribute('href'), c.textContent])).toEqual([
      ['A', true, '/gallery/hollis-since-ida/', 'Read the full briefing']
    ]);
  });

  it('LandProof sets the district card first, then each question as a linked h3 with its quote and date', () => {
    const { container } = render(LandProof, { cards: data.proof, count: data.count });
    expect(container.querySelector('h2')?.textContent).toBe('Real questions, answered from the record');
    const cards = [...container.querySelectorAll('li.land-card')];
    expect(cards).toHaveLength(7);
    expect(cards[0].classList).toContain('is-wide');
    expect(text(cards[0])).toContain('17 of 36');
    const heads = cards.map((c) => c.querySelector('h3 a')!);
    expect(heads.map((a) => a.getAttribute('href'))).toEqual([
      '/gallery/qn12/',
      '/gallery/bk06-nycha/',
      '/gallery/hunts-point-311/',
      '/gallery/gowanus-2050/',
      '/gallery/brooklyn-heights-sensors/',
      '/gallery/hunts-point-heat/',
      '/gallery/hollis-heat-week/'
    ]);
    // The heat figure is a surface temperature, and its label says so.
    expect(text(cards[5])).toContain('12.2°F');
    expect(text(cards[5].querySelector('.proof-figure-label')!)).toContain('not the air');
    expect(text(cards[6])).toContain('Riprap predicts nothing itself');
    expect(text(heads[1])).toBe(
      'Which NYCHA developments in Brooklyn Community District 6 lie inside the 2012 Sandy inundation area?'
    );
    expect(text(cards[1])).toContain('Inside the 2012 Sandy extent: RED HOOK EAST, RED HOOK WEST');
    for (const c of cards) expect(c.querySelector('time')?.getAttribute('datetime')).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(text(container)).toContain(`See all ${data.count} briefings in the gallery`);
    // Who it is for: one sentence, no second link to a proof briefing.
    const forLine = container.querySelector('.proof-for')!;
    expect(text(forLine)).toMatch(/^ ?Made for people who have to cite it: reporters/);
    expect(text(forLine)).toContain('in one printable briefing');
    expect([...forLine.querySelectorAll('a')].map((a) => a.getAttribute('href'))).toEqual(['#developers']);
  });

  it('LandCollab names every shipped city and links one sample address each on the live build', () => {
    const { container } = render(LandCollab);
    for (const city of ['NYC', 'Chicago', 'Seattle', 'Albany']) {
      expect(text(container), `LandCollab missing ${city}`).toContain(city);
    }
    expect(container.querySelectorAll('a[href^="/q/"]')).toHaveLength(4);
    // Each action once: the author's address, the issue tracker and each guide.
    const hrefs = [...container.querySelectorAll('a')].map((a) => a.getAttribute('href'));
    expect(new Set(hrefs).size).toBe(hrefs.length);
    const email = [...container.querySelectorAll('a[href^="mailto:"]')];
    expect(email.map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
      ['Email Adam', 'mailto:msrahmanadam@gmail.com?subject=Riprap']
    ]);
    expect(container.querySelector('a[href="https://github.com/msradam/riprap/issues/new/choose"]')?.textContent).toBe('Open an issue');
    expect(text(container)).toContain('Riprap is built by Adam Munawar Rahman, open source under Apache-2.0.');
  });

  it('UseBand says evidence, not advice, in one line that links the official sources it works alongside', () => {
    const { container } = render(UseBand);
    expect(container.querySelectorAll('p')).toHaveLength(1);
    expect(container.querySelector('p strong')?.textContent).toBe('Riprap reports evidence, not advice.');
    expect([...container.querySelectorAll('p a')].map((a) => a.getAttribute('href'))).toEqual([
      'https://dataviz.floodnet.nyc/',
      'https://www.weather.gov/okx/',
      'https://a858-nycnotify.nyc.gov/',
      'https://msc.fema.gov/portal/home',
      'https://www.floodhelpny.org/',
      'https://communityprofiles.planning.nyc.gov/',
      'https://www.nyc.gov/health',
      'https://www.weather.gov/safety/heat',
      'https://finder.nyc.gov/coolingcenters',
      'https://rebuildbydesign.org/rainproof-nyc-map/'
    ]);
    expect(text(container)).toContain('Not affiliated with FEMA, NOAA, USGS or the City of New York.');
  });

  it('says the two experimental models are there, labelled experimental, each with a baseline, and that the satellite water layer was retired', () => {
    const { container } = render(LandFrontier);
    expect(text(container)).toContain(
      'Each is labelled experimental, states its tested accuracy in every sentence, and has a measured baseline to beat.'
    );
    expect(text(container)).not.toContain('days and years ahead');
    expect(text(container)).toContain(
      "it reads a typical district's paved share 1.7 points above the city's own 2021 map"
    );
    expect(text(container)).not.toContain('WorldCover');
    expect(text(container)).toContain('I fine-tuned two open models for New York');
    expect([...container.querySelectorAll('h3')].map((h) => h.textContent)).toEqual([
      'Storm surge at the Battery',
      'Paved, green and tree canopy'
    ]);
    expect([...container.querySelectorAll('.exp-badge')].map((b) => b.textContent)).toEqual(['Experimental', 'Experimental']);
    expect([...container.querySelectorAll('dt')].filter((d) => d.textContent === 'The open problem')).toHaveLength(2);
    // The city's map is the record; the model's estimate comes after it.
    expect(text(container)).toContain("A briefing quotes that map first, and the model's estimate follows it.");
    // The retired layer: one sentence, no card and no gallery link.
    expect(text(container.querySelector('.frontier-retired')!)).toMatch(
      /A third model, a satellite water layer, was retired on 2026-10-02 after two tests.*no more often than chance\./
    );
    expect(text(container)).not.toContain('Prithvi');
    const hrefs = [...container.querySelectorAll('a')].map((a) => a.getAttribute('href'));
    expect(hrefs).not.toContain('/gallery/bk18-satellite/');
    expect(hrefs).toContain('https://github.com/msradam/riprap/blob/main/docs/MODELS.md');
  });

  it('LandDevelopers has the anchor the readers line uses, a captioned keyboard-scrollable code block and the seven MCP tools', () => {
    const { container } = render(LandDevelopers);
    expect(container.querySelector('section')?.id).toBe('developers');
    const pre = container.querySelector('figure > pre')!;
    expect(pre).toHaveAttribute('tabindex', '0');
    // aria-label is prohibited on a pre (generic role); the figure's caption names the block.
    expect(pre).not.toHaveAttribute('aria-label');
    expect(container.querySelector('figure > figcaption')?.textContent).toBe('Commands to run Riprap and query it');
    const lines = pre.textContent!.split('\n');
    expect(lines).toContain('git clone https://github.com/msradam/riprap && cd riprap');
    expect(lines).toContain('git lfs install && git lfs pull');
    expect(lines.indexOf('git lfs install && git lfs pull')).toBeLessThan(lines.indexOf('uv run uvicorn web.main:app --port 7860'));
    expect(pre.textContent).toContain('uv run riprap-mcp');
    expect(container.querySelectorAll('.dev-tools li')).toHaveLength(7);
  });

  it('LandStones names all five Stones, with its sources, at #methodology', () => {
    const { container } = render(LandStones);
    expect(container.querySelector('section')?.id).toBe('methodology');
    expect(container.querySelector('h2')?.textContent).toBe('Built on 33 public sources');
    const t = text(container);
    for (const name of ['Cornerstone', 'Touchstone', 'Keystone', 'Lodestone', 'Capstone']) {
      expect(t).toContain(name);
    }
    expect(container.querySelectorAll('dt')).toHaveLength(5);
    // A plain label leads each row; the Stone's name is its tag.
    expect([...container.querySelectorAll('dt')].map((d) => [d.firstChild?.textContent?.trim(), d.querySelector('.stone-tag')?.textContent])).toEqual([
      ['Hazard maps and storm records', 'Cornerstone'],
      ['Places at risk', 'Keystone'],
      ['Live sensors and complaints', 'Touchstone'],
      ['Forecasts and projections', 'Lodestone'],
      ['How answers are written', 'Capstone']
    ]);
    expect(t).toContain('USGS Hurricane Ida high-water marks');
    // Each data Stone lists its heat sources on a line of their own.
    expect([...container.querySelectorAll('.stone-heat')].map((s) => s.textContent?.split(',')[0])).toEqual([
      'For heat: Landsat surface temperature',
      'For heat: NYC Parks spray showers and pools',
      'For heat: Weather station records of 90 degree days',
      'For heat: The National Weather Service forecast and heat alerts'
    ]);
    expect(t).toContain('FloodNet data is licensed CC-BY-NC-SA 4.0');
    expect(container.querySelector('.stones-licence a')?.getAttribute('href')).toBe(
      'https://github.com/msradam/riprap/blob/main/docs/DATA-SOURCES.md'
    );
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
