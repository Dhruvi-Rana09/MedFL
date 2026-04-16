import sys, pickle, torch
sys.path.insert(0, 'services/hospital_node/app')
import os
os.environ['DATA_PATH'] = 'data/hospital_a/dataset.pkl'
os.environ['LOCAL_EPOCHS'] = '2'
os.environ['DP_EPSILON'] = '1.0'
os.environ['DP_DELTA'] = '1e-5'
os.environ['HOSPITAL_ID'] = 'hospital-a'

from model import MedModel
from local_trainer import train_local, get_label_distribution, load_dataset

# Test label dist
ds = load_dataset()
dist = get_label_distribution(ds)
print('Label dist:', [round(x, 3) for x in dist])
print('Non-zero classes:', [i for i, v in enumerate(dist) if v > 0])

# Test training
model = MedModel()
sd, label_dist, n = train_local(model.state_dict())
print('Training done. Samples:', n)
print('Updated keys:', list(sd.keys())[:3])
