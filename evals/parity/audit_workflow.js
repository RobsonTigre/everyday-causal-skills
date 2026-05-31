export const meta = {
  name: 'rpy-parity-audit',
  description: 'Audit R<->Python parity for each method; produce specs/recipes/findings + proposed sources',
  phases: [
    { title: 'Investigate' },
    { title: 'Verify' },
    { title: 'Synthesize' },
  ],
}

// Methods to audit (did is already done as the golden; exclude it).
const METHODS = (args && args.methods) || [
  'iv', 'rdd', 'matching', 'sc', 'timeseries', 'hte', 'experiments', 'dag',
  'report-figures', 'exercises',
]

const FINDING = {
  type: 'object',
  required: ['method', 'disparities', 'proposed_sources', 'recipes_written', 'fixture_written'],
  properties: {
    method: { type: 'string' },
    disparities: {
      type: 'array',
      items: {
        type: 'object',
        required: ['dimension', 'severity', 'summary', 'leveling_target', 'effort'],
        properties: {
          dimension: { type: 'string', enum: ['coverage', 'numerical', 'robustness', 'api_feature'] },
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
          summary: { type: 'string' },
          leveling_target: { type: 'string' },
          effort: { type: 'string' },
          depends_on_unapproved_source: { type: 'boolean' },
        },
      },
    },
    proposed_sources: {
      type: 'array',
      items: { type: 'object', required: ['ref', 'why'], properties: {
        ref: { type: 'string' }, why: { type: 'string' } } },
    },
    recipes_written: { type: 'boolean' },
    fixture_written: { type: 'boolean' },
    spec_path: { type: 'string' },
  },
}

const VERDICT = {
  type: 'object',
  required: ['method', 'confirmed', 'rejected', 'notes', 'proposed_sources'],
  properties: {
    method: { type: 'string' },
    confirmed: { type: 'array', items: { type: 'object' } },
    rejected: { type: 'array', items: { type: 'object' } },
    notes: { type: 'string' },
    proposed_sources: { type: 'array', items: { type: 'object' } },
  },
}

const results = await pipeline(
  METHODS,
  // Stage 1: investigate + write draft artifacts (NO new source used to ground claims yet).
  (m) => agent(
    `Audit R<->Python parity for the "${m}" method of the everyday-causal-skills plugin.\n` +
    `Repo: /Users/robsontigre/Desktop/everyday-causal-skills. Use python3 and Rscript.\n` +
    `1. Read templates/r/${m}.md and templates/python/${m}.md, references/method-registry.md, ` +
    `   and references/assumptions/${m}.md if present.\n` +
    `2. Determine the current best-practice estimator via the robson-literature-review skill + the registry. ` +
    `   Any NEW external reference (not already cited in the repo) goes ONLY into proposed_sources with a ` +
    `   one-line justification — do NOT use it to ground a recommendation yet (source-approval gate).\n` +
    `3. Write dedicated reference recipes evals/parity/reference/${m}.{R,py} (assume df is preloaded; ` +
    `   print key estimands as KEY:<value>) and a deterministic shared fixture under evals/parity/fixtures/.\n` +
    `4. Write a draft evals/parity/specs/${m}.yaml (schema per the spec doc).\n` +
    `5. Run both recipes via python3 evals/parity/run_parity.py --method ${m} and record numerical agreement.\n` +
    `6. Record disparities across the 4 dimensions (coverage, numerical, robustness, api_feature) with a ` +
    `   leveling target and effort estimate. Mark any item that relies on an unapproved source.\n` +
    `Commit your new files (author = user; NO Co-Authored-By). Return the structured finding.`,
    { schema: FINDING, label: `investigate:${m}`, phase: 'Investigate' }),
  // Stage 2: adversarial verification of each claimed disparity.
  (finding, m) => agent(
    `Skeptically verify the parity audit for "${m}". Finding:\n${JSON.stringify(finding)}\n` +
    `For each claimed disparity: re-run evals/parity/run_parity.py --method ${m}; confirm whether each ` +
    `"missing"/"outdated" package is ACTUALLY absent/old under python3 and Rscript (try importing it); ` +
    `confirm numerical (dis)agreement reproduces; reject anything you cannot reproduce or that is wrong. ` +
    `Do NOT rely on unapproved external sources. Return confirmed vs rejected disparities. ` +
    `Also pass through the finding's proposed_sources array unchanged in your response, so the ` +
    `synthesizer can consolidate them.`,
    { schema: VERDICT, label: `verify:${m}`, phase: 'Verify' }),
).then((rs) => rs.filter(Boolean))

// Stage 3: synthesize the consolidated proposed-sources list + draft report/backlog text.
phase('Synthesize')
const synthesis = await agent(
  `You are the synthesizer for the R<->Python parity audit. Inputs (verified):\n` +
  `${JSON.stringify(results)}\n` +
  `Produce: (a) one consolidated list of ALL proposed_sources across methods (dedup), each with which ` +
  `method/claim needs it; (b) the master report body (ranked confirmed disparities by severity across the ` +
  `4 dimensions, with leveling target + effort), marking any recommendation that depends on an unapproved ` +
  `source as PENDING-SOURCE-APPROVAL; (c) the backlog (one stub per confirmed disparity); (d) the list of ` +
  `baseline.yaml entries to add (method, backlog_id, dimension, summary) for every currently-disparate method. ` +
  `Return JSON with keys: proposed_sources, report_markdown, backlog_markdown, baseline_entries.`,
  { schema: {
      type: 'object',
      required: ['proposed_sources', 'report_markdown', 'backlog_markdown', 'baseline_entries'],
      properties: {
        proposed_sources: { type: 'array', items: { type: 'object' } },
        report_markdown: { type: 'string' },
        backlog_markdown: { type: 'string' },
        baseline_entries: { type: 'array', items: { type: 'object' } },
      },
    }, label: 'synthesize', phase: 'Synthesize' })

return { findings: results, synthesis }
