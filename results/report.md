# RefineMatch -- experiment report

Synthetic enterprise benchmark, seed 0, 148 test windows (60 with attacks). RefineMatch uses a fixed threshold 0.65; baselines are calibrated to 5% FPR on held-out benign traffic. **All numbers are from synthetic data and must be re-measured on LANL / OpTC before publication.**

## E1 Detection quality

| Detector | AUC | AP | Precision | Recall | F1 | FPR | ms/window |
|---|---|---|---|---|---|---|---|
| RefineMatch (full) | 1.000 | 1.000 | 1.00 | 1.00 | 1.00 | 0.00 | 12.3 |
| - no benign contrast | 0.871 | 0.691 | 0.48 | 1.00 | 0.65 | 0.74 | 9.0 |
| - no temporal order | 0.904 | 0.671 | 0.80 | 1.00 | 0.89 | 0.17 | 11.9 |
| - no novelty term | 1.000 | 1.000 | 1.00 | 1.00 | 1.00 | 0.00 | 7.5 |
| - no individualization | 0.940 | 0.937 | 1.00 | 0.88 | 0.94 | 0.00 | 11.3 |
| WL-histogram anomaly (UNICORN-style) | 0.489 | 0.441 | 0.45 | 0.15 | 0.23 | 0.12 | 3.5 |
| TCR-histogram anomaly | 0.479 | 0.433 | 0.41 | 0.12 | 0.18 | 0.11 | 10.5 |
| Per-host z-score | 0.716 | 0.628 | 0.60 | 0.20 | 0.30 | 0.09 | 0.5 |
| Threshold rules (Sigma-style) | 0.636 | 0.299 | 0.48 | 1.00 | 0.65 | 0.73 | 0.2 |
| Host WL features + logistic regression (supervised) [uses labels] | 0.565 | 0.463 | 0.56 | 0.15 | 0.24 | 0.08 | 3.3 |

## E2 Per-scenario recall / look-alike false-positive rate

| Detector | R lateral_movement | R kerberoasting | R network_scan | R exfiltration | R c2_beaconing | FPR admin_jump | FPR monitoring_sweep | FPR cloud_sync | FPR ticket_renewal | FPR update_polling | FPR noncausal_logons | FPR plain_benign |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RefineMatch (full) | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| - no benign contrast | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.88 | 1.00 | 1.00 | 0.50 | 0.55 |
| - no temporal order | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.12 | 0.00 | 0.25 | 0.12 | 0.88 | 0.10 |
| - no novelty term | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| - no individualization | 0.83 | 0.92 | 0.92 | 0.92 | 0.83 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| WL-histogram anomaly (UNICORN-style) | 0.17 | 0.08 | 0.08 | 0.17 | 0.25 | 0.12 | 0.00 | 0.00 | 0.25 | 0.25 | 0.00 | 0.15 |
| TCR-histogram anomaly | 0.17 | 0.00 | 0.08 | 0.17 | 0.17 | 0.12 | 0.00 | 0.00 | 0.25 | 0.25 | 0.00 | 0.12 |
| Per-host z-score | 0.00 | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.12 | 0.50 | 0.00 | 0.25 | 0.12 | 0.00 |
| Threshold rules (Sigma-style) | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.62 | 1.00 | 0.75 | 1.00 | 0.53 |
| Host WL features + logistic regression (supervised) [uses labels] | 0.08 | 0.25 | 0.08 | 0.17 | 0.17 | 0.12 | 0.12 | 0.12 | 0.38 | 0.00 | 0.00 | 0.03 |

## E3 Stealth sweep (recall)

| stealth | RefineMatch (full) | Threshold rules (Sigma-style) | WL-histogram anomaly (UNICORN-style) |
|---|---|---|---|
| 0.0 | 1.00 | 1.00 | 0.10 |
| 0.25 | 1.00 | 0.97 | 0.10 |
| 0.5 | 0.80 | 0.93 | 0.10 |
| 0.75 | 0.70 | 0.90 | 0.10 |
| 1.0 | 0.47 | 0.87 | 0.10 |

## E4 Robustness

Certified radius (minimum adversarial event edits needed to evade):

| Scenario | median (unconditional) | min | fraction ∞ | median if novelty is not manipulable |
|---|---|---|---|---|
| lateral_movement | ∞ | ∞ | 1.00 | ∞ |
| kerberoasting | 8 | 1 | 0.00 | 8 |
| network_scan | 13 | 6 | 0.00 | 16 |
| exfiltration | 1 | 1 | 0.00 | 1 |
| c2_beaconing | 3 | 2 | 0.00 | 4 |

Certificate soundness check: **0 violations in 141 attacks with fewer edits than the certified bound**.

Empirical detection rate vs. perturbation budget:

- delete: 0 → 1.00, 1 → 0.95, 3 → 0.75, 10 → 0.38
- noise: 0 → 1.00, 20 → 1.00, 100 → 1.00
- mimicry: 0 → 1.00, 3 → 1.00, 12 → 1.00
- jitter_s: 0 → 1.00, 120 → 0.98, 900 → 0.83
- beacon_jitter: 0 → 1.00, 2 → 1.00, 6 → 1.00

## E5 Streaming

- Keeping colours current: incremental TCR **16.5 µs/event** vs recomputing static WL 2306 µs/event (**×140**, over 800 events).
- End-to-end streaming detector: 9222 events/s (67 triggered match checks).
- Detection latency after the last attack event: network_scan: 0s, kerberoasting: 36s, lateral_movement: 133s, exfiltration: 219s

## E6 Campaign stitching

