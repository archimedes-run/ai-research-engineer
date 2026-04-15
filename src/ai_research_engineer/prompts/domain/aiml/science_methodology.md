<!-- Scientific Methodology Prompt for AI/ML -->
<!-- Domain-specific prompt for machine learning research methodology and best practices -->

# AI/ML Research Methodology Guidelines

## Research Workflow Standards

### Phase 1: Problem Definition & Literature Review
- **Problem Characterization**:
  - Clearly define prediction task (supervised, unsupervised, reinforcement learning)
  - Specify input/output spaces and data types
  - Identify success metrics aligned with application
  - Document constraints (latency, memory, computational budget)
- **Literature Survey**:
  - Search ML conferences: NeurIPS, ICML, ICLR, AAAI, IJCAI, CVPR, ICCV, EMNLP
  - Search journals: JMLR, IEEE TPAMI, ACM Computing Surveys
  - Document state-of-the-art methods and baseline performance
  - Identify novelty opportunities and underexplored directions
  - Note published datasets and benchmarks available
- **Benchmark & Dataset Selection**:
  - Choose standard benchmarks when available (ImageNet, CIFAR, MNIST, UCF101, etc.)
  - Document dataset statistics (size, class balance, feature distributions)
  - Note train/validation/test split methodology
  - Identify potential data issues (label noise, ambiguity, outliers)

### Phase 2: Baseline Development
- **Classical Baselines**:
  - Logistic regression (classification), linear regression (regression)
  - Decision trees, random forests, gradient boosting
  - Support vector machines with various kernels
  - K-nearest neighbors with different distance metrics
- **Deep Learning Baselines**:
  - Standard architectures (ResNet for vision, BERT for NLP, LSTM for sequences)
  - Pre-trained models when available (ImageNet-pretrained CNN, language models)
  - Simple neural networks (1-2 hidden layers) as sanity check
- **Baseline Documentation**:
  - Report performance with proper evaluation metrics
  - Document hyperparameters and optimization procedure
  - Include learning curves showing convergence
  - Analyze baseline performance characteristics

### Phase 3: Data Preprocessing & Feature Engineering
- **Data Cleaning**:
  - Handle missing values appropriately (imputation, removal)
  - Identify and document outliers
  - Check for and remove duplicate examples
  - Verify label correctness and consistency
- **Feature Engineering** (if applicable):
  - Extract meaningful features from raw data
  - Normalize/standardize numerical features appropriately
  - Encode categorical features properly
  - Document feature construction and justification
- **Data Augmentation**:
  - Apply domain-appropriate augmentation (image rotations, text paraphrasing, etc.)
  - Document augmentation strategies and hyperparameters
  - Verify augmentation doesn't introduce artifacts
  - Analyze impact on model performance
- **Data Splitting**:
  - Use stratified splits for imbalanced datasets
  - Ensure no test leakage to training data
  - Document split strategy (temporal, random, by subject, etc.)
  - Report dataset statistics per split

### Phase 4: Model Architecture Design
- **Architecture Selection**:
  - Justify architecture choice based on problem and data
  - Study architecture taxonomy from literature
  - Consider trade-offs: accuracy, computational cost, interpretability
  - Document design decisions and alternatives considered
- **Architecture Specification**:
  - Provide complete architecture details (layers, units, activations, regularization)
  - Include architectural diagrams or pseudocode
  - Document any novel architectural components
  - Specify initialization strategies
- **Ablation Studies**:
  - Systematically remove or modify components
  - Quantify contribution of each component
  - Identify redundant or unnecessary elements
  - Establish which components drive performance

### Phase 5: Hyperparameter Optimization
- **Hyperparameter Search Strategy**:
  - Random search as baseline (documents search cost)
  - Bayesian optimization or grid search for efficiency
  - Document search space and bounds
  - Use proper validation set (not test set) for selection
- **Hyperparameter Documentation**:
  - Report final hyperparameters with justification
  - Document sensitivity to key parameters
  - Show performance curves across parameter values
  - Note if hyperparameters are data/problem dependent
- **Training Procedure**:
  - Specify optimizer (SGD, Adam, etc.) and learning rate schedule
  - Document batch size, number of epochs, early stopping criteria
  - Report training time and computational requirements
  - Include training curves (loss, metrics vs. iteration)

### Phase 6: Evaluation & Validation
- **Evaluation Methodology**:
  - Use appropriate metrics for problem type
  - Implement train/validation/test split correctly
  - Report multiple metrics, not just one
  - Calculate confidence intervals over multiple runs
  - Perform statistical significance testing
