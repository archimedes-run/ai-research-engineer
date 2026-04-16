<!-- Scientific Methodology Prompt for Biomedics -->
<!-- Domain-specific prompt for biomedical research methodology and best practices -->

# Biomedical Research Methodology Guidelines

## Research Workflow Standards

### Phase 1: Literature Review & Hypothesis Development
- **Literature Survey**:
  - Search PubMed, Google Scholar, bioRxiv for relevant papers
  - Identify established protocols and methodologies
  - Document known targets, pathways, and therapeutic approaches
  - Note knowledge gaps and unresolved questions
- **Target & Mechanism Selection**:
  - Justify disease/target relevance (prevalence, unmet need)
  - Identify biological pathway or mechanism
  - Document supporting evidence from literature
  - Establish preliminary hypotheses
- **Study Design**:
  - Define experimental design (observational, interventional, mechanistic)
  - Specify primary and secondary outcomes
  - Justify sample sizes and power calculations
  - Plan control groups and comparisons

### Phase 2: Materials & Methods Development
- **Cell Lines & Organisms**:
  - Document source and authentication (ATCC, commercial, primary culture)
  - Provide detailed culture conditions (medium, temperature, passage number)
  - Include contamination testing procedures
- **Reagents & Antibodies**:
  - List complete reagent specifications (manufacturer, catalog number, lot)
  - Document antibody validation (Western blot, immunofluorescence)
  - Include positive and negative controls
  - Provide sequence information for custom reagents
- **Assay Development**:
  - Validate assay sensitivity and specificity
  - Establish standard curves and positive/negative controls
  - Document reproducibility across runs
  - Determine appropriate sample sizes

### Phase 3: Experimental Execution
- **Protocol Implementation**:
  - Follow Standard Operating Procedures (SOPs) consistently
  - Document all deviations from published protocols
  - Record environmental conditions (temperature, humidity, timing)
  - Maintain detailed experimental notebooks
- **Quality Control**:
  - Include positive and negative controls in each experiment
  - Run replicates (minimum n=3 for most studies)
  - Verify assay performance metrics
  - Check for contamination or technical issues
- **Data Collection**:
  - Record raw data and processed data separately
  - Document all analysis parameters and thresholds
  - Keep audit trail of data modifications
  - Establish data management system

### Phase 4: Statistical Analysis
- **Study Design Analysis**:
  - State null and alternative hypotheses clearly
  - Specify primary endpoint before analysis
  - Pre-register study when applicable (ClinicalTrials.gov)
  - Define data exclusion criteria a priori
- **Descriptive Statistics**:
  - Report basic characteristics of sample
  - Describe missing data patterns and handling
  - Present distribution of outcome variables
  - Perform exploratory analysis appropriately
- **Hypothesis Testing**:
  - Choose appropriate statistical tests (parametric vs. non-parametric)
  - Report test assumptions and validity checks
  - Calculate p-values and confidence intervals
  - Correct for multiple comparisons (Bonferroni, FDR)
- **Effect Size & Practical Significance**:
  - Report effect sizes alongside p-values
  - Discuss clinical/biological significance
  - Acknowledge both statistical and practical importance
  - Distinguish between clinical and statistical significance

### Phase 5: Validation & Confirmation
- **Intra-Assay Reproducibility**:
  - Multiple replicates within single experiment
  - Calculate coefficient of variation (CV < 10% for most assays)
  - Verify day-to-day consistency
- **Inter-Assay Reproducibility**:
  - Repeat experiment on different days/weeks
  - Use different reagent lots when available
  - Test across different operators if applicable
- **Independent Replication**:
  - Confirm findings in independent cohort
  - Use different cell line or organism if applicable
  - Validate in complementary experimental system
  - Consider external validation by other groups

### Phase 6: Mechanism Elucidation
- **Pathway Analysis**:
  - Test specific pathway components
  - Document interactions and dependencies
  - Perform loss-of-function studies (siRNA, CRISPR knockout)
  - Perform gain-of-function studies (overexpression, activation)
- **Target Validation**:
  - Demonstrate target engagement (binding, phosphorylation)
  - Show target-related downstream effects
  - Confirm selectivity and off-target effects
  - Establish dose-response relationships
- **Mechanism Confirmation**:
  - Use orthogonal methods to confirm findings
  - Test genetic vs. pharmacological approaches
  - Validate in primary cells or tissue
  - Assess relevance to human biology

### Phase 7: Documentation & Publication
- **Methods Section**:
  - Complete protocol with sufficient detail for replication
  - Materials list with exact specifications
  - Step-by-step procedures
  - Reagent and equipment specifications
- **Results Section**:
  - Present primary data clearly (figures, tables)
  - Include appropriate controls
  - Report statistical analyses with full details
  - Discuss findings in context of hypothesis
- **Discussion Section**:
  - Interpret findings mechanistically
  - Compare to existing literature
  - Acknowledge limitations and potential biases
  - Discuss implications and future directions
