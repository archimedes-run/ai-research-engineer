<!-- Scientific Methodology Prompt for Algorithms Research -->
<!-- Domain-specific prompt for algorithms research methodology and best practices -->

# Algorithms Research Methodology Guidelines

## Research Workflow Standards

### Phase 1: Problem Understanding & Literature Review
- **Problem Characterization**:
  - State problem formally with inputs, outputs, and constraints
  - Identify problem class (decision, optimization, counting, etc.)
  - Define success metrics (time, space, approximation ratio, etc.)
  - Analyze special cases and boundary conditions
- **Literature Survey**:
  - Search Algorithm literature (SODA, STOC, FOCS, Algorithmica, etc.)
  - Document prior algorithms and their complexities
  - Identify gaps and opportunities for improvement
  - Note proven lower bounds and hardness results
- **Complexity Classification**:
  - Determine if problem is in P, NP, or proven NP-hard
  - Check for approximability results and known lower bounds
  - Identify related problems and known reductions
  - Assess practical vs. theoretical difficulty

### Phase 2: Complexity Analysis & Lower Bounds
- **Theoretical Lower Bounds**:
  - Information-theoretic arguments (e.g., comparison-based sorting lower bound)
  - Adversarial arguments (worst-case input construction)
  - Communication complexity and decision tree analysis
  - Conditional lower bounds (assuming P≠NP, etc.)
- **Upper Bounds from Literature**:
  - Document best known algorithms and complexities
  - Understand key techniques and ideas
  - Identify bottlenecks and optimization opportunities
  - Note gaps between upper and lower bounds
- **Hardness Classification**:
  - Is problem NP-hard? Provide reduction proof
  - Is approximation possible? What ratios are achievable?
  - Is parameterized efficient solvability possible (FPT)?
  - What is approximate complexity class?

### Phase 3: Algorithm Design
- **Design Paradigms**:
  - **Divide-and-Conquer**: Recursive decomposition into subproblems
  - **Dynamic Programming**: Optimal substructure and overlapping subproblems
  - **Greedy**: Local optimization and greedy choice property
  - **Network Flows**: Formulate as flow problems with min-cut/max-flow
  - **Linear/Integer Programming**: Relaxations and rounding
  - **Randomized**: Probabilistic algorithms and Las Vegas/Monte Carlo variants
  - **Approximation**: Polynomial-time algorithms with proven approximation guarantees
- **Algorithm Development**:
  - Start with simple correct algorithm (baseline)
  - Incrementally add optimizations
  - Document key insights and techniques
  - Analyze intermediate complexity improvements

### Phase 4: Correctness Verification
- **Formal Methods**:
  - Provide proof of algorithm correctness
  - State and verify loop invariants
  - Verify base cases and inductive steps
  - Check termination conditions
- **Informal Verification**:
  - Trace through small examples
  - Describe intuition and key ideas
  - Identify and handle edge cases
  - Verify postconditions
- **Testing Strategy**:
  - Unit tests for components
  - Integration tests for end-to-end behavior
  - Edge case testing (empty input, single element, boundary values)
  - Property-based testing with random inputs
  - Stress testing with large inputs

### Phase 5: Complexity Analysis
- **Time Complexity**:
  - Analyze worst, average, and best case behavior
  - Use asymptotic notation (Big-O, Big-Θ, Big-Ω)
  - Count elementary operations carefully
  - Account for data structure operations (search, insert, etc.)
  - Document hidden constants and practical factors
- **Space Complexity**:
  - Analyze auxiliary space requirements
  - Determine in-place vs. out-of-place variants
  - Document memory accesses and cache behavior
  - Estimate practical memory usage
- **Recurrence Relations**:
  - Establish recurrence for recursive algorithms
  - Solve using substitution, master theorem, or iteration
  - Verify solution against algorithm behavior

### Phase 6: Implementation & Optimization
- **Code Development**:
  - Implement algorithm with clean, documented code
  - Use efficient data structures appropriate for algorithm
  - Follow best practices (error handling, input validation)
  - Include comments explaining non-obvious parts
- **Optimization Techniques**:
  - Reduce constant factors in Big-O
  - Improve cache locality and memory access patterns
  - Exploit parallelization opportunities
  - Use appropriate low-level optimizations
  - Profile code to identify bottlenecks
