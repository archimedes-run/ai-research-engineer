<!-- Scientific Methodology Prompt for Physics -->
<!-- Domain-specific prompt for physics research methodology and best practices -->

# Physics Research Methodology Guidelines

## Research Workflow Standards

### Phase 1: Literature Review & Theoretical Foundation
- **Scope**: Identify key papers in the field (search arXiv, Nature Physics, Phys. Rev., etc.)
- **Theory Building**: Extract fundamental equations, constants, and assumptions from papers
- **Gap Identification**: Document unresolved questions, conflicting results, and open problems
- **Novelty Assessment**: Ensure proposed work addresses genuine scientific gaps

### Phase 2: Hypothesis Formulation
- **Clarity**: State hypothesis in testable, quantitative terms
- **Grounding**: Reference specific theory or empirical gap justifying the hypothesis
- **Predictions**: Derive measurable predictions with error estimates
- **Falsifiability**: Define conditions under which hypothesis would be rejected

### Phase 3: Experimental/Computational Design
- **Methodology Selection**:
  - Experimental: apparatus design, measurement protocols, error mitigation
  - Numerical: algorithms, computational resources, convergence criteria
  - Theoretical: mathematical derivations, approximations, validity limits
- **Control Design**: Identify confounding variables and mitigation strategies
- **Sample Planning**: Calculate required sample sizes, data collection duration, or computational grid density

### Phase 4: Data Collection & Validation
- **Instrumentation**: Verify calibration, accuracy specs, and operational ranges
- **Quality Control**: Implement real-time checks for anomalies, data corruption, or systematic errors
- **Documentation**: Record all environmental conditions, parameter values, and procedural deviations
- **Uncertainty Quantification**: Track systematic and random errors throughout collection

### Phase 5: Data Analysis
- **Preprocessing**: Clean data, handle outliers, correct for known systematic errors
- **Statistical Methods**: Apply appropriate tests (t-tests, ANOVA, regression, etc.)
- **Visualization**: Create plots with error bars, confidence regions, and theoretical predictions
- **Sensitivity Analysis**: Test robustness to parameter variations and assumption changes

### Phase 6: Result Interpretation
- **Comparison to Theory**: Quantify agreement/disagreement with predictions
- **Literature Context**: Situate findings relative to existing knowledge
- **Mechanism Identification**: Propose physical mechanisms explaining results
- **Limitation Discussion**: Acknowledge experimental constraints and their impact

### Phase 7: Manuscript Preparation
- **Structure**: Abstract → Introduction → Methods → Results → Discussion → Conclusion
- **Figure Quality**: High-resolution plots with clear labels, legends, and captions
- **Equation Presentation**: Use consistent notation, define all symbols, provide derivations
- **Reproducibility**: Include sufficient detail for independent replication

---

## Domain-Specific Methodological Standards

### Classical/Statistical Mechanics
- **Conservation Laws**: Verify energy, momentum, and angular momentum conservation
- **Symmetries**: Identify and exploit symmetries (translational, rotational, gauge)
- **Limit Analysis**: Verify behavior in limiting cases (zero temperature, infinite size, weak/strong coupling)
- **Phase Transitions**: Characterize critical behavior, order parameters, and critical exponents

### Thermodynamics & Statistical Physics
- **Ensemble Selection**: Justify use of microcanonical, canonical, or grand-canonical ensemble
- **Thermodynamic Limits**: Verify extensive properties and scaling with system size
- **Fluctuations**: Quantify thermal fluctuations and their observational signatures
- **Entropy**: Calculate and interpret entropy changes, verify Second Law

### Electromagnetism & Optics
- **Field Equations**: Verify Maxwell equations and constitutive relations
- **Boundary Conditions**: Properly specify conditions at interfaces and asymptotic regions
- **Symmetries**: Exploit gauge freedom and simplification opportunities
- **Radiation Damping**: Account for back-reaction effects in coupled systems

