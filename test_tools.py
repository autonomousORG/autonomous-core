import json
import subprocess

def run_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

api_endpoint = "https://models.github.ai/inference/chat/completions"
payload = {
    "model": "openai/gpt-4o-mini",
    "messages": [
        {"role": "user", "content": "What is the content of the file 'TASKS.md'? Use the read_file tool."}
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the content of a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"}
                    },
                    "required": ["path"]
                }
            }
        }
    ]
}

with open("test_payload.json", "w") as f:
    json.dump(payload, f)

stdout, stderr, code = run_command(f"gh api {api_endpoint} --method POST --input test_payload.json")
print(stdout)