- **Code Quality**:
  - Follow consistent style and naming conventions
  - Include unit tests and test coverage
  - Document assumptions and preconditions
  - Provide usage examples

### Phase 7: Empirical Evaluation
- **Benchmark Design**:
  - Create diverse test inputs:
    - Small inputs (verify correctness)
    - Large inputs (measure scalability)
    - Worst-case inputs (adversarial construction)
    - Random inputs (average case)
    - Real-world inputs (practical performance)
  - Vary input size: n, 2n, 4n, ... to measure scaling
  - Multiple runs to measure variance
- **Measurement Protocol**:
  - Measure wall-clock time (or CPU cycles with profiling tools)
  - Measure memory usage (peak and average)
  - Measure cache misses and other hardware metrics
  - Account for compilation flags and hardware differences
  - Use sufficient warm-up iterations
- **Comparison Baselines**:
  - Compare against baseline algorithms
  - Compare against state-of-the-art implementations
  - Compare against published results
  - Ensure fair comparison (same hardware, compiler, input format)
- **Statistical Analysis**:
  - Report mean, median, and standard deviation
  - Calculate confidence intervals
  - Test for statistical significance of differences
  - Identify outliers and anomalies
  - Analyze trends across input sizes

### Phase 8: Analysis & Interpretation
- **Theoretical vs. Practical**:
  - Explain differences between theoretical and empirical results
  - Attribute differences to constant factors, implementation, hardware
  - Validate theoretical analysis with empirical measurements
  - Identify cases where theory breaks down