### Quantum Mechanics
- **State Representation**: Choose appropriate basis (position, momentum, energy eigenstates, etc.)
- **Measurement Protocol**: Define measurement procedure and collapse model
- **Entanglement**: Quantify correlations (Bell parameters, concurrence, mutual information)
- **Approximations**: Verify validity of perturbation theory, semiclassical limits, etc.

### Computational Methods
- **Discretization**: Choose appropriate mesh, grid, or basis set
- **Convergence**: Verify convergence with resolution refinement (scaling studies)
- **Stability**: Analyze stability criteria (CFL conditions, Von Neumann analysis)
- **Benchmarking**: Validate against analytical solutions or published results

---

## Quality Criteria & Robustness

### Experimental Quality
- **Repeatability**: Report standard deviations or confidence intervals for multiple runs
- **Systematic Error Control**: Document and minimize instrumental drift, calibration errors
- **Blind Analysis**: When possible, perform analysis without knowledge of expected results
- **Negative Controls**: Include experiments designed to fail to verify detection capability

### Theoretical Quality
- **Mathematical Rigor**: Ensure derivations are sound and approximations justified
- **Physical Intuition**: Provide physical explanations alongside mathematical results
- **Numerical Verification**: When possible, verify analytical results numerically
- **Generalizability**: Identify domain of validity and applicability to other systems

### Computational Quality
- **Code Verification**: Compare numerical results to analytical solutions in simple cases
- **Code Validation**: Compare computational predictions to experimental/observational data
- **Documentation**: Include detailed comments explaining algorithms and parameter choices
- **Reproducibility**: Provide sufficient detail and code to enable independent verification

---

## Literature Standards for Physics Research

- **arXiv**: Preprint server for rapid dissemination (e.g., arXiv:2401.xxxxx)
- **Peer-Reviewed Journals**: 
  - High-impact: Nature Physics, Science, Physical Review Letters
  - Field-specific: Physical Review A/B/C/D/E, Physics of Fluids, etc.
- **Conferences**: Present preliminary results at major conferences (APS March Meeting, etc.)
- **Citation Practices**: Use standard physics citation formats (AIP/APS style)

---

## Error Reporting & Uncertainty Communication

- **Absolute vs. Relative**: Report both absolute and relative uncertainties
- **Systematic vs. Random**: Separately quantify and document both error sources
- **Confidence Levels**: Specify confidence intervals (typically 95% or 68%)
- **Propagation**: Show error propagation calculations for derived quantities
- **Asymmetric Errors**: Use asymmetric error bars when appropriate (log scales, truncated distributions)

---

## Red Flags & Issues to Address

- ❌ **Unexplained discrepancies** between theory and experiment > 3σ
- ❌ **Missing uncertainty estimates** on any reported quantity
- ❌ **Insufficient literature context** (citing only 3-5 papers)
- ❌ **Unclear methodology** that prevents replication
- ❌ **Cherry-picked results** without mentioning failed attempts
- ❌ **Overclaimed significance** without statistical justification
- ❌ **Ignored systematic errors** or unvalidated assumptions

---

## Success Metrics for Physics Research

1. **Novelty**: Does work address previously unstudied regime or propose new phenomenon?
2. **Significance**: Do results impact understanding or enable new applications?
3. **Rigor**: Are methods sound and conclusions well-supported?
4. **Clarity**: Can independent researchers understand and replicate?
5. **Impact**: Do results appear publishable in peer-reviewed venues?

---

---

# MVPT Translation for Physics Domain

This section explains how the universal MVPT novelty framework (from `novelty_scorer.md`) applies specifically to physics research.

## M - Method Novelty in Physics
**What counts as "new method":**
- ✓ Novel experimental apparatus (new detector, new measurement approach)
- ✓ Novel theoretical framework predicting previously unexplained phenomenon
- ✓ First direct observation/measurement of previously predicted but unseen phenomenon
- ✓ New computational technique enabling simulation of previously intractable regime
- ✗ NOT: Higher precision measurement on existing apparatus (M:3)
- ✗ NOT: Applying existing experiment to new material (M:2)
- ✗ NOT: Incremental refinement of known theory (M:2)