- **Data Availability**:
  - Provide raw data when possible
  - Describe data access procedures
  - Consider GEO/ArrayExpress for genomic data
  - Ensure compliance with institutional and regulatory requirements

---

## Domain-Specific Methodological Standards

### For Cell Biology & Biochemistry
- **Cell Culture Quality**: Document passage numbers, test for mycoplasma contamination
- **Protein Analysis**: Include positive/negative controls, proper loading controls
- **Protein Purification**: Demonstrate purity by SDS-PAGE, mass spectrometry
- **Binding Studies**: Use appropriate techniques (ELISA, surface plasmon resonance, ITC)
- **Kinetic Studies**: Measure and report rate constants, Km, Vmax with error estimates

### For Molecular Biology & Genetics
- **Sequence Verification**: Confirm mutations/modifications by Sanger sequencing or deep sequencing
- **Expression Analysis**: Include reference genes, validate qPCR primers
- **Transgenic Models**: Document genotyping strategies, breeding protocols
- **CRISPR/Genome Editing**: Verify guide RNA specificity, off-target effects
- **Copy Number**: Use appropriate techniques to quantify (qPCR, digital PCR, FISH)

### For In Vivo Studies
- **Animal Selection**: Justify species, strain, age, sex
- **Randomization & Blinding**: Describe randomization method and blinding strategy
- **Sample Size**: Provide power calculations
- **Welfare & Ethics**: Describe animal care, pain management, IACUC approval
- **Endpoint Specification**: Define study endpoints and humane stopping criteria

### For Clinical Studies
- **Informed Consent**: Document IRB approval and consent procedure
- **Data Collection**: Standardize data collection forms and procedures
- **Safety Monitoring**: Describe adverse event monitoring and reporting
- **Study Population**: Define inclusion/exclusion criteria clearly
- **Statistical Analysis Plan**: Pre-specify primary and secondary analyses

### For High-Throughput Studies (Genomics, Proteomics, Metabolomics)
- **Quality Control**: Describe QC metrics and outlier detection
- **Normalization**: Justify normalization approach
- **Statistical Validation**: Include false discovery rate calculations
- **Functional Annotation**: Provide biological interpretation of results
- **Data Deposition**: Submit to appropriate public databases (GEO, Proteome Exchange)

---

## Quality Criteria & Standards

### Experimental Quality
- ✅ Multiple replicates (minimum n=3) with technical and biological replicates
- ✅ Appropriate controls (positive, negative, vehicle)
- ✅ Consistent experimental conditions
- ✅ Independent validation by repeat experiment
- ✅ Confirmation in complementary system
- ❌ Single replicate without validation
- ❌ Missing controls
- ❌ Unexplained technical issues
- ❌ No independent confirmation

### Statistical Quality
- ✅ Appropriate statistical tests for data type
- ✅ Assumptions validated (normality, equal variance)
- ✅ Confidence intervals reported alongside p-values
- ✅ Multiple comparison corrections applied
- ✅ Effect sizes reported
- ❌ Only p-values without context
- ❌ Multiple testing without correction
- ❌ Inappropriate statistical methods
- ❌ Data exclusion without justification

### Reproducibility
- ✅ Detailed protocol with sufficient specificity
- ✅ Complete reagent information (catalog numbers, lots)
- ✅ Exact conditions documented (temperature, timing, pH)
- ✅ Data available in accessible form
- ✅ Code released for computational analysis
- ❌ Vague protocol description
- ❌ Missing reagent details
- ❌ Proprietary or unavailable materials
- ❌ Data not accessible to others

---

## Red Flags & Issues to Address

- ❌ **Missing Controls**: No positive or negative controls in experiments
- ❌ **Single Replicate**: Only one run without reproducibility testing
- ❌ **Contamination**: Cell line contamination or mycoplasma not tested
- ❌ **Data Selection Bias**: "Best of X experiments" without reporting failures
- ❌ **Inadequate Sample Size**: No power calculation or unreasonably small n
- ❌ **P-hacking**: Multiple analyses without multiple comparison correction
- ❌ **Unexplained Outliers**: Data points removed without justification
- ❌ **Vague Methods**: Insufficient detail to reproduce procedures
- ❌ **No Mechanism**: Results without understanding how or why
- ❌ **Lack of Validation**: Finding not confirmed by other groups or methods

---

## Success Metrics for Biomedical Research

1. **Novelty**: Is the target, mechanism, or therapeutic approach new?
2. **Rigor**: Are experiments properly designed with appropriate controls?
3. **Reproducibility**: Can results be independently replicated?
4. **Mechanistic Understanding**: Is the biological mechanism understood?
5. **Clinical Relevance**: Do findings translate to human disease?
6. **Impact**: Do results advance the field or enable new therapies?
7. **Quality**: Are results published in reputable peer-reviewed journals?

---

---

# MVPT Translation for Biomedics Domain

This section explains how the universal MVPT novelty framework (from `novelty_scorer.md`) applies specifically to biomedical research.

