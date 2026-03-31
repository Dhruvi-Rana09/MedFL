import numpy as np
from app.config import INPUT_SIZE

def local_train():
    """
    Simulate local training on hospital data.
    Returns: model weights (list of floats) + number of samples trained on
    """
    # Simulate random starting weights (like a neural net layer)
    weights = np.random.randn(INPUT_SIZE).tolist()

    # Simulate 'learning' — small random gradient update
    learning_rate = 0.01
    gradient = np.random.randn(INPUT_SIZE)
    updated_weights = (np.array(weights) - learning_rate * gradient).tolist()

    num_samples = 100  # Simulated dataset size

    return updated_weights, num_samples