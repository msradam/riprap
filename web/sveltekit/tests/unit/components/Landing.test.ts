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

  it('LandHero has one h1, and sets the specimen as a figure after the form: the saved answer as text, with no image', () => {
    const { container } = render(LandHero, heroProps);
    expect([...container.querySelectorAll('h1')].map((h) => h.textContent)).toEqual([
      'The flood and heat record for any New York City block, cited line by line.'
    ]);
    const form = container.querySelector('form[role=search]')!;
    const figure = container.querySelector('figure')!;
    expect(form.compareDocumentPosition(figure) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // The question is text, not a heading.
    expect(figure.querySelector('h1, h2, h3')).toBeNull();
    // The window is the snapshot's own answer as text: no screenshot that can go stale, and
    // no map of sensor or complaint points.
    const win = figure.querySelector('.window')!;
    expect(win.tagName).toBe('DIV');
    expect(figure.querySelector('img, canvas, svg')).toBeNull();
    const sheet = [...win.querySelectorAll('.sheet p')].map((p) => text(p).trim());
    expect(sheet[0]).toBe(data.specimen.question);
    expect(sheet.slice(-1)[0]).toMatch(new RegExp(`^Saved briefing of ${data.specimen.date}\\.`));
    for (const p of data.specimen.paras) expect(sheet).toContain(p);
    if (data.specimen.lead) expect(sheet[1]).toBe(data.specimen.lead);
    // The first frame, as prerendered: the bar reads riprap and the box is empty.
    expect(text(win.querySelector('.window-bar')!)).toBe('riprap');
    // The typed question is a picture, hidden from assistive technology; the sheet holds it as text.
    const search = win.querySelector('.search')!;
    expect(search).toHaveAttribute('aria-hidden', 'true');
    expect(text(search.querySelector('.typed')!)).toBe('');
    expect(win.querySelector('a, button, input, [tabindex]')).toBeNull();
    // The caption is the link and the control that stops the loop (WCAG 2.2.2).
    const caption = figure.querySelector('figcaption')!;
    expect([...caption.children].map((c) => [c.tagName, c.classList.contains('land-link'), c.getAttribute('href'), c.textContent?.trim()])).toEqual([
      ['A', true, '/gallery/hollis-since-ida/', 'Read the full briefing'],
      ['BUTTON', false, null, 'Pause the preview']
    ]);
  });

  it('LandHero lets a reader stop the moving preview and start it again', async () => {
    const { getByRole } = render(LandHero, heroProps);
    const pause = getByRole('button', { name: 'Pause the preview' });
    await fireEvent.click(pause);
    expect(pause.textContent?.trim()).toBe('Play the preview');
    expect(document.querySelector('.window')?.classList).toContain('paused');
    await fireEvent.click(pause);
    expect(document.querySelector('.window')?.classList).not.toContain('paused');
  });

  it('LandHero states who reads the question and where every sentence comes from', () => {
    const { container } = render(LandHero, heroProps);
    expect(text(container.querySelector('.hero-sub')!)).toContain(
      'Rules or an open Granite model read your question and choose the evidence. Every sentence you read comes word for word from a public record, with its source and date.'
    );
    expect(text(container)).not.toMatch(/no language model writes/i);
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
    expect(text(cards[5])).toContain('12.4°F');
    expect(text(cards[5].querySelector('.proof-figure-label')!)).toContain('not the air');
    expect(text(cards[6])).toContain('Riprap predicts nothing itself');
    expect(text(heads[1])).toBe(
      'Which NYCHA developments in Brooklyn Community District 6 lie inside the 2012 Sandy inundation area?'
    );
    // A card leads with its count and extent; the names of facilities come below it.
    const figure1 = cards[1].querySelector('.proof-figure')!;
    expect(text(figure1)).toMatch(/^ ?2 ?BK06 public housing developments inside the 2012 Sandy inundation extent/);
    const names = [...cards[1].querySelectorAll('.proof-quote p')].find((p) => text(p).includes('RED HOOK EAST'))!;
    expect(figure1.compareDocumentPosition(names) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // The No is about reports: the card carries the under-reporting caveat and says what the address is.
    expect(text(cards[2].querySelector('.land-kind')!)).toBe('A No about reports, not about flooding');
    expect(text(cards[2])).toContain('a low count can mean under-reporting and not the absence of flooding');
    expect(text(cards[2].querySelector('.proof-note')!)).toContain('wholesale food markets');
    expect(text(cards[5].querySelector('.proof-note')!)).toContain('not for the neighbourhood where people live');
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
    expect(container.querySelector('p strong')?.textContent).toBe('Riprap reports evidence, not advice.');
    expect([...container.querySelectorAll('p:first-child a')].map((a) => a.getAttribute('href'))).toEqual([
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
  });

  it('UseBand says Riprap is no alert service, where to go instead, and that it is independent of every publisher it reads', () => {
    const { container } = render(UseBand);
    const [, help, independent] = [...container.querySelectorAll('p')];
    expect(help.querySelector('strong')?.textContent).toBe('Riprap is not an alert or emergency service.');
    expect([...help.querySelectorAll('a')].map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
      ['Notify NYC', 'https://a858-nycnotify.nyc.gov/'],
      ['311', 'https://portal.311.nyc.gov/'],
      ['FloodHelpNY', 'https://www.floodhelpny.org/']
    ]);
    expect(text(independent)).toContain(
      'It is not endorsed by or affiliated with FloodNet, New York University, the City University of New York, FEMA, NOAA, USGS or the City of New York.'
    );
    expect(text(independent)).toContain('it is not a City product');
    expect(text(independent)).toContain('does not warrant its completeness, accuracy, content or fitness for any use');
  });

  it('shows the land-cover model as experimental and the surge forecast as a negative result, out of default briefings, with no gallery link', () => {
    const { container } = render(LandFrontier);
    const t = text(container);
    expect(t).toContain('One, a surge forecast, lost to its baseline and was taken out.');
    expect(t).not.toContain('has a measured baseline to beat');
    expect(t).not.toMatch(/11\.5 cm|13\.3 cm|635 four-day/);
    expect(t).toContain("it reads a typical district's paved share 1.7 points above The Nature Conservancy's 2021 map");
    expect(t).not.toContain("the city's own 2021 map");
    expect(t).not.toContain('WorldCover');
    expect([...container.querySelectorAll('h3')].map((h) => h.textContent)).toEqual([
      'Paved, green and tree canopy',
      'Storm surge at the Battery'
    ]);
    expect([...container.querySelectorAll('.exp-badge')].map((b) => b.textContent)).toEqual([
      'Experimental',
      'Negative result, off by default'
    ]);
    const surge = container.querySelectorAll('li.land-card')[1];
    expect(text(surge)).toContain('It is out of default briefings since 2026-10-05.');
    expect(text(surge)).toContain('On 639 held-out four-day windows');
    expect(text(surge)).toContain('Damped persistence, a one-line rule, scored 0.108 m and beats it.');
    expect(text(surge)).toContain('It foresaw 1 of the 23 windows that reached flood stage, which are 5 distinct events.');
    expect([...surge.querySelectorAll('a')].map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
      ['Corrected model card', 'https://github.com/msradam/riprap/blob/main/docs/model-cards/Granite-TTM-r2-Battery-Surge.md']
    ]);
    expect([...container.querySelectorAll('dt')].filter((d) => d.textContent === 'The open problem')).toHaveLength(2);
    // The city's map is the record; the model's estimate comes after it.
    expect(t).toContain("A briefing quotes that map first, and the model's estimate follows it.");
    // The retired layer: one sentence, no card and no gallery link.
    expect(text(container.querySelector('.frontier-retired')!)).toMatch(
      /A third model, a satellite water layer, was retired on 2026-10-02 after two tests.*no more often than chance\./
    );
    expect(t).not.toContain('Prithvi');
    const hrefs = [...container.querySelectorAll('a')].map((a) => a.getAttribute('href'));
    expect(hrefs).not.toContain('/gallery/bk18-satellite/');
    expect(hrefs).not.toContain('/gallery/battery-surge/');
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
    expect(container.querySelector('h2')?.textContent).toBe('Built on 34 public sources');
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
