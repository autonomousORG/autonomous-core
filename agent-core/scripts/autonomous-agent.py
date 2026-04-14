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

def run_command(command, shell=True):
    result = subprocess.run(command, shell=shell, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def call_llm(system_prompt, user_prompt):
    """Call LLM via gh api (GitHub Models)."""
    # This is a placeholder for the actual LLM call logic
    # We will use the 'gh api' approach seen in idea-agent.py if possible.
    # For now, let's assume we can use a generic model.
    # We'll use a script to wrap this call to keep it clean.
    
    # Simple prompt for testing
    full_prompt = f"SYSTEM: {system_prompt}\n\nUSER: {user_prompt}"
    
    # In a real environment, we'd do something like:
    # gh api /models/chat/completions -f model=gpt-4 -f messages='[{"role":"system","content":"..."},{"role":"user","content":"..."}]'
    
    # For this task, I'll implement a basic version that uses gh api if available
    # or just returns a mock if not.
    
    try:
        # Construct the JSON for gh api
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        payload = {
            "model": "gpt-4o", # Or whatever is available in the environment
            "messages": messages,
            "temperature": 0.7
        }
        
        # This is a bit complex to run directly via subprocess with escaping
        # So we'll write it to a temp file
        with open("prompt_payload.json", "w") as f:
            json.dump(payload, f)
            
        stdout, stderr, code = run_command("gh api /repos/github/models/chat/completions --method POST --input prompt_payload.json")
        
        if code == 0:
            data = json.loads(stdout)
            return data['choices'][0]['message']['content']
        else:
            # Fallback or error
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

def main():
    print(f"--- AutonomousORG Agent Run: {datetime.now().isoformat()} ---")
    
    next_task = get_next_task()
    
    if not next_task:
        print("No active tasks found. Checking plans...")
        # TODO: Generate tasks from plans
        print("Generating new tasks from PLANS.md...")
        # (Simplified for now)
        return

    print(f"Selected Task: {next_task}")
    
    # Execute Task
    # (This is where the agent would modify the repo)
    # Since I am the agent right now, I am setting up the foundation.
    
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

if __name__ == "__main__":
    main()
