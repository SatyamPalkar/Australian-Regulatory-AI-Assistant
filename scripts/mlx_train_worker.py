"""Keep MLX allocation measurement in the process that performs training."""
import json
import sys
from pathlib import Path

import mlx.core as mx
from mlx_lm.lora import main

try:
    main()
finally:
    path = Path("reports/training-worker-memory.json")
    path.write_text(json.dumps({"peak_mlx_memory_gb": mx.get_peak_memory() / 1e9}) + "\n")
