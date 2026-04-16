"""
seed_data.py — Download MNIST and create NON-IID splits for 3 hospitals.

Hospital splits by digit class (simulating clinical specializations):
  hospital_a  →  [0, 1, 2, 3]   (cardiac-heavy simulation)
  hospital_b  →  [3, 4, 5, 6]   (general practice, overlaps at 3)
  hospital_c  →  [6, 7, 8, 9]   (paediatric-heavy, overlaps at 6)

Also creates a balanced validation set for global model evaluation.
"""

import os
import pickle
from pathlib import Path
from collections import Counter

import torch
from torch.utils.data import Subset
from torchvision import datasets, transforms

# ── Configuration ────────────────────────────────────────────────────────
DATA_ROOT = Path(__file__).resolve().parent.parent / "data"

HOSPITAL_SPLITS = {
    "hospital_a": [0, 1, 2, 3],
    "hospital_b": [3, 4, 5, 6],
    "hospital_c": [6, 7, 8, 9],
}

TRANSFORM = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.1307,), (0.3081,)),
])


def main() -> None:
    # Maximum samples per hospital — keeps CPU training under 1 minute/epoch
    MAX_SAMPLES = int(os.environ.get("MAX_SAMPLES_PER_HOSPITAL", "500"))

    # 1. Download MNIST (train split)
    print("[*] Downloading MNIST training set...")
    full_dataset = datasets.MNIST(
        root=str(DATA_ROOT / "_raw"),
        train=True,
        download=True,
        transform=TRANSFORM,
    )

    targets = full_dataset.targets  # Tensor of all labels

    # 2. Create NON-IID splits
    print(f"\n[*] Creating non-IID hospital splits (max {MAX_SAMPLES}/hospital):\n")
    for hospital, classes in HOSPITAL_SPLITS.items():
        class_tensor = torch.tensor(classes)
        mask = torch.isin(targets, class_tensor)
        indices = torch.where(mask)[0].tolist()

        # Cap the number of samples for CPU-feasible training
        if len(indices) > MAX_SAMPLES:
            import random
            random.seed(42)  # reproducible
            indices = sorted(random.sample(indices, MAX_SAMPLES))

        subset = Subset(full_dataset, indices)

        # Save filtered subset as pickle
        out_dir = DATA_ROOT / hospital
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "dataset.pkl"

        with open(out_path, "wb") as f:
            pickle.dump(subset, f)

        # Compute distribution
        local_targets = [targets[i].item() for i in indices]
        dist = Counter(local_targets)
        dist_str = "  ".join(f"{c}:{dist.get(c, 0):>5}" for c in range(10))

        print(
            f"  [OK] {hospital:14s}  |  {len(indices):>6,} samples  |  "
            f"classes {classes}"
        )
        print(f"    distribution: {dist_str}\n")

    # 3. Create a balanced validation set (for global model evaluation)
    print("[*] Creating balanced validation set...")
    val_dataset = datasets.MNIST(
        root=str(DATA_ROOT / "_raw"),
        train=False,
        download=True,
        transform=TRANSFORM,
    )

    val_dir = DATA_ROOT / "validation"
    val_dir.mkdir(parents=True, exist_ok=True)

    with open(val_dir / "dataset.pkl", "wb") as f:
        pickle.dump(val_dataset, f)

    print(f"  [OK] validation      |  {len(val_dataset):>6,} samples  |  all classes\n")

    print("[DONE] Seed data written to data/hospital_*/dataset.pkl")
    print("[DONE] Validation data written to data/validation/dataset.pkl")


if __name__ == "__main__":
    main()
