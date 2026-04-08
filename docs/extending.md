# Extending the AI Research Engineer

This guide explains how to customize and extend the AI Research Engineer framework to fit your specific research needs, domain requirements, and infrastructure constraints.

## Understanding the Agent Hierarchy

The system is organized into specific research phases, allowing targeted customization at each stage:

```
Workflow Root (SequentialAgent)
├── Ideation Loop (Idea Generator, Novelty Scorer)
├── Planning Loop (Plan Maker, Plan Reviewer)
├── Plan Parser
├── Stage Orchestrator
│   └── For each stage:
│       ├── Implementation Loop (Coding Agent, Review Agent)
│       ├── Criteria Checker
│       └── Stage Reflector
└── Summary Agent (Academic Manuscript Writer)
```

Each agent is independently configurable, allowing you to specialize the system for your domain while maintaining the overall research pipeline integrity.

## Custom Prompts

Prompts are stored in `src/ai_research_engineer/prompts/`. To change the flavor of research, modify these files.

### Available Prompt Files

- **`idea_generator.md`**: Dictates how the agent brainstorms and explores research directions
- **`plan_maker.md`**: Dictates the strictness of the mathematical blueprints and planning rigor
- **`coding_base.md`**: Houses the core rules for the Coding Agent (e.g., forcing PyTorch, requiring deterministic seeds)
- **`summary.md`**: Instructs the agent on how to format the final LaTeX/Markdown paper

### Understanding Prompt Structure

Each prompt file contains:

```markdown
# [Agent Role Title]

## Core Responsibilities
[What this agent does in the workflow]

## Style Guidelines
[Tone and approach]

## Technical Constraints
[Hard rules and requirements]

## Output Format
[Expected structure of outputs]

## Examples
[Sample inputs/outputs]
```

### Modifying Prompts Safely

1. **Always preserve the workflow hooks**: Each prompt contains markers like `{{previous_stage_output}}` and `{{success_criteria}}`
2. **Test incrementally**: Modify one section at a time and validate against a simple test query
3. **Keep a backup**: Version your custom prompts in git

### Prompt Modification Best Practices

```markdown
# BAD: Removing critical constraints
You are a code generator. Write PyTorch code.

# GOOD: Adding domain-specific constraints while preserving structure
You are a code generator specializing in medical AI. 
Write PyTorch code with the following domain requirements:
- All models must support mixed precision (fp16/fp32)
- Include DICOM image preprocessing pipelines
- Validate against FDA 21 CFR Part 11 compliance where applicable
```

## Customizing Specific Agent Prompts

### Example 1: Customize for Quantum ML

Modify `coding_base.md` to ensure the agent uses Pennylane instead of standard PyTorch:

```markdown
$global_preamble

You are a Quantum Machine Learning Engineer. 

## Framework Requirements
- Always use `pennylane` and `qiskit` for your implementations
- Ensure all quantum circuits are tracked for gate depth and execution time
- Implement classical-quantum hybrid architectures using `pytorch` + `pennylane`

## Validation Rules
- Verify quantum circuit depth does not exceed target hardware limits
- Include noise simulation for realistic gate fidelity
- Profile shot count requirements for statistical significance

[... rest of customized prompt ...]
```

### Example 2: Customize for Reinforcement Learning

Modify `plan_maker.md` to enforce RL-specific methodology:

```markdown
$global_preamble

You are an RL Research Methodologist specializing in policy gradient methods.

## Planning Requirements
- Define state/action/reward spaces formally
- Specify exploration-exploitation trade-offs
- Include curriculum learning stages if appropriate
- Plan for off-policy vs on-policy comparisons
- Define sample efficiency metrics alongside reward curves

## Success Criteria Template
For RL experiments, success criteria MUST include:
- Final average reward (with confidence intervals)
- Sample efficiency (samples to convergence)
- Generalization across 5+ random seeds
- Wall-clock training time on reference hardware

[... rest of customized prompt ...]
```

