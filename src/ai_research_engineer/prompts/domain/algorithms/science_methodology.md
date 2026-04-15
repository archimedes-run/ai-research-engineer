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