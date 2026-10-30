import json
import hashlib
import numpy as np
import pandas as pd
from pathlib import Path
from backend.app.ai_models.productivity_model import ProductivityModel

ds_dir = Path("data/external_datasets/uci-garment-productivity")
prov_file = ds_dir / "provenance.json"
artifact_file = Path("data/model_artifacts/productivity_benchmark_candidate_uci-garment-productivity.joblib")

print("=== 1. DATASET PROVENANCE ===")
if prov_file.exists():
    with open(prov_file, "r") as f:
        prov = json.load(f)
    print("Dataset Name:", prov.get("name"))
    print("Dataset ID:", prov.get("dataset_id"))
    print("SHA256:", prov.get("sha256_checksum"))
    print("Total records:", prov.get("total_records"))
    print("Train / Val / Test records:", prov.get("train_records"), prov.get("val_records"), prov.get("test_records"))
    print("Target name:", prov.get("target_name"))
    print("Target semantics:", prov.get("target_semantics"))
else:
    print("Provenance file does not exist!")

print("\n=== 2. MODEL ARTIFACT ===")
if artifact_file.exists():
    with open(artifact_file, "rb") as f:
        artifact_hash = hashlib.sha256(f.read()).hexdigest()
    print("Artifact Path:", artifact_file)
    print("Artifact SHA256:", artifact_hash)
else:
    print("Artifact file does not exist!")

train_df = pd.read_csv(ds_dir / "train.csv")
val_df = pd.read_csv(ds_dir / "val.csv")
test_df = pd.read_csv(ds_dir / "test.csv")

print("\n=== 3. EVALUATION ON STORED VALIDATION SET ===")
model = ProductivityModel(model_path=str(artifact_file))

# Predictions on 0-100 scale
val_preds_100 = []
for _, row in val_df.iterrows():
    # smv is duration in minutes -> convert to hours for predict()
    p = model.predict(hour=int(row["hour_of_day"]), task_type=str(row["task_type"]), duration=float(row["duration"]) / 60.0)
    val_preds_100.append(p)
val_preds_100 = np.array(val_preds_100)

y_val_100 = val_df["productivity_score"].to_numpy(dtype=float)
y_val_raw = val_df["actual_productivity"].to_numpy(dtype=float)
val_preds_raw = val_preds_100 / 100.0

# 0-100 scale metrics
errors_100 = val_preds_100 - y_val_100
mae_100 = float(np.mean(np.abs(errors_100)))
rmse_100 = float(np.sqrt(np.mean(errors_100**2)))
ss_tot_100 = float(np.sum((y_val_100 - np.mean(y_val_100))**2))
r2_100 = float(1.0 - (np.sum(errors_100**2) / ss_tot_100))

# Baseline (training mean) on 0-100 scale
train_mean_100 = float(np.mean(train_df["productivity_score"]))
base_err_100 = train_mean_100 - y_val_100
base_mae_100 = float(np.mean(np.abs(base_err_100)))
base_rmse_100 = float(np.sqrt(np.mean(base_err_100**2)))
base_r2_100 = float(1.0 - (np.sum(base_err_100**2) / ss_tot_100))

print("--- Scale: 0 to 100 (percentage score) ---")
print(f"Candidate Model: MAE = {mae_100:.4f}, RMSE = {rmse_100:.4f}, R2 = {r2_100:.4f}")
print(f"Naive Baseline:   MAE = {base_mae_100:.4f}, RMSE = {base_rmse_100:.4f}, R2 = {base_r2_100:.4f}")
print(f"Beats baseline on MAE? {mae_100 < base_mae_100}")
print(f"Beats baseline on RMSE? {rmse_100 < base_rmse_100}")

# 0-1 raw scale metrics
errors_raw = val_preds_raw - y_val_raw
mae_raw = float(np.mean(np.abs(errors_raw)))
rmse_raw = float(np.sqrt(np.mean(errors_raw**2)))
ss_tot_raw = float(np.sum((y_val_raw - np.mean(y_val_raw))**2))
r2_raw = float(1.0 - (np.sum(errors_raw**2) / ss_tot_raw))

train_mean_raw = float(np.mean(train_df["actual_productivity"]))
base_err_raw = train_mean_raw - y_val_raw
base_mae_raw = float(np.mean(np.abs(base_err_raw)))
base_rmse_raw = float(np.sqrt(np.mean(base_err_raw**2)))

print("\n--- Scale: 0.0 to 1.0 (raw actual_productivity ratio) ---")
print(f"Candidate Model: MAE = {mae_raw:.4f}, RMSE = {rmse_raw:.4f}, R2 = {r2_raw:.4f}")
print(f"Naive Baseline:   MAE = {base_mae_raw:.4f}, RMSE = {base_rmse_raw:.4f}")

print("\n=== 4. MODEL METADATA FROM SAVED ARTIFACT ===")
print("Model metadata in artifact:", model.metadata)
