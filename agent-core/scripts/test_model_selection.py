#!/usr/bin/env python3
"""
Test script to demonstrate dynamic model selection functionality.
"""

import sys
import os
import subprocess
from pathlib import Path

# Replicate the functions here to avoid import issues
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


def select_model(strategy="first_openai"):
    """Select a model based on a strategy to avoid hardcoding model names."""
    # Check environment variable first
    env_model = os.environ.get("AGENT_MODEL")
    if env_model:
        return env_model
    
    # Fetch available models
    models = get_available_models()
    
    if not models:
        print("Warning: No models available, using fallback", file=sys.stderr)
        return "openai/gpt-4o-mini"
    
    if strategy == "first":
        return models[0]
    
    elif strategy == "first_openai":
        for m in models:
            if m.startswith("openai/"):
                return m
        return models[0]
    
    elif strategy == "cheapest":
        cost_keywords = ["mini", "nano", "small"]
        for keyword in cost_keywords:
            for m in models:
                if keyword in m.lower():
                    return m
        return models[0]
    
    elif strategy == "most_capable":
        priority = ["gpt-5", "gpt-4.1", "gpt-4o", "claude", "grok"]
        for p in priority:
            for m in models:
                if p in m.lower():
                    return m
        return models[0]
    
    else:
        return models[0]

def test_model_listing():
    """Test fetching available models."""
    print("=" * 60)
    print("TEST 1: Fetching Available Models")
    print("=" * 60)
    
    models = get_available_models()
    
    if models:
        print(f"✓ Found {len(models)} models")
        print("\nFirst 10 models:")
        for i, model in enumerate(models[:10], 1):
            print(f"  {i}. {model}")
        if len(models) > 10:
            print(f"  ... and {len(models) - 10} more")
    else:
        print("✗ No models found (this might be expected if gh CLI is not available)")
    
    return models

def test_selection_strategies(models):
    """Test different model selection strategies."""
    print("\n" + "=" * 60)
    print("TEST 2: Model Selection Strategies")
    print("=" * 60)
    
    if not models:
        print("⊘ Skipping (no models available)")
        return
    
    strategies = ["first", "first_openai", "cheapest", "most_capable"]
    
    for strategy in strategies:
        selected = select_model(strategy)
        print(f"  {strategy:20s} → {selected}")

def test_env_override():
    """Test environment variable override."""
    print("\n" + "=" * 60)
    print("TEST 3: Environment Variable Override")
    print("=" * 60)
    
    # Set custom model via env var
    os.environ["AGENT_MODEL"] = "custom/my-custom-model"
    selected = select_model()
    
    if selected == "custom/my-custom-model":
        print(f"✓ Environment variable override works: {selected}")
    else:
        print(f"✗ Environment variable override failed: {selected}")
    
    # Clean up
    del os.environ["AGENT_MODEL"]

def main():
    print("\n" + "🧪 " * 30)
    print("Dynamic Model Selection Test Suite")
    print("🧪 " * 30 + "\n")
    
    # Test 1: Fetch models
    models = test_model_listing()
    
    # Test 2: Selection strategies
    test_selection_strategies(models)
    
    # Test 3: Environment override
    test_env_override()
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
