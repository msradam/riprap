---
type: reference
---

# How a briefing is grounded

Riprap has two ways to write a briefing. Both start from the same evidence.

## Evidence

Every pebble that returns a value is rendered through its manifest's
`narration.template` into one or more plain sentences. If the template names a
field the value lacks, the pebble says nothing. Experimental pebbles begin with
"Experimental:". This rendering lives in `riprap/core/burr/evidence.py`.

Each piece of evidence has a `doc_id` (the manifest's `provenance.doc_id`).
Citations, source URLs and vintages come from the manifest's `provenance` block
and nowhere else.

## No-LLM mode (default)

With no LLM endpoint configured, the briefing is the evidence itself, built by
`riprap/core/burr/templated_reconciler.py`. A bare address opens with an "In
brief" lead: the Sandy footprint, the FEMA zone, the DEP scenarios and the 311
count, each cited and each passed through the claim verifier below (a part
that fails is left out), after a "Place described: ..." paragraph that names
the place the briefing was answered for. Then comes one section per Stone with evidence, one
cited sentence per pebble, with the four point DEP scenarios merged into one
sentence. A plain place briefing leaves out a live reading that is not notable
(an observation with no rain, a tide less than a foot above prediction, a
water-level forecast below flood stage); a right-now question quotes them all. When no source produces evidence, the briefing says Riprap could not
build it and names the sources that failed to respond. No language model is
involved. (The experimental models are sources like any other here: their
sentences are written by code, labelled and hedged, and stay out of a plain
briefing unless they show something; see [MODELS.md](MODELS.md).) This
is the mode the MCP evidence tools use. The static gallery is built in this mode: 35
entries (for flood 12 addresses, 3 community districts and 10 questions; for
heat 3 places and 7 questions).

A question is answered in this mode too, by rules over its words
(`riprap/core/burr/rule_answer.py`). The rules pick the lead and the facts
from the question and from the values the sources returned; the facts are the
sources' sentences word for word. They are tried in a fixed order:

1. "right now": the live readings, each with its time, and no yes or no (no
   alert is not an observation that nothing is flooding). A word for now
   beside a mapped subject ("currently in a FEMA flood zone") is a question
   about that subject, not about now;
2. a named asset class (subway, schools, public housing, hospitals): its
   register. Yes or no comes from the register's own count for what the
   question names (inside the Sandy extent, inside the DEP extreme scenario);
   "is the school safe" and "has it flooded since Ida" get no yes or no;
3. "will it flood" at a place or on a day: no yes or no and no refusal. The
   lead says no source or model here predicts that, and the alerts, the
   Weather Service's water-level forecast, the current stormwater scenario and
   the Sandy extent follow (and, only on a server that opts in to it, the
   experimental surge forecast, labelled; it is out of default briefings
   because damped persistence beat it on held-out data);
4. a question an experimental model answers (a surge at the Battery, land
   cover): the official source
   for the same thing first when there is one, then the model's hedged
   sentence. With no official source the lead is "From an experimental model,
   not a measurement:". If the question is about past flooding, rule 5 sets
   the lead from the record and the model's sentence only follows it
   ([MODELS.md](MODELS.md));
5. "has it flooded": the past-event rule described below sets yes, no or
   cannot say. A sensor event or an Ida high-water mark makes a "Yes." about
   an address only within 100 m of it; farther off the lead is "Flooding was
   recorded near this address, not at it", with the distance (`near`). A
   point within 50 m of the mapped Sandy edge gets no flat yes or no. An
   event FloodNet marks as verified by a person counts whatever its
   sensor's status is today. A question about a named past day is read from
   the records dated that day;
6. "how many": the counted source, and the count of the 311 kind the question
   names. "Since 2024" sums the years from then; "since Ida" starts mid-year
   and gets the source's own window, stated, with no count as the lead;
7. forecasts, projections and scenarios: those sources, with no yes or no. A
   question about the next hours or days gets the water-level forecast, one
   about the 2050s the projections. "Does the 2080 map show water here" is a
   fact about the map and takes yes or no from the scenario's depth class;
8. "are there any marks, complaints, sensors": yes or no from the named
   source's own count, only when the question asks about the thing counted
   ("did any water reach it" asks whether it flooded, and gets no yes from a
   count of marks);
9. any other source the question names (FEMA zone, terrain, permits, a
   district's floodplain counts; water that lingers after rain is a question
   for the city's stormwater scenarios);
10. any other question about flooding: the observed record.

A question in two parts ("was it in the Sandy area, and how many 311
complaints") is split into its clauses and each is answered, in the order
asked; the first part's yes or no leads. A share of an area is "In part."
unless nearly all of it is inside ("was QN12 inside the Sandy zone" at 0.8%).

A lead the rules chose still goes through the lead checks below; one that
fails is dropped and the facts stand. When no rule recognises the question,
the page shows the evidence for the place and says the question was not
answered.

## LLM mode

Set `RIPRAP_LLM_BASE_URL` and `RIPRAP_LLM_MODEL` to any OpenAI-compatible
endpoint (for example local Ollama at `http://localhost:11434/v1`). The model
is used only where there is a question:

- A bare address or district has no question, so neither the planner nor the
  synthesis calls the LLM: the page is the no-LLM evidence briefing, and the
  mode line says no LLM was needed. `RIPRAP_LLM_BARE=1` restores the older
  behaviour below, in which the model rewrites the evidence as claims.
- For a question the model returns only the answer: a lead and the ids of
  one to four facts. It writes no section claims. For a question that asks
  about forecasts or projections, code chooses the facts (the forecasts and
  projections themselves); for a yes or no question about past flooding, a
  rule sets the lead.
- With `RIPRAP_LLM_BARE=1` the model rewrites the evidence as a list of
  claims, as described in the steps below. It never writes free prose.

1. The model receives the evidence sentences, grouped by section, each labelled
   with its `doc_id`.
2. It must answer with JSON that matches a schema built for this request:
   `claims: [{section, text, doc_ids, numbers}]`. `doc_ids` is an enum of the
   ids actually passed in, and `section` is an enum of the sections that have
   evidence. The schema goes to the endpoint as `response_format`, so the
   decoder cannot produce other ids.
3. Code checks every claim (`riprap/core/burr/synthesis.py`, `verify`):
   - it cites at least one doc_id, and every cited id was passed in;
   - its section is one of the sections offered;
   - every number in the claim, both in its `numbers` field and anywhere in its
     text, matches a number in the documents it cites;
   - its text has no template placeholders such as `<value>` or `[doc_id]`.
4. If any claim fails, the model gets one retry with the failures and reasons
   listed.
5. Claims that still fail are dropped. They are returned in `dropped_claims`
   with their reason and shown in a collapsed "Dropped claims" section. They are
   never part of the rendered briefing.
6. The briefing is rendered from the surviving claims only. A section with
   evidence but no surviving claim prints "No grounded evidence for this
   section." A claim that cites an experimental source is prefixed
   "Experimental:" if the model left that out.

If no endpoint answers, a question falls back to the rules above, then to the
no-LLM evidence, and `grounding.fallback_reason` says why.

With a model configured, the rules still go first: a question the rules
recognise, at a place the parser can read, is planned and answered with no
model call, and the model is asked only for the rest. `answer_path` (`rules`
or `llm`) at the top of the result says which one answered;
`grounding.answer_mode` (`rules` or `extractive`) records the same.
`RIPRAP_RULES_FIRST=0` puts the model first.

The order was set by measurement, in what the README calls the head-to-head
comparison. It compared Riprap's rule path with Riprap's model path. It did
not compare Riprap with observed flooding or with any other tool, and both
the questions and the judgements were made by AI agents, not by people. An agent that could not read the repository
wrote questions the way users type them; both paths answered each one in the
same process; a second agent judged the pairs blind. Over 130 judged pairs
(four sets, 2026-10-01) the rule answers were preferred on 54, the model's on
21, and 55 were ties; wrong openings 7 against 8, wrong places 13 against 12,
sentences beside the point 70 against 145, and a median of about 2 s against
9 to 13 s. Two of the four sets were never seen while the rules were
written. The first of those went against the rules on wrong openings and
places, 3 and 5 against 1 and 4; the defects behind it were fixed, and the
second met the bar.

### Questions

When the input is a question, not just a place, three more rules apply.

- The planner chooses which sources to consult from each manifest's
  `answers:` line; `select_pebbles` adds a short always-run floor (FEMA flood
  zone, Sandy extent and the DEP 2050 scenario for an address; NWS alerts for
  a "right now" question) and a floor for the question's focus (for a past
  question 311, FloodNet, Ida high-water marks and Sandy; for a right-now
  question alerts, observations, FloodNet, the tide gauge and the NWS
  water-level forecast; for a forecast question that forecast, the NPCC4
  projections and the DEP 2050 and 2080 scenarios; for an asset question that
  asset's register). Only those pebbles run, and every briefing lists the
  sources consulted and the ones not checked. A bare address runs every source.
- The briefing opens with an answer (described below). If no answer
  survives the checks,
  it opens with the fixed line "The sources consulted do not answer this
  question directly. Here is what they show." The answer is not repeated in
  the sections below it, and a Stone section with no sentence is hidden. A
  Stone whose consulted sources all returned nothing says so: "Consulted X;
  it returned nothing for this place."
- Questions Riprap does not answer (buying, renting or insuring property,
  legal advice, health or safety advice, a prediction for a specific day, or
  a hazard other than flooding or heat) get a fixed refusal text, never
  model prose.

### The answer and its checks

**Extractive.** The model does not write the answer. It returns a
lead (`yes`, `no`, `partly`, `count`, `cannot_answer`) and up to four
document ids. The answer is a fixed phrase for the lead ("Yes.", "No.", "In
part.", "From the sources consulted:") followed by those documents' template
sentences, word for word. Code checks the lead
(`riprap/core/burr/answer_checks.py`, `check_lead`):

- `no` is invalid when a chosen fact reports something;
- `yes` is invalid when every fact reports an absence, or when an asset
  register counts only some of its assets inside;
- `partly` needs one fact reporting a result and one reporting none or only
  some (a register with some inside satisfies both);
- a count or share question ("how many", "how much", "what share") gets the
  `count` lead, and `count` needs a fact with a figure;
- when the question names a source (subway, school, 311, sensor, Ida, rain,
  tide, sea level, alert), `yes` and `partly` are invalid if that source's
  fact reports none;
- `no` is invalid when a chosen source was unavailable, and a count of 0 is
  invalid when it comes from an unavailable source (the `unavailable` rule:
  a source that could not answer supports neither a "no" nor a zero).

For a yes or no question about past flooding ("has this block flooded since
Ida?"), the lead is set by a rule, not chosen by the model
(`answer_checks.past_event_lead`). The model still picks and orders the
facts. The lead is `yes` when a relevant observed source (311, FloodNet, the
Ida high-water marks or the Sandy extent, depending on the question) reports
an event in the asked period, `no` only when every relevant source answered
and reported none, and `cannot_answer` otherwise. Silence is not a "no": a
FloodNet query with no sensor in range, or no Ida mark nearby, cannot say the
place stayed dry. The source the rule relies on is added to the facts when
the model left it out, so the lead is always cited.

A question the records cannot answer is not given the neutral lead. When
it asks for something Riprap does not hold (a trend, a ranking of places, a
score, figures about people or households, advice to an agency, law or
benefits, another 311 topic; the table is `rule_answer.NOT_HELD`), the
answer's first sentence says what is not held, the lead is `not_held` and
`answered` is `false`, in `grounding` and at the top of the result. A
question not written in English gets `not_english` and one fixed line each
in Spanish, Chinese and Bengali. A question with a place and an ask no rule
recognises gets `not_recognised`. In each case the evidence for the place
follows, under a sentence that says none of it answers the question.
`answer_path` still reads `rules` for these, since it names the path that
ran, not whether it answered.

An asset register "reports a result" when any of its inside counts is above
zero. An invalid lead is retried once, then replaced by the cannot-answer
line. A count or share question with a figure among the facts is given the
`count` lead directly. If the source the question is about is missing from
the facts after the retry, it is appended; if the lead no longer fits the
appended fact, the lead is dropped and the answer opens "From the sources
consulted:".

Every briefing with an answer ends with a line naming the checks that ran: "Checks
run: citations and numbers on every claim; lead rules on the answer, which
is the cited text word for word." An answer about right now also points to
the FloodNet dashboard, the National Weather Service and Notify NYC.

**The retired guarded mode.** Until 2026-09-30 `RIPRAP_ANSWER_MODE=guarded`
let the model write one to three answer claims of its own, checked by five
word-pattern rules (absence, universal, inference, dropped count, datum) and
an entailment classifier (`knowledgator/gliclass-large-v3.0`, threshold
0.787 from a 146-claim calibration split; on the 582 test claims it kept
86% of true claims and caught 85% of perturbed ones). On real answers the
classifier caught only absence and warning-read-as-observation errors,
passed paraphrased inferences and wrong quantifiers, and dropped correct
claims (about 6% of the answer claims it saw). Extractive answers cannot
paraphrase, so the mode was removed. The code, its tests, the calibration
script and its results are at the git tag `archive/guarded-answer-mode`.

Number words ("four", "two") are read as digits by the number check in both
modes.

### Number tolerance

A claimed number matches an evidence number when one of these holds:

- they are equal, ignoring thousands separators and a leading sign;
- the evidence number rounds to the claimed number at the claim's precision
  (evidence 5870.5 supports "5870", "5871" and "5,870"; 16.89 supports "16.9"
  but not "16.95");
- the same holds after converting metres to feet or feet to metres, or metres to
  kilometres or kilometres to metres (16.89 m supports "55 ft"; 1417 m supports
  "1.4 km").

The numbers 311 and 911 are treated as service names, not measurements.
Numbers that appear in the user's own question or in the resolved address
(a house number, a street number, a year the user named) may be restated
without evidence support; they are the user's words, not claims about the
data. Numbers
must come from the documents the claim cites: a real number from a different
document does not count.

### What is not checked

Body claims (the sections after the answer, written only with
`RIPRAP_LLM_BARE=1`) get citation and number checks only: a wrong
non-numeric fact ("inside" for "outside") with correct numbers passes. In
the answer the text is the evidence text, so it cannot paraphrase; what can
still be wrong is the lead and the choice of facts, and only the lead rules
above are checked.

## Heat questions

A question about outdoor heat is answered by the same rule engine. The
hazard is read from the question's words in code
(`riprap/core/burr/heat_answer.py`, `hazard_of`), clause by clause: a heat
word in a preamble does not make a flood question a heat one, and a street
or neighbourhood with a heat word in its name ("Heath Avenue") is a place.
The plan's focus then names the hazard, and only that hazard's sources run.
`rule_answer.answer` hands the question to the heat rules, which pick the
lead and the facts in this order:

| The question asks for | Lead | Facts |
|---|---|---|
| A score, a rating, a grade or a ranking | "Riprap computes no score or rating of its own ..." | The Health Department's index, as the department's |
| The hottest or worst part of a place | "Riprap does not rank places against each other or single out one part of a place ..." | The record for the whole place named |
| One apartment, one block or a calendar date in the future | "Riprap cannot predict what will happen in one building, on one block or on a named day ..." | The Weather Service's forecast and alerts, the surface measurement; for a day the 7-day forecast cannot reach (next July, next summer), what was measured here and the station record instead |
| Now, today | Neutral | The latest observation, any active heat alert, the forecast; what the question names comes first |
| The coming days | "From the National Weather Service, as issued for the next 7 days; Riprap predicts nothing itself:" | The forecast and alerts |
| The coming decades | Neutral | NPCC4 Table 4 |
| A count of hot days | The year asked about, from the station's own yearly record; none when the question names another threshold than 90°F or a span of years | The station sentence |
| Hotter or cooler than the city | "At the surface, yes." or "At the surface, no.", only when the question gives one direction, the city is the baseline and every Landsat image agrees; neutral otherwise | The surface measurement |
| Hotter than another place, another borough or "than usual" | Neutral | Each place's own sentences |
| Deaths | "Heat deaths are published for the city as a whole only ..." | Heat illness visits |
| Hospital admissions, visits in a year outside the file's period, whether a difference is significant, a count of days at a threshold other than 90°F | The cannot-answer line | The nearest record, after the statement that it is not the answer |
| Cooling centers, asked alone | "The city opens cooling centers only during a heat emergency ..." | NYC Parks spray showers and pools |
| A trend in hot days | The station's yearly counts as decade averages | The station sentence |
| Past heat alerts, or an alert source that did not answer | The cannot-answer line: "no active advisory" is never the answer to either | What the live sources returned |
| A named source (the index, visits, canopy, places to cool off) | Neutral, or the count lead | That source |
| Anything else about heat | Neutral | The surface measurement, the index, the land cover map, the station record |

The heat leads are set only by code, from a source's own value, and are
exempt from the word-pattern lead checks (`answer_checks.CODE_LEADS`), which
were written for flood sentences. The facts are still the sources' sentences
word for word. A borough or the city is a place for a heat question, read as
an area; a place outside New York City is told that the heat briefing
covers the city only. A cold apartment in winter is named as indoor heating
and sent to 311, and basketball or "the hottest new restaurants" is told it
is not a weather question. Advice ("should I", "is it too hot to", "do I
need", "is that a bad idea") is declined with where official guidance is. A
house number is never read as a year or a temperature. A flood answer to a
question that names both hazards says that the two are separate briefings
and that Riprap does not weigh one against the other.

A part of a borough by direction ("the South Bronx") has no boundary here and
is told so; Staten Island's North Shore, Mid-Island and South Shore are its
three community districts. A ZIP code is declined as a ZIP. A neighbourhood
that the city splits in two ("East Harlem (South)") is the half the query
names. A question that names two neighbourhoods without comparing them is answered
for one, and the answer says so and how to ask for both. A place outside New
York City is declined as soon as it resolves, naming the place found. A
borough or the city is named as a whole in the opening.

How it was tested: 120 unit tests (`tests/test_heat.py`), independent keys
for the facts (`tests/golden/keys_heat.py`), two question sets written by
agents that had seen none of the code (`tests/golden/unseen_heat.json`,
`unseen_heat2.json`), a blind judge, and a reviewer with no part in the
build who ran inputs until answers broke, and three personas (a council staffer, a
reporter, a public health researcher) who used the running app. The first unseen set found the
place parser, not the sources: about a third of sixty went wrong on the
first run, almost all in finding the place or the hazard. The second set
and the reviewer found the rules: an inverted yes or no, a house number
read as a year, a landmark answered with its borough's figure. The
independent key agreed on 1,581 of 1,623 facts and found the surface raster
half a Landsat pixel out of place and Central Park's coordinate rounded by
530 m. Each is now a test built from the input that found it, or a fixture.

## 311 counts

NYC 311 flood requests are filtered by descriptor
(`app/context/nyc311.py`). The city renamed the descriptors in 2026:
complaint type "Sewer" with coded names ("Sewer Backup (Use Comments) (SA)")
gave way to "Sewer Maintenance" with plain names ("Backup"). Riprap counts
both names as one kind, with the complaint type in the filter, and counts
an incident logged under both names once. `tests/test_311_vocabulary_live.py`
fails when the dataset grows a flood-like descriptor the app does not count.

Outside NYC a 311 feed is counted only through a reviewed filter:

- Chicago and Seattle give a category name, so a reviewed table in the
  manifest decides (`config.record_filter`, `kind: category_table`,
  `riprap/core/pebbles/record_filter.py`). The reviewed categories are
  listed in each manifest's comment. Each sentence says how many of how
  many records were kept, and "the latest N" when the feed hit its fetch
  limit.
- Albany's SeeClickFix feed is queried for its own flooding,
  sewers/drainage and sinkhole request types.

A category table cannot see a flood report filed under another category,
and Seattle's feed has no street-flooding category at all.

## Measuring it

`scripts/probe_grounding.py` runs the gallery addresses in LLM mode and writes
`tests/probe_grounding_results.json`: claims kept, claims dropped with reasons,
and claims that needed the retry. `tests/test_claim_verifier.py` holds
hand-written good and bad claims for the verifier.

## Disclosure checks

`riprap/core/compliance/predicates.py` runs substring checks on every briefing
for disclosure phrases (scope statement, automation disclosure, informational
disclaimer, citations on numeric sentences). They check that the disclosures are
present. They are not evidence of briefing quality.
