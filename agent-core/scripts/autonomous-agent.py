#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import re
import time
from datetime import datetime
from pathlib import Path

# --- Configuration ---
PLANS_FILE = Path("PLANS.md")
TASKS_FILE = Path("TASKS.md")
DIARY_DIR = Path("docs/diary")
PROMPT_FILE = Path("agent-core/agent-prompt.md")

# Model selection strategy: first_openai, cheapest, most_capable, or a specific model string
MODEL_STRATEGY = os.environ.get("MODEL_SELECTION_STRATEGY", "first_openai")
MAX_TURNS = int(os.environ.get("MAX_TURNS", "20"))
API_ENDPOINT = "https://models.github.ai/inference/chat/completions"

# --- Utilities ---

def log(msg):
    """Pi-mono style concise logging."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def run_command(command, shell=True):
    result = subprocess.run(command, shell=shell, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def get_available_models():
    """Fetch available models from GitHub Models API using gh models CLI."""
    try:
        stdout, stderr, code = run_command("gh models list")
        if code != 0:
            log(f"Warning: gh models list failed: {stderr}")
            return []
        
        models = []
        for line in stdout.split('\n'):
            parts = line.split()
            if parts and '/' in parts[0]:
                models.append(parts[0])
        return models
    except Exception as e:
        log(f"Exception fetching models: {str(e)}")
        return []

def select_model(strategy=MODEL_STRATEGY):
    """Select a model based on strategy or use environment override."""
    env_model = os.environ.get("AGENT_MODEL")
    if env_model:
        return env_model
    
    models = get_available_models()
    if not models:
        # Fallback if gh models list fails or returns empty
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
        for p in ["gpt-4o", "gpt-4", "claude-3-5-sonnet"]:
            for m in models:
                if p in m.lower():
                    return m
        return models[0]
    else:
        # Default to the first available model
        return models[0]

# --- Core Tools (pi-mono style) ---

def tool_read_file(path):
    """Read file content."""
    try:
        p = Path(path)
        if not p.exists():
            return f"Error: {path} not found."
        return p.read_text()
    except Exception as e:
        return f"Error: {str(e)}"

def tool_write_file(path, content):
    """Overwrite or create file."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Success: Wrote to {path}"
    except Exception as e:
        return f"Error: {str(e)}"

def tool_edit_file(path, old, new):
    """Surgical edit via exact string replacement."""
    try:
        p = Path(path)
        if not p.exists():
            return f"Error: {path} not found."
        content = p.read_text()
        if old not in content:
            return f"Error: Exact match not found in {path}"
        if content.count(old) > 1:
            return f"Error: Multiple matches for 'old' string in {path}. Provide more context."
        
        p.write_text(content.replace(old, new))
        return f"Success: Updated {path}"
    except Exception as e:
        return f"Error: {str(e)}"

def tool_bash(command):
    """Run shell command."""
    stdout, stderr, code = run_command(command)
    return json.dumps({"stdout": stdout, "stderr": stderr, "exit_code": code}, indent=2)

def tool_grep(pattern, path=".", include=None):
    """Search for pattern in files."""
    cmd = f'grep -r "{pattern}" "{path}"'
    if include:
        cmd += f' --include="{include}"'
    stdout, stderr, code = run_command(cmd)
    return stdout if code == 0 else f"No matches found. {stderr}"

def tool_find(name, path="."):
    """Find files by name."""
    stdout, stderr, code = run_command(f'find "{path}" -name "{name}"')
    return stdout if code == 0 else f"Not found. {stderr}"

def tool_list_files(path="."):
    """List files recursively."""
    files = []
    try:
        for root, _, filenames in os.walk(path):
            if ".git" in root or "__pycache__" in root:
                continue
            for f in filenames:
                files.append(os.path.relpath(os.path.join(root, f), path))
        return "\n".join(sorted(files))
    except Exception as e:
        return f"Error: {str(e)}"

def tool_finish(report, status="completed"):
    """Complete task and submit report."""
    return f"FINISH:{status}:{report}"

TOOLS = {
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "edit_file": tool_edit_file,
    "bash": tool_bash,
    "grep": tool_grep,
    "find": tool_find,
    "list_files": tool_list_files,
    "finish": tool_finish
}

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read content of a file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Surgically edit a file via exact string replacement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old": {"type": "string", "description": "The exact string to be replaced."},
                    "new": {"type": "string", "description": "The new string."}
                },
                "required": ["path", "old", "new"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search for pattern in files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "include": {"type": "string", "description": "Glob pattern for files to include."}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find",
            "description": "Find files by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "path": {"type": "string", "default": "."}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "default": "."}}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Submit report and end session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "report": {"type": "string", "description": "Technical summary of work done."},
                    "status": {"type": "string", "enum": ["completed", "failed", "partially_completed"], "default": "completed"}
                },
                "required": ["report"]
            }
        }
    }
]