- **Multiple Runs & Statistical Analysis**:
  - Report mean and standard deviation over runs
  - Use fixed random seeds for reproducibility
  - Calculate 95% confidence intervals
  - Use appropriate statistical tests (t-test, Mann-Whitney, etc.)
  - Report effect sizes alongside p-values
- **Error Analysis**:
  - Examine examples where model performs poorly
  - Categorize error types (systematic vs. random)
  - Identify patterns in mispredictions
  - Analyze performance across data subgroups
  - Visualize decision boundaries or attention patterns
- **Cross-Validation** (when appropriate):
  - Use k-fold cross-validation for smaller datasets
  - Document fold strategy
  - Report per-fold results and variance
  - Use stratified folds for imbalanced data

### Phase 7: Robustness & Generalization Testing
- **Out-of-Distribution Testing**:
  - Create or collect OOD test set from different source
  - Evaluate performance degradation
  - Identify distribution shift types
  - Analyze which model components are sensitive
- **Adversarial Robustness**:
  - Generate adversarial examples using standard attacks
  - Test model robustness to perturbations
  - Compare to baseline robustness
  - Evaluate defended models if applicable
- **Fairness & Bias Analysis**:
  - Analyze performance across demographic groups
  - Calculate fairness metrics (demographic parity, equalized odds, etc.)
  - Identify and mitigate sources of bias
  - Document limitations and potential harms
- **Uncertainty Quantification**:
  - Report prediction confidence/uncertainty
  - Evaluate calibration (confidence vs. correctness)
  - Identify when model is uncertain
  - Test reliability of uncertainty estimates

### Phase 8: Comparison to Literature & Baselines
- **Fair Comparison Protocol**:
  - Use same datasets and evaluation metrics as baselines
  - Implement baselines or use published code
  - Ensure comparable training resources and hyperparameter tuning
  - Account for published variances and error bars
- **Statistical Comparison**:
  - Report improvement magnitude (absolute and relative)
  - Test statistical significance of improvements
  - Compare confidence intervals, not just point estimates
  - Discuss when improvements are practically significant
- **Benchmark Leaderboards**:
  - Submit to official benchmarks when available
  - Compare against published leaderboard results
  - Document any dataset-specific adaptations
  - Report reproducibility and timing information

### Phase 9: Scalability & Efficiency Analysis
- **Computational Efficiency**:
  - Report training time and computational cost
  - Analyze memory requirements
  - Profile to identify bottlenecks
  - Discuss trade-offs between accuracy and efficiency
- **Scalability**:
  - Test performance on datasets of different sizes
  - Analyze how performance scales with data
  - Document sample complexity (learning curves)
  - Estimate resources needed for larger problems
- **Inference Efficiency**:
  - Report inference time and memory
  - Analyze latency requirements
  - Consider model compression or distillation
  - Evaluate on-device deployment feasibility

### Phase 10: Documentation & Publication
- **Methods Section**:
  - Dataset description and statistics
  - Data preprocessing and augmentation details
  - Architecture specification and justification
  - Training procedure and hyperparameters
  - Evaluation metrics and methodology
- **Results Section**:
  - Main results comparing to baselines
  - Ablation study results
  - Statistical significance and confidence intervals
  - Visualization of results (plots, examples, attention maps)
- **Discussion Section**:
  - Interpretation of results and insights
  - Comparison to existing literature
  - Limitations and failure cases
  - Broader impact and ethical considerations
  - Future work and open questions
- **Reproducibility**:
  - Release code and pre-trained models
  - Document environment (dependencies, versions)
  - Provide dataset links or instructions
  - Include hyperparameters and random seeds
  - Add supplementary materials as needed

---

## Domain-Specific Methodological Standards

### For Computer Vision
- **Architecture Choices**: CNNs for local features, Vision Transformers for global context
- **Data Augmentation**: Geometric transforms, color jittering, mixup, cutmix
- **Evaluation**: Per-class metrics, confusion matrices, visualization of predictions
- **Standardized Benchmarks**: ImageNet, COCO, Cityscapes, etc.
- **Transfer Learning**: Document pre-training dataset and fine-tuning strategy

### For Natural Language Processing
- **Tokenization & Preprocessing**: Document tokenizer and preprocessing choices
- **Pre-trained Models**: Justify choice (BERT, RoBERTa, GPT, etc.)
- **Fine-tuning Strategy**: Learning rate, number of epochs, early stopping
- **Evaluation Metrics**: Task-specific metrics (F1 for NER, BLEU for MT, etc.)
- **Benchmark Datasets**: SQuAD, GLUE, SuperGLUE, WikiBio, etc.

### For Time Series & Forecasting
- **Stationarity & Differencing**: Test and document preprocessing
- **Temporal Validation**: Use temporal cross-validation, not random splits
- **Seasonality & Trends**: Model or detrend appropriately
- **Evaluation Metrics**: MAE, RMSE, MAPE appropriate to problem
- **Baseline Methods**: Compare to statistical baselines (ARIMA, exponential smoothing)

