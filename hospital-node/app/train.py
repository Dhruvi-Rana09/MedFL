import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import os

from app.config import HOSPITAL_ID

def local_train():
    # Each hospital loads its own CSV
    data_path = f"app/data/{HOSPITAL_ID}.csv"
    
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"No dataset found for {HOSPITAL_ID} at {data_path}")
    
    df = pd.read_csv(data_path)
    X = df.drop("label", axis=1).values
    y = df["label"].values
    
    # Normalize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Train
    model = LogisticRegression(max_iter=200)
    model.fit(X_scaled, y)
    
    weights = model.coef_.flatten().tolist()
    num_samples = len(y)
    
    print(f"[{HOSPITAL_ID}] Trained on {num_samples} samples | "
          f"Positive rate: {y.mean():.0%}")
    
    return weights, num_samples