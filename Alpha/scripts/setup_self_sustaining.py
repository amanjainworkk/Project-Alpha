#!/usr/bin/env python3
"""setup_self_sustaining.py - Project Alpha Self-Sustaining Local Backup Initializer.

Configures Project Alpha to run 100% locally on this machine using Ollama
and local Vault storage with zero cloud API keys, zero token costs, and zero network dependencies.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def print_status(step: str, msg: str, status: str = "INFO"):
    colors = {
        "INFO": "\033[94m[*]\033[0m",
        "OK": "\033[92m[OK]\033[0m",
        "WARN": "\033[93m[!]\033[0m",
        "ERR": "\033[91m[ERR]\033[0m",
    }
    prefix = colors.get(status, "[*]")
    print(f"{prefix} {step}: {msg}")


def check_and_start_ollama() -> bool:
    """Ensure Ollama daemon is reachable on http://127.0.0.1:11434."""
    print_status("Ollama Check", "Checking local Ollama service on 127.0.0.1:11434...")
    
    # 1. Test connection
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/", timeout=2.0) as resp:
            if resp.status == 200:
                print_status("Ollama Check", "Ollama daemon is active and responsive.", "OK")
                return True
    except Exception:
        pass

    # 2. Try starting Ollama if not running
    print_status("Ollama Check", "Ollama daemon not reachable. Attempting background launch...", "WARN")
    ollama_paths = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Ollama" / "ollama.exe",
        Path("C:/Program Files/Ollama/ollama.exe"),
    ]
    
    ollama_bin = None
    for p in ollama_paths:
        if p.exists():
            ollama_bin = p
            break
            
    if not ollama_bin:
        print_status("Ollama Check", "Ollama executable not found in standard paths. Please install from https://ollama.com", "ERR")
        return False

    try:
        subprocess.Popen([str(ollama_bin), "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Wait up to 10s for startup
        for _ in range(10):
            time.sleep(1)
            try:
                with urllib.request.urlopen("http://127.0.0.1:11434/", timeout=1.0) as resp:
                    if resp.status == 200:
                        print_status("Ollama Check", "Ollama daemon successfully started in background.", "OK")
                        return True
            except Exception:
                continue
    except Exception as e:
        print_status("Ollama Check", f"Failed to start Ollama daemon: {e}", "ERR")
        return False

    return False


def verify_or_pull_model(model_name: str = "llama3.2:1b") -> bool:
    """Verify that the required local model is installed in Ollama."""
    print_status("Model Verification", f"Verifying local model '{model_name}'...")
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            installed = [m["name"] for m in data.get("models", [])]
            
            # Check for exact or prefixed match
            for m in installed:
                if m == model_name or m.startswith(f"{model_name}:") or m.startswith(model_name):
                    print_status("Model Verification", f"Local model '{m}' is installed and ready.", "OK")
                    return True
                    
        # Model not found, trigger pull
        print_status("Model Pull", f"Pulling lightweight model '{model_name}' via Ollama API...", "WARN")
        payload = json.dumps({"name": model_name, "stream": False}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/pull",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            if res_data.get("status") == "success":
                print_status("Model Pull", f"Model '{model_name}' downloaded successfully.", "OK")
                return True
    except Exception as e:
        print_status("Model Verification", f"Failed to verify or pull model: {e}", "ERR")
        return False

    return False


def configure_offline_env() -> Path:
    """Create or update .env configured for pure local sovereign operation."""
    print_status("Configuration", "Configuring self-sustaining offline profile (.env)...")
    env_path = PROJECT_ROOT / ".env"
    
    offline_vars = {
        "ALPHA_OFFLINE": "1",
        "ALPHA_PROVIDER": "ollama",
        "DEFAULT_MODEL": "llama3.2:1b",
        "OLLAMA_HOST": "http://127.0.0.1:11434",
        "ALPHA_EMBEDDINGS": "mock",
        "ALPHA_PORT": "8765",
        "ALPHA_TOKEN": "test_alpha_bearer_token_secret_xyz789",
    }
    
    existing = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()
                
    existing.update(offline_vars)
    
    content_lines = [
        "# ====================================================================",
        "# Project Alpha — Self-Sustaining Offline Configuration",
        "# ====================================================================",
    ]
    for k, v in existing.items():
        content_lines.append(f"{k}={v}")
        
    env_path.write_text("\n".join(content_lines) + "\n", encoding="utf-8")
    print_status("Configuration", f"Saved configuration to {env_path}", "OK")
    return env_path


def initialize_local_vault() -> bool:
    """Run Vault initialization for offline operation."""
    print_status("Vault Bootstrap", "Bootstrapping Vault directories, SQLite tables, and agents...")
    try:
        from backend.setup.vault_init import initialize_vault
        vault_dir = PROJECT_ROOT / "Alpha-Vault"
        initialize_vault(
            vault_dir=vault_dir,
            force=False,
            founder_name="Aman Jain",
            company_name="Alpha OS",
            use_mock_embeddings=True,
        )
        print_status("Vault Bootstrap", "Vault directories and 13 C-Suite agents verified.", "OK")
        return True
    except Exception as e:
        print_status("Vault Bootstrap", f"Vault initialization error: {e}", "ERR")
        return False


def test_local_inference() -> bool:
    """Conduct a dry-run test prompt to the local Ollama LLM."""
    print_status("Inference Test", "Executing test prompt to local Ollama CEO agent...")
    try:
        from backend.model_router.ollama_client import OllamaClient
        client = OllamaClient(
            host="http://127.0.0.1:11434",
            default_model="llama3.2:1b",
            mock_mode=False,
        )
        resp = client.generate(
            prompt="Hello Alpha CEO, are you ready for local autonomous execution?",
            system_prompt="You are the CEO of Project Alpha running locally on the user's sovereign desktop.",
        )
        print_status("Inference Test", f"Local CEO response received ({len(resp.content)} chars):", "OK")
        print(f"\n    \033[96m\"{resp.content.strip()[:180]}...\"\033[0m\n")
        return True
    except Exception as e:
        print_status("Inference Test", f"Local inference failed: {e}", "ERR")
        return False


def main() -> int:
    print("\n" + "=" * 65)
    print("      PROJECT ALPHA — SELF-SUSTAINING BACKUP INITIALIZER")
    print("=" * 65 + "\n")
    
    # 1. Ollama daemon check
    if not check_and_start_ollama():
        print_status("FATAL", "Ollama is required for self-sustaining local mode.", "ERR")
        return 1

    # 2. Model check
    if not verify_or_pull_model("llama3.2:1b"):
        print_status("FATAL", "Could not verify or pull local model llama3.2:1b.", "ERR")
        return 1

    # 3. Offline .env
    configure_offline_env()

    # 4. Vault Bootstrap
    if not initialize_local_vault():
        print_status("FATAL", "Vault bootstrap failed.", "ERR")
        return 1

    # 5. Live Inference Test
    if not test_local_inference():
        print_status("FATAL", "Live inference test failed.", "ERR")
        return 1

    print("=" * 65)
    print(" \033[92mSUCCESS: Project Alpha Self-Sustaining Local Mode is Fully Operational!\033[0m")
    print(" To start your local CEO and C-Suite backend at any time, run:")
    print("     \033[96m.\\start_alpha_local.bat\033[0m   (or python alpha.py start --offline)")
    print("=" * 65 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