### Example 3: Customize for Biomedical Research

Modify `idea_generator.md` to ensure ethical and practical considerations:

```markdown
$global_preamble

You are a Biomedical AI Research Specialist.

## Novelty Assessment
- Query PubMed and bioRxiv in addition to general ML venues
- Cross-validate against clinical trial registries (clinicaltrials.gov)
- Assess reproducibility and data availability of cited works

## Ethical Constraints
- Flag ideas requiring IRB approval
- Identify data privacy and HIPAA implications
- Document informed consent requirements
- Consider fairness across demographic groups

## Biological Validity
- Ensure proposed mechanisms align with known biology
- Validate against established medical knowledge
- Plan for clinical validation stages

[... rest of customized prompt ...]
```

## Custom Tools

Tools provide specialized functionality to agents. You can inject new scientific databases, internal compute clusters, domain-specific APIs, or proprietary datasets into the agents' toolbelts.

### Understanding the Tool System

Tools are Python functions that agents can call. Each tool:
- Takes standardized input parameters
- Returns results in a format agents understand
- Includes error handling and rate limiting
- Is decorated with `@tool` to register with the agent framework

### Tool Signature Template

```python
from functools import partial
from typing import Optional, List, Dict, Any

def my_custom_tool(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    max_results: int = 10
) -> Dict[str, Any]:
    """
    Tool description for the agent.
    
    Args:
        query: The search or operation query
        filters: Optional filtering parameters
        max_results: Maximum number of results to return
    
    Returns:
        Dictionary with results and metadata
    """
    # Implementation here
    return {
        "results": [...],
        "count": len(...),
        "metadata": {...}
    }
```

### Adding Custom Tools to Agents

Custom tools are injected into the agent creation flow. Modify `src/ai_research_engineer/agents/adk/agent.py`:

```python
from functools import partial
from my_custom_cluster import trigger_slurm_job
from my_lab_tools import query_internal_dataset

def create_agent(working_dir: str):
    """
    Create ADK agent with custom tools injected.
    """
    
    tools = [
        # Base File Tools
        read_file_bound,
        write_file_bound,
        
        # Existing ArXiv & Academic Tools
        search_papers_bound,
        semantic_search_papers_bound,
        
        # YOUR CUSTOM TOOLS
        partial(trigger_slurm_job, cluster_name="gpu_cluster_1"),
        partial(query_internal_dataset, api_key=os.getenv("INTERNAL_API_KEY")),
    ]
    
    # Create agent with tools
    agent = SequentialAgent(
        tools=tools,
        working_dir=working_dir,
        config=config
    )
    
    return agent
```

### Example Custom Tools

#### Example 1: Internal Dataset Query Tool

```python
def query_internal_dataset(
    dataset_name: str,
    query: str,
    api_key: str
) -> Dict[str, Any]:
    """
    Query internal proprietary datasets.
    Available datasets: ["genomics_db", "clinical_records", "sensor_data"]
    """
    import requests
    
    response = requests.post(
        "https://internal-api.company.com/query",
        json={"dataset": dataset_name, "query": query},
        headers={"Authorization": f"Bearer {api_key}"}
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": response.text, "status": response.status_code}
```

#### Example 2: GPU Cluster Submission Tool

```python
def trigger_slurm_job(
    script_path: str,
    cluster_name: str = "default",
    job_name: str = None,
    timeout_hours: int = 24
) -> Dict[str, Any]:
    """
    Submit training jobs to SLURM cluster for large-scale experiments.
    """
    import subprocess
    
    sbatch_cmd = f"""
    sbatch --job-name={job_name or 'ai-research'} \
           --time={timeout_hours}:00:00 \
           --gpus-per-node=4 \
           --mem=64G \
           {script_path}
    """
    
    result = subprocess.run(
        sbatch_cmd,
        shell=True,
        capture_output=True,
        text=True
    )
    
    # Parse SLURM job ID from output
    job_id = result.stdout.split()[-1] if result.returncode == 0 else None
    
    return {
        "job_id": job_id,
        "status": "submitted" if job_id else "failed",
        "cluster": cluster_name,
        "error": result.stderr if result.returncode != 0 else None
    }
```

