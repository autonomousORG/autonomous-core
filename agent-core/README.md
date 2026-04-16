# 🧠 Agent Core

This directory contains the brains and tools of the **V-Loop** agent.

## 📁 Structure
- `scripts/`: Implementation of the autonomous agent.
  - `autonomous-agent.py`: The core daily loop.
- `agent-prompt.md`: The system prompt defining the agent's behavior.

## 🤖 The Autonomous Workflow
1. **Trigger**: GitHub Action runs once per day.
2. **Research**: The agent reads `PLANS.md` and `TASKS.md`.
3. **Planning**: If no tasks exist, it generates new ones from `PLANS.md`.
4. **Execution**: It picks one task and performs it (code changes, repo updates).
5. **Reporting**: It creates a daily diary entry in `docs/diary/`.
6. **Persistence**: Changes are committed and pushed.