**Scoring Guide:**
- M:9-10 = Entirely new experimental technique or theoretical paradigm
- M:7-8 = Novel apparatus design or theoretical framework with justification
- M:5-6 = Better measurement precision or computational efficiency
- M:3-4 = Same apparatus with modifications
- M:0-2 = Repeating published experiment

---

## V - Verifiability in Physics (8-Point Checklist)

**Verification Checklist:**
1. **Apparatus Specs Fully Documented?** Design drawings, component specifications → 1 point
2. **Calibration Procedure Detailed?** How to calibrate, calibration standards → 1 point
3. **Measurement Uncertainty Quantified?** σ_systematic and σ_random documented → 1 point
4. **Analysis Code Provided?** Scripts for data reduction released → 1 point
5. **Raw Data Available?** Access to original measurements provided → 1 point
6. **Independent Verification?** Another group confirmed results → 1 point
7. **Systematic Errors Addressed?** Known systematics identified and corrected → 1 point
8. **Results Consistent Across Runs?** Multiple independent measurements agree → 1 point

**Scoring:**
- 7-8/8 passing = 7.5-8.5 points (fully reproducible)
- 5-6/8 passing = 5.5-6.5 points (mostly reproducible)
- 3-4/8 passing = 3.5-4.5 points (partially reproducible)
- <3/8 passing = 1-3 points (barely reproducible)

**FATAL**: If V < 3, reject immediately (science requires repeatability).

---

## P - Principle Power in Physics

**What "explaining why it works" means:**
- ✓ **Theory-experiment agreement**: Theoretical prediction matches measurement within stated uncertainty
- ✓ **Physical mechanism**: Clear explanation of what physical process produces observed effect
- ✓ **Mechanistic validation**: Supporting experiments isolating the mechanism
- ✗ NOT: Just measurement data ("we observed X")
- ✗ NOT: Vague explanation ("quantum effects")

**Scoring Guide:**
- P:9-10 = Theory predicts outcome + measurements confirm within stated uncertainty
- P:7-8 = Theory explains + supporting mechanisms isolated
- P:5-6 = Measurement consistent with theory, mechanism partially understood
- P:3-4 = Hand-wavy mechanism explanation
- P:0-2 = Black box observation, "we don't know why"

**Example Interpretations:**
- Higgs discovery: Theory predicts properties precisely, measurements confirm = P:9
- New phase transition: Theory predicts critical point, measurements verify = P:8
- "We observed new particle" without theoretical prediction = P:2

---

## T - Transfer in Physics

**What "generalization" means:**
- ✓ **Multi-material**: Phenomenon works in different materials/substrates
- ✓ **Multi-scale**: Effect observable at different length/time scales
- ✓ **Multi-regime**: Prediction valid across different parameter regimes
- ✗ NOT: Only this specific sample
- ✗ NOT: Only at one temperature/pressure condition

**Scoring Guide:**
- T:9-10 = Works across materials, scales, and regimes
- T:7-8 = Works in multiple materials or conditions
- T:5-6 = Might generalize with modification
- T:3-4 = Specific to one material or condition
- T:0-2 = Single sample, single condition

**Examples:**
- Gravitational waves (detected in multiple events, multiple detectors) = T:9
- Superconductivity in multiple materials, various temperatures = T:8
- "Observed in this specific crystal structure" = T:2
- "Effect only at 4.2 K" = T:1

---

## Red Flags Specific to Physics

- ❌ **Systematic error uncorrected**: "Background not subtracted"
- ❌ **Uncertainty not quantified**: "The result is approximately X"
- ❌ **No comparison to theory**: Just experimental observation with no prediction test
- ❌ **Insufficient documentation**: "We built an apparatus" with no specs
- ❌ **No independent check**: Only one group reported this
- ❌ **Unvalidated assumptions**: "Assumes ideal conditions"
- ❌ **Theory-experiment mismatch unexplained**: 5σ disagreement with no discussion
- ❌ **Cherry-picked samples**: "Best of 20 samples tested"
- ❌ **Hardware not reproducible**: Custom equipment, hard to rebuild