#### Example 3: Custom Literature Database Tool

```python
def query_domain_bibliography(
    query: str,
    domain: str,
    min_year: int = 2020
) -> Dict[str, Any]:
    """
    Query domain-specific bibliographic database.
    Domains: ["biology", "chemistry", "neuroscience", "materials_science"]
    """
    import requests
    
    # Connect to internal literature database
    response = requests.get(
        "https://literature.company.com/search",
        params={
            "q": query,
            "domain": domain,
            "min_year": min_year,
            "format": "bibtex"
        }
    )
    
    papers = response.json()
    
    return {
        "papers": papers["results"],
        "total_count": papers["total"],
        "domain": domain,
        "bibtex": papers.get("bibtex", "")
    }
```

### Tool Integration Checklist

When adding custom tools:

- ✅ **Error Handling**: Wrap external API calls in try-catch
- ✅ **Rate Limiting**: Implement backoff for rate-limited APIs
- ✅ **Logging**: Use the session logger for debugging
- ✅ **Validation**: Validate input parameters before processing
- ✅ **Return Format**: Ensure consistent dictionary structure
- ✅ **Documentation**: Include clear docstrings for agent understanding
- ✅ **Testing**: Test tools with mock queries before deploying

## Environment Configuration

### Required Variables

- **`OPENROUTER_API_KEY`**: Powers the ADK orchestration agents (Idea Generator, Plan Maker, Novelty Scorer, etc.)
- **`ANTHROPIC_API_KEY`**: Powers the Claude Code implementer for writing and validating code
- **`SEMANTIC_SCHOLAR_API_KEY`**: (Highly Recommended) Prevents rate-limit 429 errors during deep literature reviews

### Optional Variables for Extensions

```bash
# Internal APIs
INTERNAL_API_KEY="your_internal_api_key"
INTERNAL_API_BASE="https://api.company.com"

# Domain-Specific Services
BIOMEDICAL_DB_KEY="clinicaltrials_api_key"
QUANTUM_SIMULATOR_API="qiskit_ibm_api_key"

# Compute Infrastructure
SLURM_CLUSTER_HOST="gpu-cluster.company.com"
SLURM_CLUSTER_USER="research_user"

# Custom Model Configuration
CUSTOM_DEFAULT_MODEL="openrouter/your-custom-model"
CUSTOM_CODING_MODEL="openrouter/your-coding-optimized-model"

# Feature Flags
ENABLE_ADAPTIVE_REPLANNING="true"
ENABLE_EVENT_COMPRESSION="true"
MAX_CONTEXT_EVENTS="40"
```

### Loading Custom Environment

Create a `.env.local` file for development:

```bash
# Source before running experiments
source .env.local
uv run ai-research-engineer "Your query" --mode orchestrated
```

## Advanced Customization Patterns

### Pattern 1: Domain-Specific Agent Pipeline

For specialized research domains, create a custom workflow that inserts domain-specific validation:

```python
# src/ai_research_engineer/custom_workflows/biomedical_pipeline.py

from ai_research_engineer.agents import SequentialAgent

class BiomedicalResearchPipeline(SequentialAgent):
    """
    Specialized pipeline for biomedical AI research with 
    ethical review and clinical validation stages.
    """
    
    def __init__(self, working_dir: str):
        stages = [
            "ideation",           # Novel idea generation
            "ethics_review",      # NEW: Ethics/IRB check
            "planning",           # Methodology design
            "clinical_validation",# NEW: Clinical data consideration
            "execution",          # Code implementation
            "regulatory_check",   # NEW: FDA/regulatory compliance
            "synthesis"           # Academic manuscript
        ]
        
        super().__init__(stages=stages, working_dir=working_dir)
```

