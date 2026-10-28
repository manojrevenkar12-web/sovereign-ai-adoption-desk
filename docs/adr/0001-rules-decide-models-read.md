# 1. Rules decide the classification; models only read

**Context.** A public body's counsel, data protection officer and staff council have to sign off on
what the AI Act, the GDPR and German public law ask of a use case. A model's opinion cannot be
signed off, and it changes when the model changes.

**Decision.** Classification, gates and obligations are rules in `config/` with the article each rests
on, applied by `desk.classify`. Every result carries its reasons in plain words. Models are used
where reading is the job: answering from guidance, drafting from records.

**Consequences.** The rules are reviewable like code and tested on a blind set (40/40 on its first
run). They encode one reading of the law, written in `docs/RULES.md`; where the law needs judgement
(Art. 6(3) "no significant risk of harm") the desk records the question rather than answering it.
