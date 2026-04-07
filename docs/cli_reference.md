# CLI Reference

Complete command-line interface reference for Agentic Data Scientist.

## Basic Usage

```bash
ai-research-engineer [OPTIONS] QUERY
```

The CLI provides a simple interface to run data science analyses using either the full multi-agent workflow or direct coding mode.

## Required Options

### `--mode` (REQUIRED)

You must specify an execution mode for every query. This ensures you're aware of the complexity and API costs.

**Choices:**
- `orchestrated`: Full multi-agent workflow with planning, validation, and adaptive execution (recommended for complex analyses)
- `simple`: Direct coding mode without planning overhead (for quick scripts and simple tasks)

**Examples:**
```bash
# Complex analysis with full workflow
ai-research-engineer "Perform differential expression analysis" --mode orchestrated --files data.csv

# Quick scripting task
ai-research-engineer "Write a Python function to parse JSON" --mode simple
```

## Optional Options

### `--files, -f`

Upload files or directories to include in the analysis. Can be specified multiple times for multiple files.

**Behavior:**
- Files are uploaded to the working directory
- Directories are uploaded recursively
- All uploaded files are accessible to agents

**Examples:**
```bash
# Single file
ai-research-engineer "Analyze this data" --mode orchestrated --files data.csv

# Multiple files
ai-research-engineer "Compare datasets" --mode orchestrated -f data1.csv -f data2.csv

# Directory upload (recursive)
ai-research-engineer "Analyze all files" --mode orchestrated --files ./data_folder/
```

### `--working-dir, -w`

Specify a custom working directory for the session.

**Default:** `./agentic_output/` in your current directory

**Behavior:**
- Files are saved to this location
- Directory is preserved after completion (unless `--temp-dir` is used)
- Created if it doesn't exist

**Examples:**
```bash
# Custom directory
ai-research-engineer "Analyze data" --mode orchestrated --files data.csv --working-dir ./my_analysis

# Absolute path
ai-research-engineer "Process data" --mode orchestrated --files data.csv -w /tmp/analysis_2024
```

### `--temp-dir`

Use a temporary directory in `/tmp` with automatic cleanup after completion.

**Behavior:**
- Creates a unique temporary directory
- Automatically deleted after the session completes
- Overrides `--working-dir` if both are specified
- Useful for quick analyses where you don't need to keep files

**Examples:**
```bash
# Temporary analysis
ai-research-engineer "Quick exploration" --mode simple --files data.csv --temp-dir

# Question answering (no files to keep)
ai-research-engineer "Explain gradient boosting" --mode simple --temp-dir
```

### `--keep-files`

Explicitly preserve the working directory after completion.

**Default:** Files are preserved by default when using `--working-dir` or default directory

**Note:** This flag has no effect when using `--temp-dir` (temp directories are always cleaned up)

**Examples:**
```bash
# Explicitly keep files
ai-research-engineer "Generate report" --mode orchestrated --files data.csv --keep-files
```

### `--log-file`

Specify a custom path for the log file.

**Default:** `.agentic_ds.log` in the working directory

**Examples:**
```bash
# Custom log location
ai-research-engineer "Analyze data" --mode orchestrated --files data.csv --log-file ./analysis.log

# Absolute path
ai-research-engineer "Process data" --mode simple --log-file /var/log/agentic_analysis.log
```

### `--verbose, -v`

Enable verbose logging for debugging.

**Behavior:**
- Shows detailed execution logs
- Displays internal agent communication
- Useful for troubleshooting

**Examples:**
```bash
# Verbose output
ai-research-engineer "Debug issue" --mode simple --files data.csv --verbose

# Combined with other options
ai-research-engineer "Complex analysis" --mode orchestrated --files data.csv --verbose --log-file debug.log
```

## Working Directory Behavior

Understanding how working directories work is important for managing your analysis files.

### Default Behavior

When you don't specify any directory options:
- Creates `./agentic_output/` in your current directory
- Preserves all files after completion
- Agents can read and write files here

```bash
ai-research-engineer "Analyze data" --mode orchestrated --files data.csv
# Files saved to: ./agentic_output/
# Preserved: Yes
```

### Temporary Directory

When you use `--temp-dir`:
- Creates a unique directory in `/tmp`
- Automatically deleted after completion
- Use for quick analyses where you don't need files

