"""Synthetic equipment sensors and an actual trained ML classifier.

The generator is a pedagogic model, not a physical model of any real machine.
Ground-truth labels are never included in the inference feature vector.
"""
from pathlib import Path
import json
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
import joblib

CLASSES = ['NORMAL', 'OVERHEAT', 'VIBRATION']
FEATURES = ['temperature_mean_C', 'temperature_std_C', 'vibration_rms',
            'vibration_kurtosis', 'low_band_power_ratio', 'high_band_power_ratio']

def sample(label, rng, stress=False):
    """One independent 1-second trace, 256 Hz vibration + 16 thermal samples."""
    n = 256
    t = np.arange(n) / n
    frequency = rng.uniform(18, 32)
    phase = rng.uniform(0, 2*np.pi)
    gain = rng.uniform(.75, 1.25)
    amp = [rng.uniform(.10, .25), rng.uniform(.12, .28), rng.uniform(.30, .58)][label]
    vibration = gain * amp * np.sin(2*np.pi*frequency*t + phase)
    vibration += rng.normal(0, .045 if not stress else .11, n)
    if label == 2:
        vibration += rng.uniform(.13, .32)*np.sin(2*np.pi*rng.uniform(65, 95)*t)
        indices = rng.choice(n, size=6, replace=False)
        vibration[indices] += rng.uniform(.5, 1.1, 6)
    thermal_base = rng.normal([40, 70, 44][label], [5.5, 7.5, 6.5][label])
    thermal = thermal_base + rng.normal(0, 1.5 if not stress else 4., 16)
    if stress:
        thermal += rng.normal(-5, 6)  # distribution shift, NOT independent real data
    return vibration, thermal

def extract(vibration, thermal):
    centered = vibration - vibration.mean()
    power = np.abs(np.fft.rfft(centered))**2
    frequencies = np.fft.rfftfreq(len(centered), 1/256)
    total = power.sum() + 1e-12
    variance = np.mean(centered**2) + 1e-12
    return np.array([thermal.mean(), thermal.std(), np.sqrt(np.mean(vibration**2)),
                     np.mean(centered**4)/variance**2,
                     power[(frequencies>=10)&(frequencies<50)].sum()/total,
                     power[frequencies>=60].sum()/total])

def dataset(seed, per_class, stress=False):
    rng = np.random.default_rng(seed)
    X, y = [], []
    for label in range(3):
        for _ in range(per_class):
            X.append(extract(*sample(label, rng, stress)))
            y.append(label)
    return np.array(X), np.array(y)

def decision(label, confidence, threshold=.70):
    """Allowlisted semantic output; low confidence never declares NORMAL."""
    if label not in CLASSES or not np.isfinite(confidence) or not 0 <= confidence <= 1 or confidence < threshold:
        return 'RECHECK'
    return {'NORMAL':'CONTINUE', 'OVERHEAT':'ADD_EXCLUSION',
            'VIBRATION':'FLAG_MAINTENANCE'}[label]

def train(out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    X, y = dataset(42, 600)
    model = RandomForestClassifier(n_estimators=120, max_depth=8,
                                   min_samples_leaf=3, random_state=42, n_jobs=1)
    model.fit(X, y)
    metrics = {'classes':CLASSES, 'features':FEATURES, 'train_samples':len(y),
               'train_seed':42, 'test_seed':2026, 'stress_seed':2027,
               'confidence_threshold':.70,
               'data_scope':'Synthetic IID holdout and synthetic shifted-noise stress only; no real-data claim.'}
    for name, seed, stress in [('test',2026,False),('stress',2027,True)]:
        Xt, yt = dataset(seed, 200, stress)
        prediction = model.predict(Xt)
        confidence = model.predict_proba(Xt).max(axis=1)
        accepted = confidence >= .7
        metrics[name] = {'samples':len(yt), 'accuracy':float(accuracy_score(yt,prediction)),
            'macro_f1':float(f1_score(yt,prediction,average='macro')),
            'confusion_matrix':confusion_matrix(yt,prediction,labels=[0,1,2]).tolist(),
            'accepted_fraction':float(accepted.mean()),
            'accuracy_when_accepted':float(accuracy_score(yt[accepted],prediction[accepted])) if accepted.any() else None}
    metrics['feature_importance'] = dict(zip(FEATURES,model.feature_importances_.tolist()))
    joblib.dump(model, out/'classifier.joblib')
    (out/'ml_metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    return model, metrics

def infer(model, true_label, seed):
    # True label is used ONLY by the simulated sensor environment.
    # The classifier receives 6 measured features and never receives true_label.
    vibration, thermal = sample(true_label, np.random.default_rng(seed))
    features = extract(vibration, thermal)
    probabilities = model.predict_proba([features])[0]
    index = int(probabilities.argmax())
    label = CLASSES[int(model.classes_[index])]
    confidence = float(probabilities[index])
    return {'prediction':label,'confidence':confidence,
            'action':decision(label,confidence),'features':features.tolist(),
            'probabilities':dict(zip(CLASSES,probabilities.tolist()))}
