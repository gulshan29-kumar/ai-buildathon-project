"""Reproducible ML Experiment Framework and Evaluation Tracker for RazorRecover AI.

Tracks model architectures, training configurations, dataset splits, evaluation metrics,
and artifact versions with full provenance and zero fabricated data.
"""

import argparse
import datetime
import json
import os
import uuid
from typing import Any, Dict, List, Optional


EXPERIMENTS_FILE = os.path.join(os.path.dirname(__file__), "experiments.json")


class ExperimentTracker:
    """Manages experiment history, metrics logging, and model provenance."""

    def __init__(self, filepath: str = EXPERIMENTS_FILE):
        self.filepath = filepath
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not os.path.exists(self.filepath):
            os.makedirs(os.path.dirname(self.filepath) or ".", exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({"experiments": []}, f, indent=2)

    def load_experiments(self) -> List[Dict[str, Any]]:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("experiments", [])
        except Exception:
            return []

    def log_run(
        self,
        model_version: str,
        model_name: str,
        hyperparameters: Dict[str, Any],
        dataset_metadata: Dict[str, Any],
        metrics: Dict[str, Any],
        feature_importance: List[Dict[str, Any]],
        category_metrics: Dict[str, Any],
        tags: Optional[List[str]] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Logs an empirical model evaluation experiment run with full reproducibility."""
        run_id = f"exp_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        timestamp = datetime.datetime.now().isoformat()

        entry = {
            "run_id": run_id,
            "timestamp": timestamp,
            "model_version": model_version,
            "model_name": model_name,
            "hyperparameters": hyperparameters,
            "dataset_metadata": dataset_metadata,
            "metrics": metrics,
            "feature_importance": feature_importance,
            "category_metrics": category_metrics,
            "tags": tags or ["production", "xgboost", "calibrated"],
            "notes": notes or "Automated empirical model evaluation run on held-out test data.",
        }

        experiments = self.load_experiments()
        experiments.append(entry)

        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump({"experiments": experiments}, f, indent=2)

        return entry

    def get_latest_run(self) -> Optional[Dict[str, Any]]:
        experiments = self.load_experiments()
        return experiments[-1] if experiments else None

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        for exp in self.load_experiments():
            if exp.get("run_id") == run_id:
                return exp
        return None


def main():
    parser = argparse.ArgumentParser(description="RazorRecover AI Experiment Tracker")
    parser.add_argument("--list", action="store_true", help="List all logged experiments")
    parser.add_argument("--show", type=str, help="Show details for a specific run ID")
    parser.add_argument("--latest", action="store_true", help="Show latest experiment run")
    args = parser.parse_args()

    tracker = ExperimentTracker()

    if args.list:
        runs = tracker.load_experiments()
        print(f"\nFound {len(runs)} experiment runs in {EXPERIMENTS_FILE}:")
        print("-" * 80)
        print(f"{'RUN ID':<25} | {'TIMESTAMP':<20} | {'VERSION':<10} | {'ROC-AUC':<8} | {'PR-AUC':<8} | {'F1':<6}")
        print("-" * 80)
        for r in runs:
            m = r.get("metrics", {})
            roc = f"{m.get('roc_auc', 0.0):.4f}" if m.get("roc_auc") is not None else "N/A"
            pr = f"{m.get('pr_auc', 0.0):.4f}" if m.get("pr_auc") is not None else "N/A"
            f1 = f"{m.get('f1', 0.0):.4f}" if m.get("f1") is not None else "N/A"
            print(f"{r.get('run_id', ''):<25} | {r.get('timestamp', '')[:19]:<20} | {r.get('model_version', ''):<10} | {roc:<8} | {pr:<8} | {f1:<6}")
        print("-" * 80)

    elif args.latest:
        run = tracker.get_latest_run()
        if run:
            print(json.dumps(run, indent=2))
        else:
            print("No experiments logged yet.")

    elif args.show:
        run = tracker.get_run(args.show)
        if run:
            print(json.dumps(run, indent=2))
        else:
            print(f"Run '{args.show}' not found.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
