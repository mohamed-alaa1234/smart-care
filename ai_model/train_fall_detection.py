import os
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, recall_score, precision_score

# Ensure reproducibility
np.random.seed(42)

def generate_synthetic_data(num_samples=1000, window_size=50):
    """
    Generates synthetic dummy accelerometer data for demonstration purposes.
    In a real scenario, you will replace this with the SisFall dataset.
    """
    print("Generating synthetic data for demonstration...")
    X = np.random.normal(0, 1, (num_samples, window_size, 3)) # 3 axes: X, Y, Z
    y = np.random.randint(0, 2, num_samples) # 0: ADL (Activities of Daily Living), 1: Fall
    
    # Inject "fall-like" spikes into the positive class (y=1)
    for i in range(num_samples):
        if y[i] == 1:
            spike_idx = np.random.randint(10, 40)
            X[i, spike_idx, :] += np.random.normal(5, 3, 3) # Large acceleration spike
            
    return X, y

def extract_features(X_windows):
    """
    Extracts statistical features from the time-series window for the Random Forest.
    We extract Mean, Standard Deviation, Max, and Min for each axis.
    """
    features = []
    for window in X_windows:
        mean_vals = np.mean(window, axis=0)
        std_vals = np.std(window, axis=0)
        max_vals = np.max(window, axis=0)
        min_vals = np.min(window, axis=0)
        
        # Combine all features into a single 1D array per window (3*4 = 12 features total)
        window_features = np.concatenate([mean_vals, std_vals, max_vals, min_vals])
        features.append(window_features)
        
    return np.array(features)

def main():
    # 1. Load Data
    WINDOW_SIZE = 50 # 1 second of data at 50Hz
    X_raw, y = generate_synthetic_data(num_samples=2000, window_size=WINDOW_SIZE)
    
    # 2. Extract Features
    X_features = extract_features(X_raw)
    
    # 3. Split Data
    X_train, X_test, y_train, y_test = train_test_split(X_features, y, test_size=0.2, random_state=42, stratify=y)
    
    # 4. Scale Features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 5. Build Model (Random Forest Classification)
    print("Training scikit-learn Random Forest model...")
    model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    model.fit(X_train_scaled, y_train)
    
    # 6. Evaluate
    y_pred = model.predict(X_test_scaled)
    acc = accuracy_score(y_test, y_pred)
    rec = recall_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred)
    
    print(f"\nTest Results - Accuracy: {acc:.4f}, Recall: {rec:.4f}, Precision: {prec:.4f}")
    
    # 7. Save the model and scaler
    os.makedirs("saved_models", exist_ok=True)
    joblib.dump(model, "saved_models/fall_detection_rf.joblib")
    joblib.dump(scaler, "saved_models/scaler.joblib")
    
    print("\nModel successfully saved to 'saved_models/'")

if __name__ == "__main__":
    main()
