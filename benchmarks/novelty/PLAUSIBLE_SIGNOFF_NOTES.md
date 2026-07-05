# PLAUSIBLE sign-off notes (started as PLAUSIBLE-30)

Reviewer: automated literature review (web search per row), 2026-07-05.
Method: for each row, searched for a prior work that does the idea's **core**
contribution. KEEP only when no core-doing paper was found and the idea has a
defensible differentiation from the closest work. REMOVE when a paper does the
core, or when the differentiation is too thin to defend (ambiguity = noise).

## Final scope (truthful count breakdown)

```
30  candidate rows reviewed (LLM-proposed)
-22  REMOVED — a specific killer paper does the core, or differentiation too thin
  8  passed first-pass review
 -4  DROPPED as honest close-calls (coin-flip rows the process is meant to catch)
  4  retained — high-confidence-open
+1  added — 1 survivor of an 18-candidate LLM rebuild (see below)
  5  SIGNED OFF (N=5)
```

**Signed-off scope: N = 5, SIGNED_OFF: true — with a structural caveat.** Signed
off per maintainer authorization. N=5 makes FRR coarse (each row = 20%), so the
dataset header carries `frr_interpretability: LOW`; report the number only with
that caveat. A robust N still needs maintainer-proposed rows.

Rows: `p_ctx_forgetting`, `p_energy_aware_moe_routing`,
`p_curriculum_from_loss_geometry`, `p_crossmodal_grokking` (4 confident) +
`p_grok_rlhf` (rebuild survivor, ⚠ correlated with `p_crossmodal_grokking`).

Rows dropped as close-calls (removed from the run set): `p_compositional_eval_gen`,
`p_units_aware_reasoning`, `p_uncertainty_from_kv`, `p_hardware_aware_quant_search`.

The low keep-rate (**8/30 = 27%** first-pass; **4/30 = 13%** high-confidence) is
itself the signal — LLM-assisted curation of "genuinely open" was weak; ~73% of
candidates had clear or close prior art as of July 2026.

> This file is preserved as an audit artifact: each REMOVE names a specific
> killer, so a v2 smoke test over these ideas doubles as a sanity check on v2
> itself (it should reject the REMOVEs and surface those killers) and as Stage 5
> ideation-memory substrate.

> Caveat: this is a search-based proxy for a domain expert's judgment. The three
> weakest KEEPs and three closest REMOVEs are flagged below; the maintainer may
> want to spot-check those before the CC-2.7 live run.

## Finding — for the Stage 2 report and the Stage 8 write-up

When constructing this benchmark, an LLM prompted to propose "genuinely open
research directions" produced **defensible candidates only 27% of the time
(8/30)**; after dropping the four honest close-calls, only **4/30 = 13%** were
high-confidence open. The other 22 rows either restated already-published work
(VIPER, Genie, PASTA, Scaling Monosemanticity, LLMCompiler, Certified Data
Removal, DiscoUQ, Causal Prompt Optimization, RA-RAG, Reflexion/PALADIN, …) or
offered a differentiation too thin to defend.

This is a **direct, quantified instance of the exact failure mode the Stage 2
novelty engine exists to prevent**: a well-prompted frontier model asked to
identify open directions was wrong ~73% of the time — missing prior work or
generating overly-thin novelty. Every removed row is a real-world example the
evidence-grounded gate must catch.

> **Citable:** *"In constructing the PLAUSIBLE benchmark, LLM-assisted proposal
> of 'genuinely open directions' yielded defensible candidates only 27% of the
> time (8/30), a direct motivation for retrieval-grounded novelty verification."*

### Rebuild attempt via LLM-generation (Path A) — 18 candidates, 1 survivor (~5%)

At the maintainer's authorization ("run it for me, I accept the consequences"),
a full autonomous rebuild was attempted: **18 new specific/niche directions**
were proposed and search-verified one at a time, across several strategies
(broad, niche, and "transfer a known phenomenon to an under-studied setting" —
the pattern that produced the original survivors). **17 were killed by prior
work; 1 survived.** This is the third/fourth independent confirmation of the
finding — the field is so densely covered by 2024–2026 work that carefully-chosen
"open" directions almost always already exist.