```bash
ai-research-engineer "Quick test" --mode simple --files data.csv --temp-dir
# Files saved to: /tmp/agentic_ds_XXXXXX/
# Preserved: No (auto-cleanup)
```

### Custom Directory

When you specify `--working-dir`:
- Uses your specified directory
- Preserves files after completion
- Directory is created if it doesn't exist

```bash
ai-research-engineer "Project analysis" --mode orchestrated --files data.csv --working-dir ./my_project
# Files saved to: ./my_project/
# Preserved: Yes
```

## Execution Modes

### Orchestrated Mode (Recommended)

Full multi-agent workflow with planning, validation, and adaptive execution.

**When to Use:**
- Complex data analyses
- Multi-step workflows
- Tasks requiring validation and quality assurance
- Situations where planning improves outcomes
- Tasks where requirements might evolve during execution

**What Happens:**
1. Plan Maker creates a comprehensive plan
2. Plan Reviewer validates the plan
3. For each stage:
   - Coding Agent implements the stage
   - Review Agent validates implementation
   - Criteria Checker tracks progress
   - Stage Reflector adapts remaining work
4. Summary Agent creates final report

**Examples:**
```bash
# Differential expression analysis
ai-research-engineer "Perform DEG analysis comparing treatment vs control" \
  --mode orchestrated \
  --files treatment_data.csv \
  --files control_data.csv

# Complete analysis pipeline
ai-research-engineer "Analyze customer churn, create predictive model, and generate report" \
  --mode orchestrated \
  --files customers.csv \
  --working-dir ./churn_analysis

# Multi-file processing
ai-research-engineer "Analyze all CSV files and create summary statistics" \
  --mode orchestrated \
  --files ./raw_data/
```

### Simple Mode

Direct coding without planning or validation overhead.

**When to Use:**
- Quick scripting tasks
- Simple code generation
- Question answering
- Rapid prototyping
- Tasks where planning overhead isn't needed

**What Happens:**
- Direct execution by Claude Code agent
- No planning phase
- No review or validation loops
- Faster but no quality assurance

**Examples:**
```bash
# Generate utility scripts
ai-research-engineer "Write a Python script to merge CSV files by common column" \
  --mode simple

# Technical questions
ai-research-engineer "Explain the difference between Random Forest and Gradient Boosting" \
  --mode simple

# Quick analysis
ai-research-engineer "Create a basic scatter plot from this data" \
  --mode simple \
  --files data.csv \
  --temp-dir
```

## Common Patterns

### Multiple File Analysis

```bash
# Compare multiple datasets
ai-research-engineer "Compare these datasets and identify trends" \
  --mode orchestrated \
  -f dataset1.csv \
  -f dataset2.csv \
  -f dataset3.csv
```

### Directory Processing

```bash
# Process entire directory
ai-research-engineer "Analyze all JSON files and create consolidated report" \
  --mode orchestrated \
  --files ./data_directory/
```

### Temporary Analysis

```bash
# Quick exploration without keeping files
ai-research-engineer "Explore data distributions" \
  --mode simple \
  --files data.csv \
  --temp-dir
```

### Project-Based Analysis

```bash
# Organized project structure
ai-research-engineer "Complete statistical analysis with visualizations" \
  --mode orchestrated \
  --files raw_data.csv \
  --working-dir ./projects/analysis_2024 \
  --log-file ./projects/analysis_2024.log
```

### Debugging and Development

```bash
# Verbose output for troubleshooting
ai-research-engineer "Debug data processing issue" \
  --mode simple \
  --files problematic_data.csv \
  --verbose \
  --log-file debug.log
```

## Input Methods

### Command-Line Argument

Most common method - provide query as a command-line argument:

```bash
ai-research-engineer "Your query here" --mode orchestrated
```

### Stdin Pipe

Pipe input from another command or file:

```bash
# From echo
echo "Analyze this dataset" | ai-research-engineer --mode simple --files data.csv

# From file
cat query.txt | ai-research-engineer --mode orchestrated --files data.csv
```

## Exit Codes

- `0`: Success
- `1`: Error (invalid arguments, runtime error, etc.)

## Environment Variables

The CLI respects these environment variables (set in `.env` file or shell):