### For Reinforcement Learning
- **Environment & Rewards**: Clearly specify task and reward function
- **Baseline Algorithms**: Compare to standard algorithms (DQN, PPO, A3C, etc.)
- **Exploration Strategy**: Document exploration-exploitation trade-off
- **Sample Efficiency**: Report sample complexity and learning curves
- **Sim-to-Real**: If applicable, document reality gap and transfer strategy

### For Generative Models
- **Generation Quality**: Evaluate sample quality (FID for images, BLEU for text)
- **Mode Coverage**: Assess diversity and mode coverage
- **Training Stability**: Document any issues with training dynamics
- **Likelihood Evaluation**: For models with tractable likelihood, report likelihood metrics
- **Human Evaluation**: Include human evaluation of sample quality

### For Graph Learning
- **Graph Characteristics**: Document graph properties (size, density, features)
- **Graph Splitting**: Ensure proper train/test splits (transductive vs. inductive)
- **Baseline Algorithms**: Compare to standard graph neural network architectures
- **Scalability**: Test on graphs of varying sizes
- **Application-Specific Metrics**: Use metrics appropriate to node/graph classification/link prediction

---

## Quality Criteria & Standards

### Experimental Quality
- ✅ Proper train/validation/test split with no leakage
- ✅ Multiple runs with mean, std, confidence intervals
- ✅ Fair baseline comparisons with equal hyperparameter tuning
- ✅ Ablation studies isolating contribution of each component
- ✅ Statistical significance testing of improvements
- ✅ Error analysis and failure mode investigation
- ✅ Code and results reproducible with published seeds
- ❌ Single run without variance estimates
- ❌ Test set used for hyperparameter selection
- ❌ Unfair baseline comparisons
- ❌ Cherry-picked results
- ❌ No statistical testing of significance
- ❌ Unexplained design choices

### Rigor & Honesty
- ✅ Clear hypothesis and success criteria stated upfront
- ✅ Negative results and failures documented
- ✅ Limitations clearly acknowledged
- ✅ Overfitting and underfitting analyzed
- ✅ Data quality issues identified and addressed
- ✅ Generalization tested on OOD data
- ✅ Reproducibility materials provided
- ❌ Results presented without context
- ❌ Failures hidden or not mentioned
- ❌ Overclaimed significance or generality
- ❌ Insufficient detail for reproduction
- ❌ Bias and fairness issues ignored

### Completeness
- ✅ Both theoretical analysis and empirical validation
- ✅ Dataset description and statistics
- ✅ Complete architecture specification
- ✅ Full hyperparameter documentation
- ✅ Multiple evaluation metrics
- ✅ Comparison to relevant baselines
- ✅ Visualization of results and predictions
- ❌ Theory without experiments
- ❌ Experiments without theoretical insight
- ❌ Missing implementation details
- ❌ Insufficient baseline comparisons
- ❌ No analysis of why method works

---

## Red Flags & Issues to Address

- ❌ **Data Leakage**: Information from test set used in training
- ❌ **Hyperparameter Tuning on Test Set**: Using test set for model selection
- ❌ **Unfair Comparison**: Baselines with inferior hyperparameter tuning
- ❌ **Single Run**: No variance estimates or confidence intervals
- ❌ **P-hacking**: Multiple comparisons without correction
- ❌ **Cherry-Picked Results**: Reporting best run out of many
- ❌ **Overclaimed Significance**: Statistical significance not tested
- ❌ **Insufficient Baseline**: Weak or missing baselines
- ❌ **Missing Ablations**: No analysis of component contributions
- ❌ **Reproducibility Issues**: Insufficient detail, no code release
- ❌ **Generalization Not Tested**: Performance only on original dataset
- ❌ **Bias/Fairness Ignored**: No analysis of fairness and bias
- ❌ **Unrealistic Assumptions**: Assumes perfect data, infinite compute, etc.

---

## Success Metrics for AI/ML Research

1. **Novelty**: Does work propose genuinely new method or insight?
2. **Performance**: Does method improve over existing approaches? By how much?
3. **Rigor**: Are experiments properly designed and statistically valid?
4. **Reproducibility**: Can results be independently verified?
5. **Generality**: Does method work across diverse datasets and domains?
6. **Efficiency**: What is computational cost relative to performance gain?
7. **Interpretability**: Can we understand why and when method works?
8. **Impact**: Does work enable new applications or advance the field?
9. **Fairness**: Does method exhibit bias? Are there adverse side effects?
10. **Clarity**: Is work clearly presented and easy to understand?