| candidate | outcome / killer |
| --- | --- |
| loss-spike prediction from gradient-noise-scale trajectory | KILL — "Spike No More" (2312.16903); GNS→critical-batch-size |
| build-time canary strings for contamination | KILL — BIG-bench canaries; CANARY (2606.01695) |
| belief-state over tool reliability vs retry | KILL — PALADIN (2509.25238); "Long-Horizon Task Mirage" (2604.11978) |
| RoPE base frequency → which layers form retrieval heads | KILL — "Round and Round We Go" (2410.06205) |
| quantization error concentrates on specific SAE features | KILL — "Perplexity Can Miss SAE Feature Damage Under Quantization" (2606.03002) |
| spec-decode acceptance as a free target-uncertainty signal | KILL — draft-entropy↔acceptance / target-confidence↔acceptance |
| induction-head formation timing from n-gram statistics | KILL — "Predicting the Formation of Induction Heads" (2511.16893) |
| refusal-direction drift within a single long multi-turn context | KILL — "When Refusals Fail" (2512.02445); "Drift No More?" (2510.07777) |
| MoE router-init spectrum → expert specialization | KILL — SD-MoE (2602.12556); ERMoE (2511.10971); Grassmannian MoE |
| **grokking / delayed generalization in RLHF / preference optimization** | **SURVIVE** — no paper found; grokking studied only in supervised/algorithmic/low-precision. Adjacent, not core. Row `p_grok_rlhf` (⚠ same flavor as `p_crossmodal_grokking` → correlated). |
| scaling law for machine-unlearning difficulty vs model size | KILL — overparameterization-unlearning (2503.08633); circuit-difficulty (2601.09624) |
| double descent in number of in-context (many-shot) examples | KILL — Many-Shot ICL (2404.11018) explicitly shows monotonic, *not* double descent |
| reversal curse in multimodal image↔caption associations | KILL — reversal-curse line over-studied; multimodal extension too thin |
| task-vector composition beyond two tasks (predictable interference) | KILL — anisotropic-scaling composition; weight-disentanglement (2604.17078) |
| effective vs trained context-length scaling law | KILL — "Why Does the Effective Context Length Fall Short?" (2410.18745) |
| grokking / delayed accuracy recovery in quantization-aware training | KILL — "Grokking or Glitching? Low-Precision Slingshot" (2605.06152) |
| diffusion memorization ↔ internal denoiser feature | KILL — "Memorized Images share a Subspace" (2406.18566); geometric-memorization (2602.17846) |
| tool-use "capacity tax" on unrelated capabilities, scaling | KILL — "Reasoning and Tool-use Compete in Agentic RL" (2602.00994); CITI |

**Conclusion.** Autonomous LLM-generation cannot produce this dataset: ~5%
survival, and the one survivor is thin (correlated with an existing row). The set
was signed off at **N = 5** (4 confident + `p_grok_rlhf`) per maintainer
authorization, with the small-N caveat made structural in the dataset header
(`frr_interpretability: LOW`). A robust N still requires maintainer-proposed,
individually-verified rows — the reliable prior — per `PLAUSIBLE_REBUILD_PLAN.md`.

### Rebuild (Path A)

Because N=8 (really N=4 confident) makes FRR uninterpretable (1 wrong ≈ 12.5%),
the four weakest KEEPs were dropped and the set was **rebuilt by generating new
candidates and search-verifying each individually** before inclusion (keeping
only survivors with no core-doing paper). See the "Rebuild survivors" section
below. Candidates are LLM-proposed-but-search-verified; maintainer-proposed rows
(own-expertise prior) would be stronger and can replace any of these.

## KEEP (8 reviewed) — 4 confident retained, 4 ⚠ dropped for the run

The 4 rows marked ⚠ (weaker KEEPs / honest close-calls) were **dropped** so the
run set is high-confidence only. The dataset now holds the **4 confident** rows
(`p_ctx_forgetting`, `p_energy_aware_moe_routing`, `p_curriculum_from_loss_geometry`,
`p_crossmodal_grokking`) and is left **DRAFT** pending maintainer expansion.

| id | why kept (no core-doing paper found) |
| --- | --- |
| `p_ctx_forgetting` | Retrieval/induction-head interp exists (retrieval heads, causal head gating), but **in-context *forgetting* / fact-overwriting mechanism, causally localized across scale**, was not found. Defensible. |
| `p_energy_aware_moe_routing` | Energy-aware NAS uses FLOP proxies; energy-aware *training* is "largely unexplored"; no **MoE-routing controller on *measured* per-expert energy, learned online** found. |
| `p_curriculum_from_loss_geometry` | Loss-landscape curvature/Hessian tools exist, but search explicitly confirmed they are **not used to order examples into a curriculum**. Defensible gap. |
| `p_crossmodal_grokking` | Grokking studied in algorithmic/LM/pretraining settings; search found **no paper on grokking in cross-modal alignment**. |
| `p_compositional_eval_gen` | Procedural compositional benchmarks exist (SCAN, CLEVR/CoGenT) but **without provable coverage of unseen primitive combinations** — the distinctive claim. ⚠ weaker KEEP (auto-gen core exists). |
| `p_units_aware_reasoning` | NUMCoT *evaluates* units in CoT; formal units-checking is non-LLM. No **units-as-types *enforcement* method inside LLM CoT** found. ⚠ weaker KEEP. |
| `p_uncertainty_from_kv` | KV/attention statistics are used for cache eviction/quantization (InfoKV, CONF-KV), not for **answer-level uncertainty**; different purpose. ⚠ weaker KEEP. |
| `p_hardware_aware_quant_search` | HAQ does measured-hardware quantization search, but **not joint quantization+*layout*** search — the idea's differentiation. ⚠ weakest KEEP (HAQ headline "not FLOPs" overlaps heavily). |