## M - Method Novelty in Biomedics
**What counts as "new method":**
- ✓ Novel drug discovery target (new gene/protein implicated in disease)
- ✓ New assay/screening technique (e.g., first high-throughput screen for pathway X)
- ✓ Novel therapeutic approach (new mechanism class, e.g., CRISPR-based therapy)
- ✓ New diagnostic marker identifying disease earlier/more accurately
- ✓ Novel mechanistic pathway discovery
- ✗ NOT: Testing known drug on new patient population (M:2)
- ✗ NOT: New dosage of existing therapy (M:2)
- ✗ NOT: Using known target with off-the-shelf antibody (M:2)

**Scoring Guide:**
- M:9-10 = Entirely new therapeutic target or mechanism
- M:7-8 = Novel assay discovering new biology
- M:5-6 = Improved implementation of known approach
- M:3-4 = Same approach with minor modifications
- M:0-2 = Applying established method as-is

---

## V - Verifiability in Biomedics (8-Point Checklist)

**Verification Checklist:**
1. **Full Protocol in Methods?** Step-by-step reproducible procedure → 1 point
2. **Materials Documented?** Cell lines, antibodies, chemicals with catalog numbers → 1 point
3. **Reagent Codes Listed?** Antibody clones, siRNA sequences, plasmids available → 1 point
4. **Statistics Detailed?** n values, test types, p-values, CI reported → 1 point
5. **Raw Data Available?** Figure source data, raw images, spreadsheets provided → 1 point
6. **Multiple Replicates?** ≥3 independent replicates shown → 1 point
7. **Pos/Neg Controls Included?** Positive and negative controls present in figures → 1 point
8. **Independent Validation?** Findings confirmed in independent cohort/cell line → 1 point

**Scoring:**
- 7-8/8 passing = 7.5-8.5 points (fully reproducible)
- 5-6/8 passing = 5.5-6.5 points (mostly reproducible)
- 3-4/8 passing = 3.5-4.5 points (partially reproducible)
- <3/8 passing = 1-3 points (barely reproducible)

**FATAL**: If V < 3, reject immediately (biomedical science requires replicability).

---

## P - Principle Power in Biomedics

**What "explaining why it works" means:**
- ✓ **Mechanistic explanation**: "Drug binds X receptor → activates Y pathway → reduces disease"
- ✓ **Pathway validation**: Loss-of-function (knockout, siRNA) and gain-of-function studies
- ✓ **Cellular mechanism**: Detailed understanding of how intervention produces phenotype
- ✗ NOT: Just "reduces tumor size" or "improves survival" without mechanism
- ✗ NOT: Correlation without proving causation

**Scoring Guide:**
- P:9-10 = Clear mechanism with loss/gain-of-function validation
- P:7-8 = Good mechanistic understanding, partial validation
- P:5-6 = Mechanism partially understood, some supporting evidence
- P:3-4 = Hand-wavy mechanism explanation
- P:0-2 = Black box, just empirical observation

**Example Interpretations:**
- "Drug binds X, activates Y pathway, shown by mutation studies" = P:8
- "CRISPR knockdown of X reduces disease, pathway shown" = P:8
- "Antibody anti-target reduces tumor" (no mechanism) = P:2
- "Compound improves symptoms" (no understanding) = P:1

---

## T - Transfer in Biomedics

**What "generalization" means:**
- ✓ **Multi-organism**: Works in mouse, rat, dog (toward humans)
- ✓ **Multiple disease models**: Target relevant to multiple conditions
- ✓ **Multiple tissues/cell types**: Pathway/target conserved
- ✓ **Conservation**: Mechanism works across species, disease types
- ✗ NOT: Only one cell line tested
- ✗ NOT: Only one disease model tested
- ✗ NOT: Only in mice (not validated toward human relevance)

**Scoring Guide:**
- T:9-10 = Works across multiple organisms, diseases, tissues
- T:7-8 = Works in multiple models or tissues
- T:5-6 = Might generalize with modification
- T:3-4 = Limited to specific model or tissue
- T:0-2 = Only one cell line or condition

**Examples:**
- CRISPR edit works in human, mouse, zebrafish = T:9
- Drug improves cognition in Alzheimer's AND Parkinson's models = T:8
- "Works in HEK293 cells" (only one cell line) = T:1
- Antibody works for cancer A only = T:2
- Pathway conserved from C. elegans to human = T:9

---

## Red Flags Specific to Biomedics

- ❌ **No positive/negative controls**: Experiments lack appropriate controls
- ❌ **Single replicate**: n=1 without reproducibility testing
- ❌ **Cell line authenticity unverified**: Using cell line without mycoplasma test
- ❌ **Vague protocol**: Methods insufficient for reproduction
- ❌ **Data not available**: "Available on request" (should be public)
- ❌ **No independent validation**: Finding only shown in one system
- ❌ **Only in vitro**: No in vivo or clinical relevance shown
- ❌ **Unvalidated antibodies**: Using antibodies without cross-reactivity testing
- ❌ **Statistical violations**: Multiple comparisons without correction
- ❌ **Reproducibility issues**: Others report inability to replicate findings