| stealth | best single-window score | campaign score | windows alerting | tactics |
|---|---|---|---|---|
| 0.0 | 1.00 | 1.00 | 4 | discovery → credential-access → lateral-movement → exfiltration |
| 0.6 | 1.00 | 1.00 | 3 | discovery → credential-access → lateral-movement |
| 0.9 | 1.00 | 0.99 | 2 | discovery → credential-access → lateral-movement |

## E7 Explanations

- 60/60 certificates independently verified against raw events; 60/60 tampered certificates rejected.
- Mean evidence size: 1.6 events per alert.

Example certificates:

```
ALERT lateral_movement [lateral-movement; T1021, T1550.002]  score=1.00 (critical)
  hosts: a=WS024(workstation), b=WS034(workstation), c=WS019(workstation)
  evidence (causal order):
    [1] 2023-11-18 14:21:40  WS024 -> WS034  auth_remote  (count=1)
    [2] 2023-11-18 14:27:21  WS034 -> WS019  auth_remote  (count=1)
  attack_sim=1.00  benign_sim=0.00  novelty=1.00  temporal=1.00  structural=1.00
  why not benign: no benign counterpart (admin_jump, helpdesk_support) matches these hosts
  unexplained: WS024(workstation)->WS034(workstation) 'auth_remote' cannot match any edge of admin_jump
  unexplained: WS034(workstation)->WS019(workstation) 'auth_remote' cannot match any edge of admin_jump
  search: 1 individualization(s), exhaustive
  robustness: certified radius inf edits (deletion >= inf, insertion >= inf)
```

```
ALERT kerberoasting [credential-access; T1558.003, T1087.002]  score=1.00 (critical)
  hosts: a=WS015(workstation), d=DC01(dc)
  evidence (causal order):
    [1] 2023-11-19 02:30:16  WS015 -> DC01  ldap  (count=1)
    [2] 2023-11-19 02:30:18  WS015 -> DC01  kerberos_tgs  (count=19)
  attack_sim=1.00  benign_sim=0.00  novelty=1.00  temporal=1.00  structural=1.00
  why not benign: no benign counterpart (service_ticket_renewal) matches these hosts
  unexplained: WS015(workstation)->DC01(dc) 'ldap' cannot match any edge of service_ticket_renewal
  unexplained: WS015(workstation)->DC01(dc) 'kerberos_tgs' cannot match any edge of service_ticket_renewal
  search: 0 individualization(s), exhaustive
  robustness: certified radius 10 edits (deletion >= 10, insertion >= inf)
```

```
ALERT network_scan [discovery; T1046, T1018]  score=1.00 (critical)
  hosts: s=WS035(workstation), t=ADM01(admin_ws)
  fact: WS035 contacted 23 distinct hosts via 'conn' (threshold 15)
  fact: 23 interchangeable hosts fit pattern node 't'
  evidence (causal order):
    [1] 2023-11-19 14:22:44  WS035 -> ADM01  conn  (count=1)
  attack_sim=1.00  benign_sim=0.00  novelty=1.00  temporal=1.00  structural=1.00
  why not benign: no benign counterpart (monitoring_sweep) matches these hosts
  unexplained: WS035(workstation)->ADM01(admin_ws) 'conn' cannot match any edge of monitoring_sweep
  search: 0 individualization(s), exhaustive
  robustness: certified radius 9 edits (deletion >= 9, insertion >= inf); 12 deletions if the novelty term cannot be manipulated
```

```
ALERT exfiltration [exfiltration; T1041, T1567, T1039]  score=0.88 (critical)
  hosts: a=WS014(workstation), f=FS01(fileserver), x=EVIL001(external)
  evidence (causal order):
    [1] 2023-11-20 02:26:51  WS014 -> FS01  smb_file  (count=7)
    [2] 2023-11-20 02:37:46  WS014 -> EVIL001  http_upload  (count=1)
  attack_sim=1.00  benign_sim=0.12  novelty=1.00  temporal=1.00  structural=1.00
  why not benign: closest benign template 'cloud_sync' explains only 12% of the weighted evidence
  unexplained: WS014(workstation)->EVIL001(external) 'http_upload' cannot match any edge of cloud_sync
  search: 0 individualization(s), exhaustive
  robustness: certified radius 1 edits (deletion >= 7, insertion >= 1)
```

```
ALERT c2_beaconing [command-and-control; T1071.001, T1573]  score=0.98 (critical)
  hosts: a=WS004(workstation), x=EVIL013(external)
  evidence (causal order):
    [1] 2023-11-20 14:26:39  WS004 -> EVIL013  http  (count=22)
  attack_sim=1.00  benign_sim=0.00  novelty=0.85  temporal=1.00  structural=1.00
  why not benign: no benign counterpart (update_polling) matches these hosts
  unexplained: WS004(workstation)->EVIL013(external) 'http' cannot match any edge of update_polling
  search: 0 individualization(s), exhaustive
  robustness: certified radius 2 edits (deletion >= 2, insertion >= inf); 3 deletions if the novelty term cannot be manipulated
```

## E8 Privacy-preserving sharing (org A → org B)

| Template | recall @B | FPR @B | privacy k-anon ok | tamper rejected |
|---|---|---|---|---|
| lateral_movement | 1.00 | 0.00 | True | True |
| kerberoasting | 1.00 | 0.00 | True | True |
| network_scan | 1.00 | 0.00 | True | True |
| exfiltration | 1.00 | 0.00 | True | True |
| c2_beaconing | 1.00 | 0.00 | True | True |

## E9 Individualization budget (8 symmetric remote-logon chains)

| depth | score | exhaustive | confidence | seconds |
|---|---|---|---|---|
| 0 | 0.00 | False | 0.52 | 0.008 |
| 1 | 0.93 | True | 1.00 | 0.028 |
| 2 | 0.93 | True | 1.00 | 0.028 |
| 3 | 0.93 | True | 1.00 | 0.028 |

_Total runtime 38s._
