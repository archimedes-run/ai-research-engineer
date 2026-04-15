<!-- Scientific Methodology Prompt for Finance -->
<!-- Domain-specific prompt for quantitative finance research methodology -->

# Quantitative Finance Research Methodology Guidelines

## Research Workflow Standards

### Phase 1: Literature Review & Theoretical Foundation
- **Academic Sources**: 
  - Journals: Journal of Finance, Review of Financial Studies, Journal of Financial Economics, Quantitative Finance
  - Repositories: SSRN, arXiv (q-fin section), papers.ssrn.com
  - Books: Standard references in derivatives, fixed income, equities, risk management
- **Theory Building**: Extract key models, assumptions, and empirical findings
- **Gap Identification**: Identify unstudied market regimes, time periods, or asset classes
- **Novelty Assessment**: Ensure work addresses gaps or challenges existing literature

### Phase 2: Hypothesis Formulation
- **Market Inefficiency Hypothesis**: Propose specific market anomaly with testable predictions
- **Factor Hypothesis**: Propose new risk factor or strategy with expected premium
- **Structural Hypothesis**: Propose mechanism (e.g., fire sales, limits-to-arbitrage) explaining observations
- **Quantitative Specification**: Express hypothesis as testable statistical models with measurable parameters

### Phase 3: Data Collection & Preprocessing
- **Data Sources**:
  - Equity data: Bloomberg, Reuters, Yahoo Finance, CRSP, Compustat
  - Fixed income: Bloomberg, TradeWeb, TRACE, FINRA
  - Derivatives: OptionMetrics, Ivy DB, exchanges, Bloomberg
  - Macro: Federal Reserve Economic Data (FRED), OECD, World Bank
  - Alternative: Blockchain APIs, alternative data providers
- **Data Quality Checks**:
  - Survivorship bias: Include delisted securities, failed companies
  - Look-ahead bias: Ensure timing of data matches actual availability
  - Selection bias: Verify sampling methodology and representativeness
  - Missing data: Document gaps and handle appropriately
- **Preprocessing**: 
  - Handle corporate actions (splits, dividends, mergers)
  - Clean outliers with economically justified thresholds
  - Align different data frequencies
  - Create appropriate market regimes/time periods

### Phase 4: Statistical Analysis & Hypothesis Testing
- **Exploratory Analysis**:
  - Descriptive statistics (mean, volatility, skewness, kurtosis)
  - Time series properties (stationarity, autocorrelation, seasonality)
  - Cross-sectional relationships and correlations
  - Distributional analysis and tail characterization
- **Formal Hypothesis Testing**:
  - Specify null and alternative hypotheses precisely
  - Choose appropriate test statistics (t-tests, F-tests, χ² tests, etc.)
  - Correct for multiple comparisons (Bonferroni, FDR control)
  - Account for non-standard distributions (fat tails, jumps)
- **Regression Analysis**:
  - Specify models with economic motivation
  - Check assumptions (linearity, homoscedasticity, independence)
  - Use robust standard errors (Newey-West for autocorrelation, HC for heteroscedasticity)
  - Perform specification tests and model diagnostics
- **Causality Analysis**:
  - Use appropriate techniques (Granger causality, instrumental variables, natural experiments)
  - Verify timing and mechanism consistency
  - Document limitations of causal inference

### Phase 5: Strategy Development & Backtesting
- **Strategy Specification**:
  - Define entry and exit rules with objective criteria
  - Specify portfolio construction methodology (equal-weight, optimal, rule-based)
  - Detail rebalancing frequency and schedule
  - Document all decisions and parameters
- **Backtesting Framework**:
  - Use realistic market assumptions:
    - Transaction costs (bid-ask spreads, commissions, market impact)
    - Execution assumptions (market orders, time-weighted average price)
    - Borrowing costs for short positions
    - Dividend/coupon reinvestment
  - Account for liquidity constraints (volume, bid-ask spreads, market depth)
  - Include realistic slippage assumptions
- **Performance Evaluation**:
  - Calculate raw returns and risk-adjusted metrics
  - Benchmark against appropriate indices (SPY for equities, AGG for bonds, etc.)
  - Compute information ratio and factor-adjusted returns
  - Analyze performance drivers (allocation, selection, timing)

### Phase 6: Robustness & Out-of-Sample Testing
- **Walk-Forward Analysis**: 
  - Divide data into in-sample training and out-of-sample testing periods
  - Re-estimate parameters periodically and measure out-of-sample performance
  - Test for structural breaks and parameter stability
- **Sensitivity Analysis**:
  - Vary key parameters (thresholds, lookback periods, rebalancing frequency)
  - Test performance across market regimes and volatility regimes
  - Evaluate impact of transaction cost assumptions
  - Test on different asset classes or time periods
- **Stress Testing**:
  - Simulate historical crises (2008, 2020, etc.)
  - Use synthetic extreme scenarios
  - Analyze maximum drawdowns and recovery times
  - Test correlation and leverage assumptions
- **Statistical Significance**:
  - Calculate t-statistics for returns and information ratios
  - Perform Monte Carlo simulations to test if results exceed chance
  - Use permutation tests for robustness
  - Correct for multiple strategy testing

### Phase 7: Risk & Scenario Analysis
- **Standard Risk Metrics**:
  - Value-at-Risk (VaR): 95%, 99% confidence levels
  - Expected Shortfall (CVaR): expected loss given tail events
  - Volatility: annualized standard deviation
  - Correlation matrices and covariance structures
- **Advanced Risk Analysis**:
  - Conditional Value-at-Risk for tail behavior
  - Extreme Value Theory for rare events
  - Stress tests for known crisis scenarios
  - Liquidity-adjusted risk metrics
