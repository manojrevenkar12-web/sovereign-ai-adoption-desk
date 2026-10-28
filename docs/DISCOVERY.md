# Discovery questionnaire

What the desk needs to know about a use case. Every answer maps to one field in the portfolio
file (`data/portfolio/<customer>.yaml`) or a blind test case.

## Customer

| Field | Meaning |
|---|---|
| `level` | `bund`, `land` or `kommune` |
| `land` | `bund` for federal bodies, otherwise the state, e.g. `by` for Bavaria |
| `buyer` | `central_government` (oberste and obere Bundesbehörden) or `other` |
| `contracts` | hosting targets already under contract, e.g. `[chatgpt_enterprise_eu]` |
| `framework_agreement` | `true` if a framework agreement for AI services allows a call-off |
| `hosting_policy` | optional narrowing: data class → list of targets the customer allows for it |

## Use case

| Field | Values | Meaning |
|---|---|---|
| `pattern` | see below | What kind of solution it is. Decides the channel. |
| `users` | `staff`, `public`, `both` | Who uses it directly. |
| `data` | list of `public`, `internal`, `personal`, `special`, `social`, `tax`, `vs_nfd`, `vs_confidential_plus` | Every class of data the system will process. |
| `decision_role` | `information`, `procedural`, `improves_completed_human_work`, `pattern_detection`, `preparatory`, `materially_influences`, `decides` | What its output does to an outcome for a person. |
| `purpose_area` | `none` or an Annex III area: `biometrics`, `critical_infrastructure`, `education`, `employment`, `public_benefits`, `emergency_triage`, `law_enforcement`, `migration`, `justice`, `elections` | The area of its intended purpose. |
| `profiling` | bool | It profiles natural persons. |
| `prohibited` | list of `social_scoring`, `predictive_policing_profiling_only`, `untargeted_facial_scraping`, `emotion_recognition_workplace`, `biometric_categorisation_sensitive`, `manipulation` | Art. 5 practices involved. |
| `publishes_public_interest_text` | bool | Its text is published to inform the public. |
| `editorial_review` | bool | A person reviews that text and holds editorial responsibility. |
| `automated_decision` | bool | It decides about a person without a person deciding. |
| `per_user_logging` | bool, default `true` | Staff use is logged per person. |
| `large_scale`, `vulnerable_subjects`, `matching_datasets`, `systematic_monitoring` | bool | DPIA criteria. |
| `contract_value_eur` | number | Estimated value if a new contract is needed. |
| `target_preference` | target name or empty | The customer's preferred target. |

## Patterns and their channels

| Pattern | Channel |
|---|---|
| `enquiry_answering` | citizen channel |
| `drafting_with_sources` | agent workflow |
| `records_summary` | staff assistant |
| `form_extraction` | API application |
| `translation_plain_language` | staff assistant |
| `code_modernisation` | Codex |
| `knowledge_assistant` | staff assistant |
| `eligibility_assessment` | API application |
| `case_prioritisation` | API application |