**Required:**
- `OPENROUTER_API_KEY`: OpenRouter API key for planning/review agents
- `ANTHROPIC_API_KEY`: Anthropic API key for coding agent

**Optional:**
- `DEFAULT_MODEL`: Model for planning/review (default: `google/gemini-2.5-pro`)
- `CODING_MODEL`: Model for coding agent (default: `claude-sonnet-4-5-20250929`)

## Output and Logging

### Console Output

The CLI displays:
- Agent activities and progress
- Key decisions and milestones
- File creation notifications
- Completion summary

### Log Files

Detailed logs are written to:
- Default: `.agentic_ds.log` in working directory
- Custom: Path specified by `--log-file`

Logs include:
- Full agent conversations
- Tool calls and responses
- Error messages and stack traces
- Token usage statistics

## Troubleshooting

### "Error: No query provided"

You didn't provide a query. Either:
- Provide query as argument: `ai-research-engineer "query" --mode orchestrated`
- Pipe from stdin: `echo "query" | ai-research-engineer --mode orchestrated`

### "Error: Missing option '--mode'"

The `--mode` flag is required. Specify either:
- `--mode orchestrated` for full multi-agent workflow
- `--mode simple` for direct coding

### "File not found" Errors

Check that:
- File paths are correct and files exist
- You have read permissions
- File paths don't contain special characters that need escaping

### "API Key Not Found" Errors

Ensure you have:
- `OPENROUTER_API_KEY` set in environment or `.env` file
- `ANTHROPIC_API_KEY` set in environment or `.env` file
- API keys are valid and have sufficient credits

### Working Directory Permission Errors

Ensure you have:
- Write permissions to the working directory
- Sufficient disk space
- Parent directories exist (or can be created)

### Out of Memory Errors

For large analyses:
- Use `--temp-dir` to ensure cleanup
- Process files in smaller batches
- Use simple mode for less memory overhead

## Best Practices

1. **Use Orchestrated Mode for Important Work**
   - Planning catches issues early
   - Validation ensures quality
   - Worth the extra API cost for production analyses

2. **Use Simple Mode for Quick Tasks**
   - Fast iteration during development
   - Question answering
   - Simple script generation

3. **Organize Your Work**
   - Use `--working-dir` for project organization
   - Use `--temp-dir` for temporary explorations
   - Keep related analyses in dedicated directories

4. **Enable Verbose Logging When Needed**
   - Use `--verbose` when debugging
   - Specify `--log-file` for persistent logs
   - Review logs to understand agent behavior

5. **Manage File Lifecycle**
   - Use `--temp-dir` for throwaway analyses
   - Use custom `--working-dir` for important work
   - Clean up old working directories periodically

## Examples by Use Case

### Data Science Workflow

```bash
# Initial exploration (temporary)
ai-research-engineer "Explore data distributions and missing values" \
  --mode simple --files data.csv --temp-dir

# Full analysis (preserved)
ai-research-engineer "Perform complete statistical analysis with visualizations" \
  --mode orchestrated --files data.csv --working-dir ./analysis_results

# Model building
ai-research-engineer "Build and evaluate multiple regression models" \
  --mode orchestrated --files train.csv --files test.csv \
  --working-dir ./models
```

### Bioinformatics

```bash
# Differential expression
ai-research-engineer "Perform DESeq2 differential expression analysis" \
  --mode orchestrated \
  --files counts.csv --files metadata.csv \
  --working-dir ./deg_analysis

# Pathway analysis
ai-research-engineer "Run GSEA pathway enrichment on DEGs" \
  --mode orchestrated --files deg_results.csv \
  --working-dir ./pathway_analysis
```

### Scripting and Automation

```bash
# Generate utility script
ai-research-engineer "Write Python script to merge CSV files" \
  --mode simple --working-dir ./scripts

# Batch processing script
ai-research-engineer "Create script to process multiple data files" \
  --mode simple --files sample_data.csv --working-dir ./scripts
```

### Learning and Exploration

```bash
# Technical questions
ai-research-engineer "Explain PCA and when to use it" --mode simple --temp-dir

# Code examples
ai-research-engineer "Show me how to use pandas groupby with multiple aggregations" \
  --mode simple --temp-dir
```

