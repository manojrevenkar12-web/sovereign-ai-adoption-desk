# Writing a blind set of use cases

You are writing test cases for a tool that classifies public-sector AI use cases. You have NOT seen
its code and must not look at it. Read only `docs/RULES.md` and `docs/DISCOVERY.md`, then write
`heldout/<set>/cases.yaml` and put the word `blind` in `heldout/<set>/STATUS`.

Write 40 cases. Make them realistic German public-sector situations (federal, state and municipal),
and spread them: at least 4 prohibited, 8 high-risk, 6 not-high-risk under Art. 6(3), 8 with
transparency duties, the rest minimal; include classified data, social data, tax data, special
categories, citizen channels, staff tools with and without per-user logging, customers with and
without contracts and framework agreements, values on both sides of the EU thresholds, and some
cases where the only fitting target is the planned sovereign one. Include hard cases: an informing
system in an Annex III area, profiling with a preparatory role, published text with and without
editorial review, a hosting policy that narrows the choice. Work out every expectation by hand from
the rules, independently of any software.

Format:

```yaml
cases:
  - id: c01
    note: one sentence describing the situation
    customer:            # optional; defaults: level land, land by, buyer other, no contracts, no framework
      level: bund
      land: bund
      buyer: central_government
      contracts: [chatgpt_enterprise_eu]
      framework_agreement: false
      hosting_policy: {personal: [openai_api_eu]}
    use_case:            # fields from docs/DISCOVERY.md
      pattern: enquiry_answering
      users: public
      data: [public, personal]
      decision_role: information
      purpose_area: none
      contract_value_eur: 90000
    expect:              # every field you state is checked; omit a field to leave it unchecked
      ai_act_class: transparency      # prohibited | high_risk | not_high_risk | transparency | minimal
      derogation: null                # null or procedural | improves_completed_human_work | pattern_detection | preparatory
      transparency: [interacts_with_public]   # any of interacts_with_public, publishes_public_interest_text
      dpia: false
      fria: false
      staff_council: false
      procurement_route: eu_procedure # null | framework_call_off | national | eu_procedure
      hosting: openai_api_eu          # null if stopped by hosting
      stops: []                       # any of prohibited, classified, no_target
```

For a prohibited case, state only `ai_act_class` and `stops`. For a classified case, state `stops`
and the AI Act class. Do not invent fields.
