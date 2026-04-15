#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import re
from datetime import datetime
from pathlib import Path

# Paths
PLANS_FILE = Path("PLANS.md")
TASKS_FILE = Path("TASKS.md")
DIARY_DIR = Path("docs/diary")

# Model selection configuration
MODEL_SELECTION_STRATEGY = os.environ.get("MODEL_SELECTION_STRATEGY", "first_openai")


def run_command(command, shell=True):
    result = subprocess.run(command, shell=shell, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def get_available_models():
    """Fetch available models from GitHub Models API using gh models CLI."""
    try:
        result = subprocess.run(
            ["gh", "models", "list"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"Warning: Failed to fetch models list: {result.stderr}", file=sys.stderr)
            return []
        
        # Parse the output to get model IDs (skip header lines)
        models = []
        lines = result.stdout.strip().split('\n')
        for line in lines:
            # Model IDs are in the format "provider/model-name"
            parts = line.split()
            if parts and '/' in parts[0]:
                models.append(parts[0])
        
        return models
    except subprocess.TimeoutExpired:
        print("Warning: Timeout fetching models list", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Warning: Error fetching models list: {e}", file=sys.stderr)
        return []


def select_model(strategy=None):
    """Select a model based on a strategy to avoid hardcoding model names.
    
    Strategies:
    - "first": Use the first available model
    - "first_openai": Use the first OpenAI model (recommended)
    - "cheapest": Prefer mini/nano models for cost efficiency
    - "most_capable": Prefer the most capable models (gpt-5, gpt-4.1, etc.)
    - "env": Use AGENT_MODEL environment variable
    """
    if strategy is None:
        strategy = MODEL_SELECTION_STRATEGY
    
    # Check environment variable first
    env_model = os.environ.get("AGENT_MODEL")
    if env_model:
        return env_model
    
    # Fetch available models
    models = get_available_models()
    
    if not models:
        # Fallback to a known model if we can't fetch the list
        print("Warning: No models available, using fallback", file=sys.stderr)
        return "openai/gpt-4o-mini"
    
    if strategy == "first":
        return models[0]
    
    elif strategy == "first_openai":
        for m in models:
            if m.startswith("openai/"):
                return m
        # Fallback to first if no OpenAI models
        return models[0]
    
    elif strategy == "cheapest":
        # Prefer mini/nano models for cost efficiency
        cost_keywords = ["mini", "nano", "small"]
        for keyword in cost_keywords:
            for m in models:
                if keyword in m.lower():
                    return m
        # Fallback to first
        return models[0]
    
    elif strategy == "most_capable":
        # Prefer most capable models in order of priority
        priority = ["gpt-5", "gpt-4.1", "gpt-4o", "claude", "grok"]
        for p in priority:
            for m in models:
                if p in m.lower():
                    return m
        # Fallback to first
        return models[0]
    
    else:
        print(f"Warning: Unknown strategy '{strategy}', using first model", file=sys.stderr)
        return models[0]


def call_llm(system_prompt, user_prompt, model=None):
    """Call LLM via GitHub Models API with dynamic model selection."""
    
    # Auto-select model if not provided
    if model is None:
        model = select_model(MODEL_SELECTION_STRATEGY)
    
    print(f"Using model: {model}", file=sys.stderr)
    
    try:
        # Construct the JSON payload
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7
        }
        
        # Write payload to temp file to avoid shell escaping issues
        payload_file = "/tmp/gh_model_payload.json"
        with open(payload_file, "w") as f:
            json.dump(payload, f)
        
        # Call the GitHub Models API
        api_endpoint = "https://models.github.ai/inference/chat/completions"
        stdout, stderr, code = run_command(
            f"gh api {api_endpoint} --method POST --input {payload_file}"
        )
        
        if code == 0:
            data = json.loads(stdout)
            return data['choices'][0]['message']['content']
        else:
            return f"Error calling LLM (model={model}): {stderr}"
    
    except Exception as e:
        return f"Exception calling LLM (model={model}): {str(e)}"

def read_plans():
    return PLANS_FILE.read_text()

def read_tasks():
    return TASKS_FILE.read_text()

def get_next_task():
    tasks_content = read_tasks()
    # Find the first uncompleted task under "Active Tasks"
    match = re.search(r"## 🚀 Active Tasks\n(.*?)\n##", tasks_content, re.DOTALL)
    if match:
        tasks_list = match.group(1).strip().split("\n")
        for line in tasks_list:
            if line.startswith("- [ ]"):
                return line[5:].strip()
    return None

def configure_git_identity(model_name):
    """Configure git committer identity to show which AI model made the commit."""
    # Extract just the model part (e.g., "openai/gpt-4.1")
    model_display = model_name.replace("/", "-")
    committer_name = f"{model_display} (Autonomous Agent)"
    committer_email = f"{model_display}@autonomous-agent.local"
    
    run_command(f'git config user.name "{committer_name}"')
    run_command(f'git config user.email "{committer_email}"')
    print(f"Git identity set to: {committer_name}")
    return committer_name


def commit_changes(message):
    """Stage and commit all changes with the configured git identity."""
    run_command("git add -A")
    run_command(f'git commit -m "{message}"')


def main():
    print(f"--- AutonomousORG Agent Run: {datetime.now().isoformat()} ---")
    
    # Display available models and select one FIRST
    models = get_available_models()
    selected_model = select_model()
    
    # Print selected model early so workflow can capture it
    print(f"Selected model: {selected_model}")
    
    if models:
        print(f"Available models: {len(models)} models found")
        print(f"Using selection strategy: {MODEL_SELECTION_STRATEGY}")
    else:
        print("Warning: Could not fetch available models list")
    
    # Configure git identity based on selected model
    configure_git_identity(selected_model)

    next_task = get_next_task()

    if not next_task:
        print("No active tasks found. Checking plans...")
        # Generate tasks from plans using LLM
        print("Generating new tasks from PLANS.md...")
        plans_content = read_plans()
        if plans_content.strip():
            system_prompt = """You are a task planner for an autonomous agent. 
Given a strategic plan, break it down into specific, actionable tasks.
Return tasks in the format: "- [ ] task description" (one per line)"""
            user_prompt = f"Generate 3-5 specific tasks from this plan:\n\n{plans_content}"
            
            try:
                task_suggestions = call_llm(system_prompt, user_prompt)
                print(f"LLM suggested tasks:\n{task_suggestions}")
                # TODO: Parse and add these to TASKS.md
            except Exception as e:
                print(f"Failed to generate tasks: {e}")
        return

    print(f"Selected Task: {next_task}")

    # Execute Task using LLM
    system_prompt = f"""You are an autonomous agent working on the autonomousORG project.
Your current task is: {next_task}
Provide helpful guidance on how to complete this task."""
    user_prompt = f"I need to complete this task: {next_task}. Please provide specific guidance."
    
    try:
        guidance = call_llm(system_prompt, user_prompt)
        print(f"LLM Guidance:\n{guidance}")
    except Exception as e:
        print(f"Failed to get LLM guidance: {e}")

    # Create Diary Entry
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_file = DIARY_DIR / f"{date_str}.md"

    report_content = f"""# 📔 Daily Progress Report - {date_str}

## 🎯 Task of the Day
**{next_task}**

## 📝 Activity Log
- Started the autonomous workflow.
- Initialized `PLANS.md` and `TASKS.md`.
- Set up the `docs/diary` for public reporting.
- Implemented dynamic model selection to avoid hardcoded model names.

## 🤖 Model Selection
- Strategy: {MODEL_SELECTION_STRATEGY}
- Available models: {len(models) if models else 'unknown'}
- Using: {select_model() if models else 'fallback'}

## 🚀 Next Steps
- Implement the actual LLM-based task execution.
- Automated commitment of changes.
"""
    report_file.write_text(report_content)
    print(f"Report written to {report_file}")

    # Update TASKS.md (mark as completed)
    tasks_content = read_tasks()
    new_tasks_content = tasks_content.replace(f"- [ ] {next_task}", f"- [x] {next_task}")
    # Move to history
    if "## 📖 Task History" in new_tasks_content:
        history_line = f"- [x] {next_task} ({date_str})"
        new_tasks_content = new_tasks_content.replace("## 📖 Task History\n*(Empty)*", f"## 📖 Task History\n{history_line}")
        if history_line not in new_tasks_content:
             new_tasks_content = new_tasks_content.replace("## 📖 Task History", f"## 📖 Task History\n{history_line}")

    TASKS_FILE.write_text(new_tasks_content)
    print("Updated TASKS.md")
    
    # Commit changes with model-based identity
    commit_changes(f"Agent: completed task '{next_task}'")

if __name__ == "__main__":
    main()
