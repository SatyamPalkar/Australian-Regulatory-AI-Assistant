"""Run an isolated, measured MLX LoRA experiment after validating the frozen split."""
import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_experiment import verify_split
from reg_assistant.core import read_jsonl, write_json
from reg_assistant.rag import local_model, model_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    verify_split()
    config_path = ROOT / ("configs/lora-smoke.yaml" if args.smoke else "configs/lora-experiment.yaml")
    config = yaml.safe_load(config_path.read_text())
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(local_model("generator"), local_files_only=True)
    if args.smoke:
        for split in ("train", "valid"):
            rows = read_jsonl(ROOT / f"data/training/{split}.jsonl")
            short = [r for r in rows if len(tokenizer.apply_chat_template(r["messages"], return_dict=False)) <= config["max_seq_length"]]
            path = ROOT / f"data/training-smoke/{split}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(json.dumps(r) + "\n" for r in short[:4]))
    lengths = {}
    for split in ("train", "valid"):
        rows = read_jsonl(ROOT / config["data"] / f"{split}.jsonl")
        lengths[split] = [len(tokenizer.apply_chat_template(r["messages"], return_dict=False)) for r in rows]
        if not lengths[split] or max(lengths[split]) > config["max_seq_length"]:
            raise ValueError(f"{split} examples would be truncated: {max(lengths[split], default=0)} tokens")
    if (ROOT / config["adapter_path"] / "adapters.safetensors").exists():
        raise ValueError("Adapter already exists; preserve the measured run rather than overwrite it")
    name = "lora-smoke" if args.smoke else "lora-training"
    log_path = ROOT / f"reports/{name}.log"
    start, peak = time.perf_counter(), 0
    with log_path.open("w") as log:
        process = subprocess.Popen([sys.executable, "scripts/mlx_train_worker.py", "--config", str(config_path)],
                                   cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        child = psutil.Process(process.pid)
        while process.poll() is None:
            try:
                peak = max(peak, child.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            time.sleep(.25)
    text = log_path.read_text()
    clean_log = re.sub(r"\x1b\[[0-9;]*m", "", text).replace(str(ROOT) + "/", "")
    (ROOT / f"reports/{name}.txt").write_text(clean_log)
    memories = [float(v) for v in re.findall(r"Peak mem(?:ory)?:\s*([\d.]+)\s*GB", text, re.I)]
    adapter = ROOT / config["adapter_path"] / "adapters.safetensors"
    report = {"completed": process.returncode == 0, "exit_code": process.returncode,
              "created_at": datetime.now(timezone.utc).isoformat(), "config": config,
              "configuration_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
              "model_manifest": model_manifest(), "split_manifest": verify_split(),
              "sequence_lengths": {k: {"examples": len(v), "max_tokens": max(v)} for k, v in lengths.items()},
              "validation_losses": [{"step": int(n), "loss": float(v)} for n, v in re.findall(r"^\s*(\d+)\s+val\s+([\d.]+)", clean_log, re.M)],
              "elapsed_seconds": time.perf_counter() - start,
              "peak_process_rss_gb": peak / 1e9,
              "peak_mlx_memory_gb": json.loads((ROOT / "reports/training-worker-memory.json").read_text())["peak_mlx_memory_gb"],
              "hardware": {"machine": platform.machine(), "platform": platform.platform(),
                           "system_memory_gb": psutil.virtual_memory().total / 1e9},
              "adapter_sha256": hashlib.sha256(adapter.read_bytes()).hexdigest() if adapter.exists() else None,
              "limitations": "Small synthetic training set; loss and successful training do not establish improved answers. Process RSS and MLX allocation are different memory measures. Evaluate the adapter against the same base-RAG test before selecting it."}
    write_json(ROOT / f"reports/{name}.json", report)
    print(text[-9000:])
    print(json.dumps({k: report[k] for k in ("completed", "elapsed_seconds", "peak_process_rss_gb", "peak_mlx_memory_gb")}, indent=2))
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
