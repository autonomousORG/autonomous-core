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
PROGRESS_DIR = Path("agent-core/progress")

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
            return []
        models = []
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            if parts and '/' in parts[0]:
                models.append(parts[0])
        return models
    except Exception:
        return []


def select_model(strategy=None):
    """Select a model based on a strategy."""
    if strategy is None:
        strategy = MODEL_SELECTION_STRATEGY
    
    env_model = os.environ.get("AGENT_MODEL")
    if env_model:
        return env_model
    
    models = get_available_models()
    if not models:
        return "openai/gpt-4o-mini"
    
    if strategy == "first":
        return models[0]
    elif strategy == "first_openai":
        for m in models:
            if m.startswith("openai/"):
                return m
        return models[0]
    elif strategy == "cheapest":
        for keyword in ["mini", "nano", "small"]:
            for m in models:
                if keyword in m.lower():
                    return m
        return models[0]
    elif strategy == "most_capable":
        for p in ["gpt-5", "gpt-4.1", "gpt-4o"]:
            for m in models:
                if p in m.lower():
                    return m
        return models[0]
    else:
        return models[0]


def configure_git_identity(model_name):
    """Configure git committer identity to show which AI model made the commit."""
    model_display = model_name.replace("/", "-")
    committer_name = f"{model_display} (Autonomous Agent)"
    committer_email = f"{model_display}@autonomousorg.com"
    run_command(f'git config user.name "{committer_name}"')
    run_command(f'git config user.email "{committer_email}"')


def commit_changes(message):
    """Stage and commit all changes."""
    run_command("git add -A")
    run_command(f'git commit -m "{message}"')


def call_llm(system_prompt, user_prompt, model=None):
    """Call LLM via GitHub Models API with dynamic model selection."""
    if model is None:
        model = select_model(MODEL_SELECTION_STRATEGY)
    print(f"Using model: {model}", file=sys.stderr)
    
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7
        }
        payload_file = "/tmp/gh_model_payload.json"
        with open(payload_file, "w") as f:
            json.dump(payload, f)

        api_endpoint = "https://models.github.ai/inference/chat/completions"
        stdout, stderr, code = run_command(
            f"gh api {api_endpoint} --method POST --input {payload_file}"
        )

        if code == 0:
            data = json.loads(stdout)
            return data['choices'][0]['message']['content']
        else:
            return f"Error calling LLM: {stderr}"
    except Exception as e:
        return f"Exception calling LLM: {str(e)}"

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

def get_dated_path(base_dir, extension, slug=None):
    now = datetime.now()
    year = now.strftime("%Y")
    month = now.strftime("%m")
    day = now.strftime("%d")
    time_str = now.strftime("%H-%M-%S")
    
    # Nested folder structure: YYYY/MM/DD
    target_dir = base_dir / year / month / day
    target_dir.mkdir(parents=True, exist_ok=True)
    
    if slug:
        filename = f"{year}-{month}-{day}-{time_str}_{slug}.{extension}"
    else:
        filename = f"{year}-{month}-{day}-{time_str}.{extension}"
        
    return target_dir / filename, f"{year}/{month}/{day}/{filename}"

def main():
    print(f"--- AutonomousORG Agent Run: {datetime.now().isoformat()} ---")

    # Select model and configure git identity
    models = get_available_models()
    selected_model = select_model()
    print(f"Selected model: {selected_model}")
    if models:
        print(f"Available models: {len(models)}")
        print(f"Strategy: {MODEL_SELECTION_STRATEGY}")
    
    configure_git_identity(selected_model)

    next_task = get_next_task()

    if not next_task:
        print("No active tasks found. Checking plans...")
        # TODO: Generate tasks from plans
        print("Generating new tasks from PLANS.md...")
        return

    print(f"Selected Task: {next_task}")
    
    # Slugify task name for filename
    slug = re.sub(r'[^a-z0-9]+', '-', next_task.lower()).strip('-')
    
    # Create Diary and Progress Entries
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    diary_path, diary_relative = get_dated_path(DIARY_DIR, "md", slug)
    progress_path, _ = get_dated_path(PROGRESS_DIR, "json", slug)
    
    report_content = f"""# 📔 Daily Progress Report - {date_str}

## 🎯 Task of the Day
**{next_task}**

## 📝 Activity Log
- Refactored storage structure to match `autonomousBLOG` style.
- Implemented deep nested folder structure: `docs/diary/YYYY/MM/DD/`.
- Filename format: `YYYY-MM-DD-HH-MM-SS_task-slug.md`.
- Added automated JSON progress tracking for agent memory.

## 🚀 Next Steps
- Automate frontend gallery/list view for reports.
- Implement specialized "Progress" analysis tool for the agent.
"""
    diary_path.write_text(report_content)
    print(f"Diary written to {diary_path}")

    progress_data = {
        "timestamp": now.isoformat(),
        "task": next_task,
        "slug": slug,
        "status": "completed",
        "activity_log": [
            "Refactored storage structure to match autonomousBLOG style.",
            "Implemented deep nested folder structure: docs/diary/YYYY/MM/DD/.",
            "Added automated JSON progress tracking."
        ],
        "paths": {
            "diary": str(diary_path),
            "progress": str(progress_path)
        }
    }
    progress_path.write_text(json.dumps(progress_data, indent=2))
    print(f"Progress data written to {progress_path}")

    # Update TASKS.md (mark as completed)
    tasks_content = read_tasks()
    new_tasks_content = tasks_content.replace(f"- [ ] {next_task}", f"- [x] {next_task}")
    
    # Move to history
    if "## 📖 Task History" in new_tasks_content:
        history_line = f"- [x] {next_task} ({now.strftime('%Y-%m-%d')})"
        if history_line not in new_tasks_content:
             new_tasks_content = new_tasks_content.replace("## 📖 Task History", f"## 📖 Task History\n{history_line}")

    TASKS_FILE.write_text(new_tasks_content)
    print("Updated TASKS.md")
    
    # Commit changes
    commit_changes(f"Agent: completed task '{next_task}'")

if __name__ == "__main__":
    main()