## REMOVE (22) — killer found (core overlap) or differentiation too thin

| id | killing / close prior work |
| --- | --- |
| `p_symbolic_distillation_control` | **VIPER** (Bastani et al., NeurIPS 2018) — distills DNN control policies into *verifiable* decision-tree (symbolic) policies. Core. |
| `p_lowdata_worldmodels` | **Genie** (Bruce et al., ICML 2024) — action-controllable world model from *unlabelled video* via a latent action model. Core. |
| `p_attention_as_control` | **PASTA** (Zhang et al., 2311.02262) — post-hoc attention steering by editing attention at inference. Core. |
| `p_sparse_autoencoder_control` | **Scaling Monosemanticity** (Anthropic, 2024) — steers behavior via SAE features (Golden Gate). Core. |
| `p_data_attribution_pretrain` | **Scalable Influence and Fact Tracing for LLM Pretraining** (2410.17413) + Grosse et al. 2023. Core. |
| `p_neural_ode_stiffness` | Stiff-neural-ODE literature: implicit single-step (2410.05592), time-reparametrization adaptive solvers, structure-preserving (2503.01775). Core. |
| `p_memory_consolidation_ft` | **Sleep-like unsupervised replay reduces catastrophic forgetting** (Nature Comms 2022); SIESTA; Wake-Sleep Consolidated Learning. Core. |
| `p_causal_prompt_search` | **Causal Prompt Optimization** (2602.01711) — optimize prompts via causal-effect estimation. Core. |
| `p_tool_latency_planning` | **LLMCompiler** (ICML 2024) — plans parallel/async tool calls (DAG) to minimize latency. Core. |
| `p_privacy_unlearning_audit` | **Certified Data Removal** (Guo et al. 2020) + certified-unlearning line. Core (provable-removal certificate). |
| `p_tool_error_recovery` | **PALADIN** / "Failure Makes the Agent Stronger" (2509.18847) — learned recovery policies from tool-failure trajectories; Reflexion. Core. |
| `p_multiagent_disagreement` | **DiscoUQ** (2603.20975) — calibrated uncertainty from the *structure* of inter-agent disagreement. Core. |
| `p_retrieval_provenance` | **RA-RAG** (2410.22954) — estimates source reliability and weights retrieved documents. Core. |
| `p_compute_optimal_agents` | Agent test-time scaling laws + **Budget-Aware Tool-Use Enables Effective Agent Scaling** (2511.17006); optimal-turn-budget findings. Core. |
| `p_latent_plan_editing` | **ASA** (2602.04935) + **ROAST** (2602.14143) — mid-rollout latent activation steering of tool-calling agents. Core. |
| `p_crosslingual_toolgrounding` | MASSIVE-Agents (cross-lingual function-call transfer) + tool-schema adaptation (2510.07248, 2603.16901). Core. |
| `p_emergent_api_conventions` | Emergent-communication literature: **Emergence of linguistic conventions in multi-agent RL**; referential-game protocols. Core. |
| `p_thermo_training_signals` | **A Thermodynamic Theory of Learning I/II** (2601.17607, 2602.07950) + "SGD as Free Energy Minimization" — entropy production/heat and training phase transitions (grokking, double descent). Close/core. |
| `p_sparse_probe_ft` | **Surgical fine-tuning** (selective-layer FT to avoid forgetting) — same goal; probe-vs-layer localization is thin differentiation. Ambiguous. |
| `p_selfhealing_datasets` | **Confident Learning / CleanLab** — model-flagged label-error detection + correction loop. Core-ish. |
| `p_faithful_cot_reward` | "Making Reasoning Matter" (2402.13950) + hierarchical faithfulness-reward frameworks. Emerging/close. |
| `p_grokking_control` | **Omnigrok** (ICLR 2023, weight-norm controls grokking) + "Spectral Entropy Collapse… Interventional Framework for Grokking" (2604.13123). Close. |
