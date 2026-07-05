# PLAUSIBLE-30 sign-off notes

Reviewer: automated literature review (web search per row), 2026-07-05.
Method: for each row, searched for a prior work that does the idea's **core**
contribution. KEEP only when no core-doing paper was found and the idea has a
defensible differentiation from the closest work. REMOVE when a paper does the
core, or when the differentiation is too thin to defend (ambiguity = noise).

**Result: 8 KEEP / 22 REMOVE.** The low keep-rate is itself the signal the
maintainer asked for — LLM-assisted curation of "genuinely open" was weak;
~73% of the candidate rows had clear or close prior art as of July 2026.

> Caveat: this is a search-based proxy for a domain expert's judgment. The three
> weakest KEEPs and three closest REMOVEs are flagged below; the maintainer may
> want to spot-check those before the CC-2.7 live run.

## KEEP (8) — signed off

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