### Pattern 2: Multi-Model Ensemble

Use multiple language models for different phases:

```python
# config/multi_model_config.py

class MultiModelConfig:
    """
    Route different agents through different models based on task complexity.
    """
    
    IDEATION_MODEL = "openrouter/claude-opus-4-1"      # Complex reasoning
    PLANNING_MODEL = "openrouter/claude-sonnet-4"      # Balanced
    CODING_MODEL = "openrouter/claude-sonnet-4"        # Code generation
    REVIEW_MODEL = "openrouter/claude-haiku-3"         # Fast validation
    SUMMARY_MODEL = "openrouter/claude-opus-4-1"       # High-quality writing
```

### Pattern 3: Hybrid Human-AI Workflow

Add checkpoints for human review:

```python
# src/ai_research_engineer/custom_workflows/human_in_loop.py

def run_with_human_checkpoints(query: str, working_dir: str):
    """
    Execute workflow with human approval checkpoints.
    """
    
    # Phase 1: Automated Ideation
    ideation_result = run_ideation_phase(query)
    
    # CHECKPOINT 1: Approve research hypothesis
    print("Proposed Research Direction:")
    print(ideation_result["hypothesis"])
    approved = input("Approve this direction? (y/n): ")
    
    if approved.lower() != 'y':
        return {"status": "rejected_at_ideation"}
    
    # Phase 2: Automated Planning
    plan = run_planning_phase(ideation_result)
    
    # CHECKPOINT 2: Review experimental design
    print("Proposed Experimental Plan:")
    print(plan["methodology"])
    approved = input("Approve this plan? (y/n): ")
    
    if approved.lower() != 'y':
        return {"status": "rejected_at_planning"}
    
    # Phase 3-4: Automated Execution & Synthesis
    results = run_execution_phase(plan)
    manuscript = run_synthesis_phase(results)
    
    return {"status": "completed", "manuscript": manuscript}
```

## Validation & Testing

When extending the framework:

### Test Custom Prompts

```bash
# Test a modified prompt with a simple query
uv run ai-research-engineer \
  "Test query for validation" \
  --mode orchestrated \
  --working-dir ./test_extension \
  --verbose
```

### Test Custom Tools

```python
# test_custom_tool.py
from my_custom_tools import query_internal_dataset

def test_tool():
    result = query_internal_dataset(
        dataset_name="genomics_db",
        query="CRISPR applications"
    )
    
    assert "papers" in result
    assert result["total_count"] > 0
    assert result["domain"] == "biology"
    
    print("✓ Tool test passed")

if __name__ == "__main__":
    test_tool()
```

### Integration Testing

```bash
# Run a full workflow with extensions
uv run ai-research-engineer \
  "Your domain-specific research question" \
  --mode orchestrated \
  --verbose
```

## Deployment & Versioning

### Versioning Custom Extensions

```bash
# Track custom extensions in git
git checkout -b feature/quantum-ml-extension
# Make your changes
git commit -am "Add quantum ML support"
git push origin feature/quantum-ml-extension
```

### Environment-Specific Deployments

```bash
# Development
export ENVIRONMENT=dev
source .env.dev
uv run ai-research-engineer "query" --mode orchestrated

# Production
export ENVIRONMENT=prod
source .env.prod
uv run ai-research-engineer "query" --mode orchestrated
```

## Support for Custom Extensions

- **Documentation**: Keep comments explaining non-obvious customizations
- **Error Messages**: Include context when tools fail
- **Logging**: Use structured logging for debugging extensions
- **Fallbacks**: Provide graceful degradation if custom tools are unavailable

## Next Steps

1. **Modify a prompt** for your domain (start with `coding_base.md`)
2. **Create a custom tool** for your primary use case
3. **Test extensively** with simple queries before complex research
4. **Document your extensions** for team reuse
5. **Share improvements** back to the community

Happy customizing! 🔧