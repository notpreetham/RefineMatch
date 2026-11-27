# RefineMatch

**Training-free, explainable-by-construction, certifiably robust detection of multi-stage network
attacks using temporal colour refinement.**

RefineMatch turns authentication and network logs into a temporal graph and detects ATT&CK-mapped
attack behaviours by *combinatorial matching* rather than learning:

```
logs ─► temporal graph ─► temporal colour refinement (TCR) ─► IR pattern matching ─► contrastive score
                                   │                                │                     │
                         streaming, O(1)/event              certificate (proof)     robustness radius
                                                                                          │
                                                               campaign stitching ◄───────┘
```

## Why it is different

| | Learned detectors (GNNs, KAIROS, Euler…) | Query-graph matching (POIROT) | Graph sketches (UNICORN) | **RefineMatch** |
|---|---|---|---|---|
| Needs attack labels / training | yes | no | no | **no** |
| Respects causal time order | partly | partly | no | **yes (TCR, provable)** |
| Suppresses benign look-alikes | implicitly | no | no | **explicit benign contrast** |
| Explanation | post-hoc, approximate | alignment | none | **machine-checkable certificate** |
| Evasion guarantee | none / smoothing | none | none | **certified edit radius** |
| Streaming cost per event | model inference | – | sketch update | **O(K) hashes (append-local)** |
| Multi-stage reasoning | limited | per query | no | **kill-chain stitching** |
| Cross-org sharing | model weights | query graphs | – | **signed, anonymised behaviour templates** |
| Template authoring | – | manual | – | **LLM-drafted, automatically validated** |

## Contributions (each backed by code and an experiment)

1. **Temporal colour refinement (TCR)** – a causal Weisfeiler–Leman variant
   ([src/refinement/temporal.py](src/refinement/temporal.py)). It separates causal from non-causal
   chains, which static 1-WL (and hence message-passing GNNs) cannot. Appending an event changes
   only the colours of its two endpoints (*append-locality*), so streaming updates cost O(K) per
   event: **×140 faster** than recomputing WL (E5).
2. **Individualization-refinement temporal subgraph matching**
   ([src/matching/matcher.py](src/matching/matcher.py)): containment refinement plus
   individualization, causal-order verification, leaf compression for fan-out behaviours, graceful
   relaxation, and an explicit exactness / confidence report (E9).
3. **Contrastive scoring against benign look-alikes**
   ([src/scoring/contrastive.py](src/scoring/contrastive.py)). Attack templates are broad (high
   recall); benign templates (jump-host admin, monitoring sweeps, cloud sync, ticket renewal, update
   polling) explain sanctioned behaviour away. Without it the false-positive rate is 74%; with it, 0% (E1/E2).
4. **Explainable-by-construction alerts** ([src/explanation/certificate.py](src/explanation/certificate.py)):
   every alert carries a certificate (embedding, one raw event per step, causal order, refinement
   trace, why each benign template fails) that an independent verifier re-checks: **100% verified,
   100% of tampered certificates rejected** (E7).
5. **Certified robustness** ([src/robustness/certify.py](src/robustness/certify.py)): a sound lower
   bound on the number of attacker event edits needed to evade, under an explicit threat model
   (essential steps, fixed asset roles, worst-case novelty). Validated empirically: **0 violations in
   141 attacks with fewer edits than the bound** (E4). The periodicity test was redesigned (longest
   periodic subsequence) so that C2 beacon detection is insertion-monotone and therefore certifiable.
6. **Campaign stitching** ([src/scoring/campaign.py](src/scoring/campaign.py)): DP over a kill-chain
   DAG of detections that share hosts, with noisy-OR evidence accumulation (E6).
7. **Privacy-preserving behavioural sharing** ([src/sharing/fingerprint.py](src/sharing/fingerprint.py)):
   a detection becomes a signed, anonymised template (roles + structure only, k-anonymity report,
   TCR canonical hash) that detects the same attack at another organisation (E8).
8. **LLM-assisted template authoring** ([src/templates_llm/generator.py](src/templates_llm/generator.py)):
   Claude drafts templates under a strict JSON schema; each draft must pass well-formedness,
   self-consistency (a synthetic instance built from the template is matched) and specificity (it
   does not fire on benign history) before acceptance. The LLM proposes; the matcher decides.

## Headline results (synthetic benchmark – see [results/report.md](results/report.md))

