# Research Answer Policy

## Product contract

Use the user’s requested intent, format and selected scope. Do not turn ordinary questions into tables. Do not expand a selected document scope to a project or whole library without an explicit request. A project is a container; documents remain independently attributable.

## Per-intent behavior

- **Definition/direct fact:** concise answer first, followed by supporting source citation(s). If the selected evidence does not state it, say so.
- **Explanation:** connected prose; distinguish explicit source statements from synthesis across passages and identify uncertainty.
- **Summary:** include only populated sections supported by retrieved evidence; do not repeat the same passage under multiple headings.
- **Method/algorithm:** report purpose/procedure/assumptions and complexity only if the source states them.
- **Results/metrics:** retain metric, value, unit, dataset, setup and baseline when available. Do not promote a bare number to a result.
- **Comparison:** per-document evidence balance; dimensions, agreements, differences, conflicting reports and missing evidence remain distinct. Do not normalize unlike metrics.
- **Table:** only when requested or selected in a comparison/report tool; each cell carries its source reference.
- **Unanswerable:** abstain from source claims and make the evidence limit clear.
- **Follow-up:** use conversation context only to resolve references; preserve explicit selected scope and new user instructions.

## Claim and citation wording

Every factual sentence must cite the relevant retrieved source(s). Page labels must mean PDF viewer pages unless a printed-page mapping was independently verified. Do not substitute the project title for a document title or invent bibliographic metadata.

Use conservative status labels: directly supported, partially supported, conflicting evidence, insufficient evidence, or not verified. Citation ID resolution proves only that the cited chunk exists. The current independent validator uses deterministic extraction, lexical/numeric conflict checks and citation mapping; it cannot establish semantic entailment. The interface/report must disclose that limitation instead of calling it a semantic proof or “strongly supported” solely because a citation resolves.

## Status in current code

The independent composer has separate intents/templates and a no-model path; the legacy query pipeline has planner, sufficiency and claim-check services. They are not one consistent runtime contract: the default independent query returns before the legacy planner. Review intent templates against authorized examples before claiming answer quality. Empty sections, generic filler, repeated citations and unverified cross-source claims are regression targets.