- **Scenario Analysis**:
  - Define adverse market scenarios (rate shocks, volatility spikes, correlation shifts)
  - Calculate strategy performance in each scenario
  - Estimate maximum realistic loss
  - Identify hedging needs

### Phase 8: Documentation & Manuscript Preparation
- **Methodology Section**: 
  - Data sources and sample selection
  - Variable definitions and construction
  - Model specifications and estimation methods
  - Backtesting assumptions and implementation details
- **Results Section**:
  - Summary statistics and correlation tables
  - Main hypothesis test results
  - Strategy performance metrics
  - Robustness and sensitivity analysis results
- **Discussion Section**:
  - Economic interpretation of findings
  - Comparison with existing literature
  - Discussion of limitations and potential biases
  - Implications for practitioners and researchers

---

## Domain-Specific Methodological Standards

### For Equity Market Research
- **Return Predictability**: Test for autocorrelation, seasonality, and anomalies
- **Factor Analysis**: Quantify exposures to size, value, momentum, quality, low volatility
- **Liquidity Effects**: Estimate bid-ask spread impact and price impact models
- **Earnings Announcements**: Analyze abnormal returns and volatility around events
- **Market Microstructure**: Study order flow, depth, and trading dynamics

### For Fixed Income Research
- **Term Structure**: Analyze yield curve shape, shifts, and predictive power
- **Credit Analysis**: Model default probabilities and spread changes
- **Duration Management**: Calculate effective duration and convexity
- **Macro Sensitivity**: Estimate sensitivities to inflation, growth, policy rates
- **Liquidity Premiums**: Quantify compensation for illiquidity

### For Derivatives & Options
- **Volatility Modeling**: Compare GARCH, stochastic volatility, and jump-diffusion models
- **Pricing Accuracy**: Test option pricing models against market prices
- **Greeks Stability**: Verify delta, gamma, vega estimates and hedging effectiveness
- **Smile/Skew Analysis**: Model implied volatility surface dynamics
- **Hedging Effectiveness**: Measure risk reduction from delta/gamma hedging strategies

### For Cryptocurrency & Blockchain
- **Market Efficiency**: Test for anomalies, predictability, and arbitrage opportunities
- **Correlation Dynamics**: Analyze time-varying correlations with traditional assets
- **Volatility Characterization**: Document extremes, clustering, and regime changes
- **Blockchain Data**: Analyze on-chain metrics (addresses, volume, holder concentration)
- **Regulatory Impact**: Quantify effects of regulatory announcements and policy changes

### For Macroeconomic Research
- **Economic Indicators**: Identify leading/lagging relationships and causal effects
- **Recession Detection**: Build models predicting probability and timing
- **Policy Analysis**: Quantify effects of monetary and fiscal policy
- **International Factors**: Model currency and commodity relationships
- **Structural Stability**: Test for parameter stability across time periods and regimes

---

## Quality Criteria & Guardrails

### Statistical Quality
- ✅ Use appropriate tests for data type and distribution
- ✅ Report p-values and confidence intervals
- ✅ Correct for multiple comparisons
- ✅ Test assumptions (normality, independence, homoscedasticity)
- ❌ Don't p-hack or data mine without disclosure
- ❌ Don't ignore violations of statistical assumptions
- ❌ Don't ignore multiple comparison issues

### Data Quality
- ✅ Document data sources and sample construction clearly
- ✅ Address survivorship bias, look-ahead bias, selection bias
- ✅ Handle missing data appropriately
- ✅ Verify alignment across different data sources
- ❌ Don't hide data quality issues or sample exclusions
- ❌ Don't ignore potential biases in data
- ❌ Don't use future information in backtest

### Practical Quality
- ✅ Use realistic transaction cost assumptions
- ✅ Account for liquidity constraints
- ✅ Include slippage and market impact
- ✅ Test on out-of-sample data
- ✅ Perform extensive robustness tests
- ❌ Don't ignore transaction costs
- ❌ Don't assume infinite liquidity
- ❌ Don't overfit to historical data

### Research Quality
- ✅ Ground work in established financial theory
- ✅ Compare with existing literature and strategies
- ✅ Acknowledge limitations and potential biases
- ✅ Consider alternative explanations
- ✅ Document all assumptions
- ❌ Don't make overclaimed conclusions without support
- ❌ Don't ignore conflicting evidence
- ❌ Don't dismiss negative results

---

## Red Flags & Issues to Address

- ❌ **Survivorship bias**: Including only companies that survived to present
- ❌ **Look-ahead bias**: Using information unavailable at decision time
- ❌ **Data mining bias**: Testing many strategies without correcting for multiple comparisons
- ❌ **Overfitting**: In-sample fit so good it indicates overfitting to noise
- ❌ **Unrealistic costs**: Ignoring transaction costs, slippage, or execution constraints
- ❌ **Liquidity illusion**: Assuming easy execution in illiquid securities
- ❌ **Correlation assumptions**: Assuming correlations stable during crises
- ❌ **Leverage abuse**: Using excessive leverage without proper risk controls
- ❌ **Concentration risk**: Extreme allocations to few positions
- ❌ **Regime blindness**: Strategy breaks during new market regimes

---

## Success Metrics for Finance Research

1. **Novelty**: Does work identify new market inefficiency or factor not previously documented?
2. **Robustness**: Does finding persist across time periods, asset classes, and market conditions?
3. **Economic Significance**: Is the magnitude of returns large enough to exceed trading costs?
4. **Statistical Significance**: Is the finding statistically significant after correcting for multiple tests?
5. **Replicability**: Can independent researchers verify results with publicly available data?
6. **Practical Implementation**: Can the strategy be implemented realistically with available capital?
7. **Regulatory Compliance**: Does strategy comply with applicable regulations and ethical standards?