# --- LLM Communication ---

def call_llm(messages, model, retries=3):
    """Call GitHub Models API via gh CLI."""
    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOL_DEFS,
        "tool_choice": "auto",
        "temperature": 0.1
    }
    
    payload_file = "/tmp/agent_payload.json"
    with open(payload_file, "w") as f:
        json.dump(payload, f)
    
    for i in range(retries):
        stdout, stderr, code = run_command(f"gh api {API_ENDPOINT} --method POST --input {payload_file}")
        if code == 0:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                log("Error: Failed to decode LLM response JSON.")
                return None
        else:
            log(f"LLM call failed (attempt {i+1}/{retries}): {stderr}")
            if "rate limit" in stderr.lower() or "429" in stderr:
                time.sleep(10 * (i + 1))
            else:
                time.sleep(2)
    return None

# --- Task Management ---

def get_next_task():
    try:
        content = TASKS_FILE.read_text()
        match = re.search(r"## 🚀 Active Tasks\n(.*?)\n##", content, re.DOTALL)
        if match:
            for line in match.group(1).strip().split("\n"):
                if line.startswith("- [ ]"):
                    return line[5:].strip()
    except Exception as e:
        log(f"Error reading tasks: {str(e)}")
    return None

def finalize_task(task, status, report):
    """Mark task as complete and write diary entry."""
    now = datetime.now()
    log(f"Finalizing task: {status}")
    
    # Write Diary
    slug = re.sub(r'[^a-z0-9]+', '-', task.lower()).strip('-')
    diary_dir = DIARY_DIR / now.strftime("%Y/%m/%d")
    diary_dir.mkdir(parents=True, exist_ok=True)
    diary_path = diary_dir / f"{now.strftime('%H%M%S')}_{slug}.md"
    
    diary_content = f"# 📔 Progress Report - {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    diary_content += f"## 🎯 Task: {task}\n\n"
    diary_content += f"**Status**: {status}\n\n"
    diary_content += "## 📝 Report\n\n" + report
    diary_path.write_text(diary_content)
    
    # Update TASKS.md
    try:
        content = TASKS_FILE.read_text()
        content = content.replace(f"- [ ] {task}", f"- [x] {task}")
        if "## 📖 Task History" in content:
            history_line = f"- [x] {task} ({now.strftime('%Y-%m-%d')})"
            if history_line not in content:
                content = content.replace("## 📖 Task History", f"## 📖 Task History\n{history_line}")
        TASKS_FILE.write_text(content)
    except Exception as e:
        log(f"Error updating tasks: {str(e)}")

# --- Main Loop ---

def main():
    log("AutonomousORG Agent starting.")
    
    model = select_model()
    log(f"Selected model: {model}")
    
    # Configure local git identity for this agent session
    model_name = model.replace("/", "-")
    run_command(f'git config --local user.name "{model_name} (Autonomous Agent)"')
    run_command(f'git config --local user.email "{model_name}@autonomousorg.com"')

    task = get_next_task()
    if not task:
        log("No active tasks found.")
        return

    log(f"Active Task: {task}")
    
    messages = [
        {"role": "system", "content": PROMPT_FILE.read_text()},
        {"role": "user", "content": f"Execute: {task}"}
    ]

    turn = 0
    while turn < MAX_TURNS:
        turn += 1
        log(f"Turn {turn}/{MAX_TURNS}")
        
        response = call_llm(messages, model)
        if not response:
            log("Critical Error: LLM returned no response.")
            break
            
        message = response['choices'][0]['message']
        messages.append(message)
        
        if message.get('content'):
            log(f"Agent: {message['content']}")
            
        tool_calls = message.get('tool_calls')
        if not tool_calls:
            log("Agent stopped without tool calls.")
            break
            
        for tool_call in tool_calls:
            name = tool_call['function']['name']
            args = json.loads(tool_call['function']['arguments'])
            log(f"Tool Call: {name}({json.dumps(args)})")
            
            if name in TOOLS:
                result = TOOLS[name](**args)
                
                # Check for finish signal
                if name == "finish":
                    finalize_task(task, args.get('status', 'completed'), args['report'])
                    log("Task finished.")
                    return
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call['id'],
                    "name": name,
                    "content": str(result)
                })
            else:
                log(f"Error: Tool {name} not found.")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call['id'],
                    "name": name,
                    "content": f"Error: Tool {name} not found."
                })
                
    if turn >= MAX_TURNS:
        log("Error: Reached MAX_TURNS.")

if __name__ == "__main__":
    main()
