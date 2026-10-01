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
that fails is left out). Then comes one section per Stone with evidence, one
cited sentence per pebble, with the three point DEP scenarios merged into one
sentence. A plain place briefing leaves out a live reading that is not notable
(an observation with no rain, a tide less than a foot above prediction, a
water-level forecast below flood stage); a right-now question quotes them all. When no source produces evidence, the briefing says Riprap could not
build it and names the sources that failed to respond. There is no model. This
is the mode the MCP evidence tools use. The static gallery has 12 address
entries in this mode and 7 question entries in LLM mode.

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
3. "has it flooded": the past-event rule described below sets yes, no or
   cannot say. An Ida high-water mark says the block flooded only when it is
   within 250 m; a point within 50 m of the mapped Sandy edge gets no flat
   yes or no;
4. "how many": the counted source, and the count of the 311 kind the question
   names;
5. forecasts, projections and scenarios: those sources, with no yes or no.
   "Does the 2080 map show water here" is a fact about the map and takes yes
   or no from the scenario's depth class; "will it flood" does not;
6. "are there any": yes or no from the named source's own count;
7. any other source the question names (FEMA zone, terrain, permits, a
   district's floodplain counts);
8. any other question about flooding: the observed record.

A question in two parts ("was it in the Sandy area, and how many 311
complaints") is split into its clauses and each is answered, in the order
asked; the first part's yes or no leads.

A lead the rules chose still goes through the lead checks below; one that
fails is dropped and the facts stand. When no rule recognises the question,
the page shows the evidence for the place and says the question was not
answered.

## LLM mode

Set `RIPRAP_LLM_BASE_URL` and `RIPRAP_LLM_MODEL` to any OpenAI-compatible
endpoint (for example local Ollama at `http://localhost:11434/v1`). The model
is used only where there is a question (refactor 8):

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
no-LLM evidence, and `grounding.fallback_reason` says why. With a model
configured the model path is the default (`synthesis.RULES_FIRST = False`);
`grounding.answer_mode` is `rules` or `extractive` and records which one
answered.

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
  legal advice, a prediction for a specific day, or a hazard other than
  flooding) get a fixed refusal text, never model prose.

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