- **Scalability Analysis**:
  - Measure speedup and efficiency for parallel algorithms
  - Analyze weak and strong scaling
  - Compare to theoretical predictions (Amdahl's law)
  - Identify communication bottlenecks
- **Comparative Analysis**:
  - Summarize performance differences to baselines
  - Identify which algorithm is best for which regime
  - Characterize algorithm trade-offs
  - Provide guidance on algorithm selection

### Phase 9: Documentation & Publication
- **Algorithm Description**:
  - Clear pseudocode with variable definitions
  - High-level intuition and key ideas
  - Worked examples on small inputs
  - Complexity summary (time, space, approximation)
- **Formal Analysis**:
  - Correctness proof (formal or sketch)
  - Complexity analysis with detailed derivation
  - Proof of optimality or approximation guarantee
  - Lower bound matching (if applicable)
- **Experimental Evaluation**:
  - Benchmark methodology and input characteristics
  - Performance results with statistical analysis
  - Comparison to baselines and prior work
  - Scalability and hardware efficiency analysis
- **Discussion**:
  - Significance and novelty of contributions
  - Comparison to existing work
  - Limitations and future directions
  - Practical implications and use cases

---

## Domain-Specific Methodological Standards

### For Sorting & Selection
- Compare against optimal comparison-based lower bounds
- Analyze stability and adaptive behavior on partially sorted data
- Measure cache efficiency (I/O complexity, external memory models)
- Consider parallel variants and efficient implementations
- Benchmark on realistic data distributions

### For Graph Algorithms
- Verify correctness on diverse graph structures (dense, sparse, weighted, etc.)
- Compare to standard library implementations
- Analyze performance on real graphs (social networks, web graphs, etc.)
- Measure scalability to large graphs (millions of nodes/edges)
- Consider specialized algorithms for restricted graph classes

### For Dynamic Programming
- Verify correctness on optimal substructure and overlapping subproblems
- Analyze space optimization (1D vs. 2D tables)
- Measure performance of top-down (memoization) vs. bottom-up
- Identify pruning and early termination opportunities
- Compare to specialized algorithms when available

### For Numerical Algorithms
- Analyze floating-point behavior and error accumulation
- Test numerical stability on ill-conditioned problems
- Compare to BLAS/LAPACK implementations
- Measure convergence rates and iteration counts
- Verify against exact solutions on tractable problems

### For Machine Learning Algorithms
- Analyze convergence rates and optimality guarantees
- Measure generalization with proper train/test splits
- Compare to established baseline implementations
- Study sensitivity to hyperparameters
- Test on diverse datasets and problem types

### For Approximation & Randomized Algorithms
- Prove approximation guarantee and tightness
- Analyze Las Vegas (correct, variable time) vs. Monte Carlo (fast, probabilistic)
- Measure probability of failure and average case behavior
- Compare to exact and other approximation algorithms
- Analyze practical vs. worst-case performance

---

## Quality Criteria & Standards

### Theoretical Quality
- ✅ Clear problem statement and formal definitions
- ✅ Rigorous complexity analysis with proven bounds
- ✅ Formal or detailed correctness argument
- ✅ Lower bounds demonstrating near-optimality
- ✅ Comparison to existing algorithms and literature
- ❌ Vague problem statements or informal definitions
- ❌ Unsubstantiated complexity claims
- ❌ Missing correctness argument
- ❌ Ignoring better known algorithms
- ❌ Overclaiming novelty

### Practical Quality
- ✅ Working implementation with clean code
- ✅ Comprehensive empirical evaluation
- ✅ Fair comparison against baselines
- ✅ Realistic measurement methodology
- ✅ Analysis of practical vs. theoretical differences
- ❌ No working implementation
- ❌ Unfair comparisons (different hardware, compilers)
- ❌ Measurement errors and statistical issues
- ❌ Cherry-picked results
- ❌ Ignoring constant factors

### Completeness
- ✅ Both theoretical and empirical analysis
- ✅ Full documentation and usage examples
- ✅ Publicly available code and test data
- ✅ Sufficient detail for reproduction
- ✅ Discussion of limitations and future work
- ❌ Theory without practical validation
- ❌ Experiments without theoretical context
- ❌ Proprietary code or data
- ❌ Missing implementation details
- ❌ Overclaimed generality

---

## Red Flags & Issues to Address

- ❌ **Incorrect complexity analysis**: Off-by-one errors, wrong recurrence solving, hidden operations
- ❌ **Unfair comparisons**: Different languages, compiler flags, hardware, input formats
- ❌ **Measurement bias**: Timing includes I/O, garbage collection, or system noise
- ❌ **Statistical issues**: Single run, no confidence intervals, ignoring variance
- ❌ **Overstated novelty**: Algorithm is minor variant of prior work
- ❌ **Missing lower bounds**: No comparison to theoretical limits
- ❌ **Incomplete evaluation**: Only best-case inputs or limited scales
- ❌ **Reproducibility issues**: Insufficient detail or unavailable code
- ❌ **Incorrect proofs**: Logical gaps, unstated assumptions, unchecked edge cases
- ❌ **Practical unreality**: Algorithm assumes unlimited memory, perfect hardware, etc.

---

## Success Metrics for Algorithm Research

1. **Novelty**: Does work introduce genuinely new technique or significantly improve existing?
2. **Rigor**: Are theoretical claims proven and empirical claims verified?
3. **Significance**: Does result improve complexity, practical performance, or applicability?
4. **Completeness**: Does work cover both theory and practice, analysis and implementation?
5. **Clarity**: Can result be understood, verified, and reproduced by others?
6. **Reproducibility**: Is code available and sufficient detail provided?
7. **Generality**: Does result apply to broad problem class or is it specialized?
8. **Impact**: Does result influence future research or enable new applications?

---

---

# MVPT Translation for Algorithms Domain

This section explains how the universal MVPT novelty framework (from `novelty_scorer.md`) applies specifically to algorithms research.

## M - Method Novelty in Algorithms
**What counts as "new method":**
- ✓ New algorithm class solving problem with better complexity
- ✓ First algorithm for previously unsolvable problem
- ✓ Complexity improvement on known problem (e.g., O(n²) → O(n log n))
- ✓ Novel algorithmic technique with broad applicability
- ✗ NOT: Implementation optimization of known algorithm (M:2)
- ✗ NOT: Constant factor improvement (M:2)
- ✗ NOT: Combination of existing techniques without new principle (M:2)

**Scoring Guide:**
- M:9-10 = Entirely new algorithm class or paradigm (e.g., FFT was this)
- M:7-8 = Significant complexity reduction on known problem
- M:5-6 = Implementation optimization or engineering improvement
- M:3-4 = Minor variant of known algorithm
- M:0-2 = Re-implementing published algorithm

---

## V - Verifiability in Algorithms (8-Point Checklist)

**Verification Checklist:**
1. **Code Released?** GitHub/Zenodo with working implementation → 1 point
2. **Edge Cases Tested?** Empty input, single element, boundary conditions → 1 point
3. **Large Inputs Tested?** Scaling studies to n = 10⁶ or 10⁷ → 1 point
4. **Time/Space Complexity Verified?** Empirical scaling matches theory → 1 point
5. **Correctness Proof Provided?** Formal or detailed correctness argument → 1 point
6. **Baseline Code Included?** Can compare against prior methods → 1 point
7. **Timing Results Reproducible?** ±10% variance with same input size → 1 point
8. **Others Can Replicate?** Sufficient detail, no missing steps → 1 point

**Scoring:**
- 7-8/8 passing = 7.5-8.5 points (fully reproducible)
- 5-6/8 passing = 5.5-6.5 points (mostly reproducible)
- 3-4/8 passing = 3.5-4.5 points (partially reproducible)
- <3/8 passing = 1-3 points (barely reproducible)

**FATAL**: If V < 3, reject immediately (algorithm must be verifiable).

---

## P - Principle Power in Algorithms

**What "explaining why it works" means:**
- ✓ **Proof of correctness**: Formal or detailed argument that algorithm produces correct output
- ✓ **Complexity analysis**: Rigorous proof of time/space bounds with explanation
- ✓ **Key insight explanation**: Why does this approach achieve better complexity?
- ✗ NOT: "Empirically faster" without proof
- ✗ NOT: Code without explanation

**Scoring Guide:**
- P:9-10 = Formal correctness proof + detailed complexity analysis
- P:7-8 = Correctness proof (informal) + complexity justified
- P:5-6 = Algorithm works empirically, complexity explained but not proven
- P:3-4 = Vague explanation, complexity unclear
- P:0-2 = Black box, "it works"

**Example Interpretations:**
- QuickSort with divide-and-conquer proof + O(n log n) average case = P:8
- "Algorithm is faster" without proof = P:1
- FFT with signal processing explanation + O(n log n) proof = P:9

---

## T - Transfer in Algorithms
### **SPECIAL DEFINITION FOR ALGORITHMS DOMAIN**

**Important**: For Algorithms, T does **NOT** mean cross-domain applicability.  
Instead, T measures: **Theoretical Generalization & Scalability**

**What "generalization" means in Algorithms:**
- ✓ **Broad input class**: Works for any input in problem class (not just special cases)
- ✓ **Asymptotic scalability**: Handles n → ∞ efficiently, proven complexity
- ✓ **General problem variant**: Applies beyond one specific problem formulation
- ✗ NOT: Only works on specific graph structures (e.g., "only for DAGs")
- ✗ NOT: Only efficient up to n < 10,000 (doesn't scale)
- ✗ NOT: Only for one instance (M-specific traveling salesman, specific knapsack)

**Scoring Guide:**
- T:9-10 = Works for any input in broad problem class, scales asymptotically
- T:7-8 = Works for broad class, scales well
- T:5-6 = Might generalize with modification
- T:3-4 = Limited to specific problem or constraint
- T:0-2 = Only handles one edge case or instance

**Examples:**
- QuickSort: Works for any comparable data, O(n log n) average → T:9
- Dijkstra: Works for any weighted graph, O(E log V) → T:9
- Algorithm for 5-node graphs: Only n=5, not generalizable → T:1
- Optimization for DAGs: Only that specific structure → T:2
- "Fast algorithm for this specific matrix" (unique structure) → T:1
- Graph algorithm proven for n < 1000: Doesn't scale asymptotically → T:2

---

## Red Flags Specific to Algorithms

- ❌ **Complexity not proven**: "Faster than X" without proof
- ❌ **Only toy examples**: "Works on graphs with 10-100 nodes"
- ❌ **Incorrect proofs**: Logical gaps, unstated assumptions
- ❌ **No baseline code**: Can't compare against prior work
- ❌ **Edge cases ignored**: "Assumes well-formed input"
- ❌ **Unfair comparison**: Different languages, compiler optimizations
- ❌ **Worst-case hidden**: "Average case O(n), but worst case O(n²)" not addressed
- ❌ **Generality overclaimed**: "Works for all graphs" but actually only for directed acyclic graphs
- ❌ **Scalability not tested**: "Should work for larger n" without verification
- ❌ **Code unavailable**: "Proprietary implementation"