| Detector | AUC | Precision | Recall | FPR |
|---|---|---|---|---|
| **RefineMatch** | **1.000** | **1.00** | **1.00** | **0.00** |
| – without benign contrast | 0.871 | 0.48 | 1.00 | 0.74 |
| – without temporal order | 0.904 | 0.80 | 1.00 | 0.17 |
| Threshold rules (Sigma-style) | 0.636 | 0.48 | 1.00 | 0.73 |
| Per-host z-score | 0.716 | 0.60 | 0.20 | 0.09 |
| WL-histogram anomaly (UNICORN-style) | 0.489 | 0.45 | 0.15 | 0.12 |
| Host WL + logistic regression (**supervised**) | 0.565 | 0.56 | 0.15 | 0.08 |

> ⚠️ These numbers come from a synthetic enterprise generator written for this project. They show
> that the mechanisms work and that each component matters (ablations); they are **not** evidence
> of real-world performance. The perfect scores mostly reflect that the attack templates were
> written for the attacks the generator produces. See *Limitations*.

Honest weak spots that the experiments already expose:
- Recall drops to 0.47 for maximally stealthy variants (E3), where threshold rules keep 0.87 recall,
  but at a 73% false-positive rate.
- Exfiltration's certified radius is small (1 edit): an attacker who also uploads to a sanctioned
  SaaS provider gets part of the evidence explained away. This is a real evasion path, and it is
  visible in the certificate.
- Timing jitter of 15 minutes lowers detection to 0.83 (E4).

## Quick start

```bash
pip install -r requirements.txt
python -m pytest -q                                   # 31 tests
python -m src.evaluation.experiments --out results    # full suite, ~40 s
streamlit run app/dashboard.py                        # analyst dashboard
```

```python
from src.ingestion.synthetic import SyntheticEnterprise, generate_benchmark
from src.pipeline import RefineMatch
from src.matching.matcher import PatternMatcher
from src.robustness.certify import certify
from src.explanation.certificate import build_certificate

ent = SyntheticEnterprise(seed=0)
rm = RefineMatch(known_roles=ent.roles).fit_baseline(
    [w.events for w in generate_benchmark(20, 0, 0, seed=1, enterprise=ent)])
window = generate_benchmark(0, 1, 0, seed=2, enterprise=ent)[0]
report = rm.analyze_window(window.events)
det = report.detections[0]
m = PatternMatcher(report.index)
print(build_certificate(det, m, rm.scorer, certify(det, m, rm.scorer)).to_text())
```

Real data: [src/ingestion/loaders.py](src/ingestion/loaders.py) reads the LANL *Comprehensive
Multi-Source Cyber-Security Events* files (`auth.txt`, `flows.txt`, `redteam.txt`) and generic CSV
(Zeek / CIC flow exports).

## Repository layout

```
src/core          data models, configuration, vocabulary
src/ingestion     LANL / CSV loaders, synthetic enterprise + attacks + hard negatives
src/graph         temporal graph, role inference, windows, typed index, streaming detector
src/refinement    deterministic hashing, TCR (batch + incremental), static WL, WL kernels
src/matching      pattern language, IR matcher, ATT&CK + benign template library
src/scoring       contrastive scorer, benign colour profile, campaign stitching
src/explanation   detection certificates + independent verifier
src/robustness    robustness certificates, adversarial perturbations
src/sharing       anonymised, signed template export / import
src/templates_llm Claude-drafted templates with validation gates
src/evaluation    baselines, metrics, experiment suite (E1–E9)
app/              Streamlit dashboard
tests/            31 tests (properties of TCR, matcher, certificates, sharing, loaders, LLM loop)
```

## Limitations and what must happen before submission

1. **Real data.** Run the suite on LANL (red-team auth events, which map directly to the
   lateral-movement template), DARPA OpTC, and ideally one CIC dataset. Report results by day, with
   templates frozen *before* looking at the test days.
2. **Stronger baselines on the same data:** published Euler (LANL numbers are reported in its paper),
   a GraphSAGE/GIN node classifier, and UNICORN's released code.
3. **Template coverage.** Use the LLM generator to produce templates for 20–40 ATT&CK techniques
   and report precision of generated vs hand-written templates.
4. **Role inference without a CMDB.** The certificates assume roles the attacker cannot change.
   Measure sensitivity when roles are inferred from behaviour.
5. **Formal write-up** of the TCR properties (time-respecting-walk characterisation,
   append-locality) and soundness of the deletion bound; the code comments state the arguments.
