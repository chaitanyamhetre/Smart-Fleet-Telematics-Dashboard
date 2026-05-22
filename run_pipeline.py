"""
run_pipeline.py
---------------
Orchestrates the full fleet analytics pipeline:
  1. Preprocess raw telematics data
  2. Calculate KPIs
  3. Train ML model

Run from project root:
    python run_pipeline.py
    python run_pipeline.py --skip-model   (preprocess + KPIs only)
    python run_pipeline.py --only-model   (model training only)
"""

import subprocess
import sys
import time
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s"
)
log = logging.getLogger(__name__)

STEPS = {
    "preprocess": "scripts/preprocess.py",
    "kpis":       "scripts/kpi_calculations.py",
    "model":      "models/train_driver_risk_model.py",
}


def run_step(name: str, script: str) -> bool:
    log.info(f"{'='*50}")
    log.info(f"STEP: {name.upper()}")
    log.info(f"Script: {script}")
    log.info(f"{'='*50}")

    t0 = time.time()

    result = subprocess.run(
        [sys.executable, script],
        capture_output=False,
    )

    elapsed = time.time() - t0

    if result.returncode == 0:
        log.info(f"✓ {name} completed in {elapsed:.1f}s")
        return True
    else:
        log.error(f"✗ {name} FAILED after {elapsed:.1f}s (exit code {result.returncode})")
        return False


def main():
    parser = argparse.ArgumentParser(description="Fleet Analytics Pipeline")
    parser.add_argument("--skip-model", action="store_true", help="Skip model training")
    parser.add_argument("--only-model", action="store_true", help="Run model training only")
    args = parser.parse_args()

    pipeline_start = time.time()
    results = {}

    if args.only_model:
        steps_to_run = ["model"]
    elif args.skip_model:
        steps_to_run = ["preprocess", "kpis"]
    else:
        steps_to_run = ["preprocess", "kpis", "model"]

    for step in steps_to_run:
        success = run_step(step, STEPS[step])
        results[step] = success
        if not success:
            log.error(f"Pipeline aborted at step: {step}")
            sys.exit(1)

    total = time.time() - pipeline_start

    log.info("")
    log.info("="*50)
    log.info("  PIPELINE SUMMARY")
    log.info("="*50)
    for step, ok in results.items():
        status = "✓ PASSED" if ok else "✗ FAILED"
        log.info(f"  {step:<20} {status}")
    log.info(f"  Total time: {total:.1f}s")
    log.info("="*50)


if __name__ == "__main__":
    main()
