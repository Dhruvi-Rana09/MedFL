"""
model.py — MedModel CNN for MNIST digit classification.

Architecture designed for Opacus (differential privacy) compatibility:
- No in-place operations
- No batch normalization (DP requires per-sample gradients)
- Uses nn.Sequential for clean GradSampleModule wrapping
"""

import torch.nn as nn


class MedModel(nn.Module):
    """2-layer CNN for 28×28 grayscale image classification (MNIST/medical)."""

    def __init__(self, n_classes: int = 10):
        super(MedModel, self).__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Flatten(),

            nn.Linear(64 * 7 * 7, 128),
            nn.ReLU(),

            nn.Linear(128, n_classes),
        )

    def forward(self, x):
        return self.features(x)
