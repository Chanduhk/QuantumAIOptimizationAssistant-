from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Dedicated directory for public external datasets
DEFAULT_EXTERNAL_DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "external_datasets"

UCI_GARMENT_URL = "https://archive.ics.uci.edu/static/public/597/productivity+prediction+of+garment+employees.zip"
UCI_GARMENT_ID = "uci-garment-productivity"


@dataclass(frozen=True)
class PublicDatasetMetadata:
    """Documented provenance, license, and schema for a public benchmark dataset."""

    dataset_id: str
    name: str
    source_url: str
    license: str
    citation: str
    domain: str
    is_personalized: bool
    target_name: str
    target_semantics: str
    total_records: int
    train_records: int
    val_records: int
    test_records: int
    sha256_checksum: str
    download_timestamp_utc: str
    files: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "name": self.name,
            "source_url": self.source_url,
            "license": self.license,
            "citation": self.citation,
            "domain": self.domain,
            "is_personalized": self.is_personalized,
            "target_name": self.target_name,
            "target_semantics": self.target_semantics,
            "total_records": self.total_records,
            "train_records": self.train_records,
            "val_records": self.val_records,
            "test_records": self.test_records,
            "sha256_checksum": self.sha256_checksum,
            "download_timestamp_utc": self.download_timestamp_utc,
            "files": list(self.files),
        }


class PublicDatasetManager:
    """Manages reproducible downloading, checksum validation, cleaning, and partitioning of public datasets."""

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        self.storage_dir = Path(storage_dir or DEFAULT_EXTERNAL_DATA_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def get_dataset_dir(self, dataset_id: str) -> Path:
        target = self.storage_dir / dataset_id
        target.mkdir(parents=True, exist_ok=True)
        return target

    def is_bootstrapped(self, dataset_id: str = UCI_GARMENT_ID) -> bool:
        ds_dir = self.get_dataset_dir(dataset_id)
        prov_file = ds_dir / "provenance.json"
        train_file = ds_dir / "train.csv"
        val_file = ds_dir / "val.csv"
        test_file = ds_dir / "test.csv"
        return prov_file.exists() and train_file.exists() and val_file.exists() and test_file.exists()

    def get_provenance(self, dataset_id: str = UCI_GARMENT_ID) -> Optional[Dict[str, Any]]:
        prov_file = self.get_dataset_dir(dataset_id) / "provenance.json"
        if not prov_file.exists():
            return None
        try:
            return json.loads(prov_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not read provenance for %s: %s", dataset_id, exc)
            return None

    def bootstrap_uci_garment(self, force: bool = False) -> PublicDatasetMetadata:
        """Download, checksum-verify, clean, and chronologically split the UCI Garment Productivity dataset."""
        ds_dir = self.get_dataset_dir(UCI_GARMENT_ID)
        prov_file = ds_dir / "provenance.json"

        if not force and self.is_bootstrapped(UCI_GARMENT_ID):
            existing_prov = json.loads(prov_file.read_text(encoding="utf-8"))
            return PublicDatasetMetadata(
                dataset_id=existing_prov["dataset_id"],
                name=existing_prov["name"],
                source_url=existing_prov["source_url"],
                license=existing_prov["license"],
                citation=existing_prov["citation"],
                domain=existing_prov["domain"],
                is_personalized=existing_prov["is_personalized"],
                target_name=existing_prov["target_name"],
                target_semantics=existing_prov["target_semantics"],
                total_records=existing_prov["total_records"],
                train_records=existing_prov["train_records"],
                val_records=existing_prov["val_records"],
                test_records=existing_prov["test_records"],
                sha256_checksum=existing_prov["sha256_checksum"],
                download_timestamp_utc=existing_prov["download_timestamp_utc"],
                files=tuple(existing_prov.get("files", [])),
            )

        logger.info("Fetching UCI Garment Productivity dataset from %s", UCI_GARMENT_URL)
        from backend.app.core.resilient_http import ResilientHttpClient
        client = ResilientHttpClient(default_timeout=20.0, max_retries=3)
        try:
            archive_bytes = client.execute_request(UCI_GARMENT_URL)
        except Exception as exc:
            raise RuntimeError(f"Failed to download UCI dataset from {UCI_GARMENT_URL}: {exc}") from exc

        sha256_hash = hashlib.sha256(archive_bytes).hexdigest()
        download_time = datetime.now(timezone.utc).isoformat()

        # Extract CSV from ZIP
        try:
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
                csv_members = [m for m in zf.namelist() if m.endswith(".csv")]
                if not csv_members:
                    raise ValueError("No CSV file found in downloaded ZIP archive.")
                raw_csv_name = csv_members[0]
                with zf.open(raw_csv_name) as f:
                    raw_df = pd.read_csv(f)
        except Exception as exc:
            raise ValueError(f"Failed to extract ZIP archive: {exc}") from exc

        # Data Cleaning and Normalization
        # Attributes: date, quarter, department, day, team, targeted_productivity, smv, wip, over_time, incentive, idle_time, idle_men, no_of_style_change, no_of_workers, actual_productivity
        cleaned_df = raw_df.copy()
        cleaned_df["department"] = cleaned_df["department"].astype(str).str.strip().str.lower()
        cleaned_df["wip"] = pd.to_numeric(cleaned_df["wip"], errors="coerce").fillna(0.0)
        cleaned_df["actual_productivity"] = pd.to_numeric(cleaned_df["actual_productivity"], errors="coerce")
        cleaned_df = cleaned_df.dropna(subset=["actual_productivity", "smv"]).reset_index(drop=True)

        # Parse date chronologically
        cleaned_df["parsed_date"] = pd.to_datetime(cleaned_df["date"], errors="coerce")
        cleaned_df = cleaned_df.sort_values(by="parsed_date").reset_index(drop=True)

        # Prepare standardized features for HELIOX ProductivityModel:
        # hour_of_day: default operational work hour 9-17 based on index/team
        cleaned_df["hour_of_day"] = ((cleaned_df.index % 8) + 9).astype(float)
        # task_type: map garment departments to valid task categories or other
        dept_map = {"sewing": "coding", "finishing": "admin"}
        cleaned_df["task_type"] = cleaned_df["department"].map(lambda d: dept_map.get(d, "other"))
        # duration in minutes (SMV = standard minute value)
        cleaned_df["duration"] = pd.to_numeric(cleaned_df["smv"], errors="coerce").clip(lower=1.0)
        # productivity score scaled to 0-100 range
        cleaned_df["productivity_score"] = np.clip(cleaned_df["actual_productivity"] * 100.0, 0.0, 100.0)

        # Chronological split: 70% Train, 15% Validation, 15% Test
        n_total = len(cleaned_df)
        n_train = int(n_total * 0.70)
        n_val = int(n_total * 0.15)

        train_df = cleaned_df.iloc[:n_train].copy()
        val_df = cleaned_df.iloc[n_train : n_train + n_val].copy()
        test_df = cleaned_df.iloc[n_train + n_val :].copy()

        # Save partitioned files
        raw_path = ds_dir / "raw_garments_worker_productivity.csv"
        train_path = ds_dir / "train.csv"
        val_path = ds_dir / "val.csv"
        test_path = ds_dir / "test.csv"

        raw_df.to_csv(raw_path, index=False)
        train_df.to_csv(train_path, index=False)
        val_df.to_csv(val_path, index=False)
        test_df.to_csv(test_path, index=False)

        metadata = PublicDatasetMetadata(
            dataset_id=UCI_GARMENT_ID,
            name="Productivity Prediction of Garment Employees",
            source_url=UCI_GARMENT_URL,
            license="Creative Commons Attribution 4.0 International (CC BY 4.0)",
            citation="Al-Amin, M., et al. (2020). Productivity Prediction of Garment Employees. UCI Machine Learning Repository.",
            domain="Workplace activity and team productivity benchmarks",
            is_personalized=False,
            target_name="actual_productivity (scaled 0-100 score)",
            target_semantics="objective_workplace_productivity_ratio_scaled_0_100",
            total_records=n_total,
            train_records=len(train_df),
            val_records=len(val_df),
            test_records=len(test_df),
            sha256_checksum=sha256_hash,
            download_timestamp_utc=download_time,
            files=(
                "raw_garments_worker_productivity.csv",
                "train.csv",
                "val.csv",
                "test.csv",
                "provenance.json",
            ),
        )

        tmp_prov = ds_dir / "provenance.json.tmp"
        tmp_prov.write_text(json.dumps(metadata.to_dict(), indent=2), encoding="utf-8")
        try:
            tmp_prov.replace(prov_file)
        except OSError:
            import shutil, time
            for attempt in range(5):
                try:
                    time.sleep(0.05 * (attempt + 1))
                    if prov_file.exists():
                        try:
                            prov_file.unlink()
                        except OSError:
                            pass
                    shutil.move(str(tmp_prov), str(prov_file))
                    break
                except OSError:
                    if attempt == 4:
                        prov_file.write_text(json.dumps(metadata.to_dict(), indent=2), encoding="utf-8")
                        try:
                            tmp_prov.unlink()
                        except OSError:
                            pass
        logger.info("Successfully bootstrapped UCI Garment Productivity dataset (%d records, SHA256: %s)", n_total, sha256_hash[:12])
        return metadata

    def load_productivity_splits(self, dataset_id: str = UCI_GARMENT_ID) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Load train, val, and test partitions tagged with standard schema attributes."""
        if not self.is_bootstrapped(dataset_id):
            self.bootstrap_uci_garment()

        ds_dir = self.get_dataset_dir(dataset_id)
        train_df = pd.read_csv(ds_dir / "train.csv")
        val_df = pd.read_csv(ds_dir / "val.csv")
        test_df = pd.read_csv(ds_dir / "test.csv")

        # Tag attributes required by ProductivityModel contract
        for df in (train_df, val_df, test_df):
            df.attrs["duration_unit"] = "minutes"
            df.attrs["dataset_schema_version"] = "behavior-dataset-v2"
            df.attrs["target_schema_version"] = "heuristic-productivity-v1"
            df.attrs["dataset_provenance"] = dataset_id

        return train_df, val_df, test_df

    def get_compatibility_matrix(self) -> List[Dict[str, Any]]:
        """Return the documented dataset-to-model compatibility matrix required by Section 3."""
        return [
            {
                "dataset_name": "Productivity Prediction of Garment Employees",
                "source": "UCI Machine Learning Repository",
                "official_download_location": UCI_GARMENT_URL,
                "license": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
                "dataset_version": "1.0 (2020)",
                "target_variable": "actual_productivity (scaled 0-100)",
                "target_units": "Percentage / score (0-100)",
                "feature_compatibility": "hour_of_day (work hour 9-17), task_type (dept mapping), duration_hours (SMV in hours)",
                "sample_count": 1197,
                "missing_value_concerns": "wip had 506 missing values imputed to 0.0; zero target NaNs",
                "temporal_structure": "Chronological date sequence (2015-01-01 to 2015-03-11)",
                "known_leakage_risks": "Team serial autocorrelation; mitigated by strictly chronological train/val/test split",
                "model_candidates_supported": "ProductivityModel (RandomForestRegressor)",
                "preprocessing_required": "Trim department strings, convert SMV to duration hours, scale actual_productivity to 0-100",
                "train_validation_test_strategy": "Chronological holdout: 70% Train (837), 15% Val (179), 15% Test (181)",
                "baseline": "Naive chronological training mean predictor (mean = 73.54)",
                "evaluation_metrics": "MAE: 12.63% vs Base 12.37%; RMSE: 16.29% vs Base 15.68%; R2: -0.08",
                "estimated_download_size": "~100 KB (zipped)",
                "status": "ACCEPTED_OFFLINE_STAGING",
                "reason_accepted_or_rejected": (
                    "Accepted as offline public benchmark candidate and domain-adaptation case study. "
                    "Rejected from personal production promotion because candidate fails to beat naive baseline "
                    "on chronological holdout and factory assembly lines do not reflect personal cognitive tasks."
                ),
            },
            {
                "dataset_name": "Combinatorial Task Scheduling Benchmark Suite",
                "source": "HELIOX AI Algorithmic Benchmark Suite",
                "official_download_location": "Local reproducible benchmark generator",
                "license": "Apache 2.0 (Open Source project internal)",
                "dataset_version": "1.0",
                "target_variable": "Feasible schedule, makespan, total weighted tardiness, energy alignment",
                "target_units": "Hour slots (6-22), cumulative reward",
                "feature_compatibility": "Task ID, priority (1-5), duration (hours), deadline hour, dependencies, focus requirement",
                "sample_count": 5,
                "missing_value_concerns": "None (fully specified discrete benchmark problem instances)",
                "temporal_structure": "Discrete 1-day (17 slots: 06:00-23:00) and multi-day planning horizons",
                "known_leakage_risks": "None; isolated test fixtures strictly separated from user personal production history",
                "model_candidates_supported": "RLScheduler (Tabular Q-learning), ClassicalOptimizer, ExactClassicalSolver, QAOAEngine",
                "preprocessing_required": "Duration normalized to float hours, priorities bounded [1, 5]",
                "train_validation_test_strategy": "Multi-seed repeated simulation (seeds: 42, 123, 999; 50-200 episodes)",
                "baseline": "Earliest-Deadline-First (EDF) and Priority-First heuristics",
                "evaluation_metrics": "Completion rate (%), deadline adherence (%), collision count, episode reward, stability across seeds",
                "estimated_download_size": "<10 KB (in-code deterministic generator)",
                "status": "ACCEPTED_BENCHMARK_FIXTURE",
                "reason_accepted_or_rejected": (
                    "Accepted for isolated reinforcement learning and quantum/classical optimization benchmarking. "
                    "Strictly isolated from personal user history."
                ),
            },
            {
                "dataset_name": "Software Project Effort & Duration Dataset (Desharnais)",
                "source": "OpenML (ID 1117) / PROMISE Repository",
                "official_download_location": "https://www.openml.org/d/1117",
                "license": "Public Domain / Open Academic Research (CC0)",
                "dataset_version": "1.0 (1989)",
                "target_variable": "Effort (person-hours)",
                "target_units": "Person-hours",
                "feature_compatibility": "TeamExp, ManagerExp, Length (months), Transactions, Entities, PointsNonAdjust, PointsAjust",
                "sample_count": 81,
                "missing_value_concerns": "4 projects missing values; 77 complete cases",
                "temporal_structure": "Project-level cross-sectional; non-temporal",
                "known_leakage_risks": "Small sample size (N=81) limits statistical generalization",
                "model_candidates_supported": "Macro project effort estimation research",
                "preprocessing_required": "Drop 4 missing projects, log-transform skewed counts, standard scale numeric features",
                "train_validation_test_strategy": "K-fold cross-validation (5 folds)",
                "baseline": "Project mean effort predictor",
                "evaluation_metrics": "MAE, RMSE, MAPE",
                "estimated_download_size": "~15 KB",
                "status": "RESEARCH_REFERENCE_ONLY",
                "reason_accepted_or_rejected": (
                    "Cataloged as academic research baseline. Unsuitable for micro task duration ratio prediction "
                    "because Desharnais models macro multi-month software project effort rather than personal task execution."
                ),
            },
            {
                "dataset_name": "Bank Marketing Dataset",
                "source": "UCI Machine Learning Repository (ID 222)",
                "official_download_location": "https://archive.ics.uci.edu/dataset/222/bank+marketing",
                "license": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
                "dataset_version": "1.0",
                "target_variable": "y (term deposit subscribed: yes/no)",
                "target_units": "Binary class",
                "feature_compatibility": "Incompatible (client demographics, bank contact history, macro indicators)",
                "sample_count": 45211,
                "missing_value_concerns": "Unknown values present in job, education, contact",
                "temporal_structure": "Contact date sequence",
                "known_leakage_risks": "Duration of phone call is target leakage for subscription",
                "model_candidates_supported": "None",
                "preprocessing_required": "N/A",
                "train_validation_test_strategy": "N/A",
                "baseline": "Majority class baseline",
                "evaluation_metrics": "N/A",
                "estimated_download_size": "~5 MB",
                "status": "REJECTED",
                "reason_accepted_or_rejected": "Rejected: Target is bank deposit subscription; completely unrelated to task duration or productivity.",
            },
            {
                "dataset_name": "Human Activity Recognition Using Smartphones (HAR)",
                "source": "UCI Machine Learning Repository (ID 240)",
                "official_download_location": "https://archive.ics.uci.edu/dataset/240/human+activity+recognition+using+smartphones",
                "license": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
                "dataset_version": "1.0",
                "target_variable": "Activity (Walking, Sitting, Standing, Laying, etc.)",
                "target_units": "Discrete physical activity category",
                "feature_compatibility": "Incompatible (561-feature accelerometer and gyroscope signals)",
                "sample_count": 10299,
                "missing_value_concerns": "Zero missing values",
                "temporal_structure": "Time-windowed sliding sensor signals",
                "known_leakage_risks": "Subject overlap across sliding windows",
                "model_candidates_supported": "None",
                "preprocessing_required": "N/A",
                "train_validation_test_strategy": "N/A",
                "baseline": "Majority class baseline",
                "evaluation_metrics": "N/A",
                "estimated_download_size": "~60 MB",
                "status": "REJECTED",
                "reason_accepted_or_rejected": "Rejected: Target is physical body movement classification from accelerometer; zero relevance to cognitive task planning or duration.",
            },
        ]

    def get_dataset_catalog(self) -> List[Dict[str, Any]]:
        """Return the complete dataset catalog with provenance, status, and checksums."""
        catalog = []
        # 1. UCI Garment
        prov = self.get_provenance(UCI_GARMENT_ID)
        if prov:
            catalog.append({
                "dataset_id": UCI_GARMENT_ID,
                "name": prov.get("name", "Productivity Prediction of Garment Employees"),
                "source_url": prov.get("source_url", UCI_GARMENT_URL),
                "license": prov.get("license", "CC BY 4.0"),
                "status": "AVAILABLE_LOCAL_CACHE",
                "is_personalized": False,
                "total_records": prov.get("total_records", 1197),
                "train_records": prov.get("train_records", 837),
                "val_records": prov.get("val_records", 179),
                "test_records": prov.get("test_records", 181),
                "sha256_checksum": prov.get("sha256_checksum", ""),
                "target_name": prov.get("target_name", "actual_productivity (scaled 0-100 score)"),
                "compatible_models": ["ProductivityModel"],
                "promotion_verdict": "OFFLINE_CANDIDATE_STAGING",
            })
        else:
            catalog.append({
                "dataset_id": UCI_GARMENT_ID,
                "name": "Productivity Prediction of Garment Employees",
                "source_url": UCI_GARMENT_URL,
                "license": "CC BY 4.0",
                "status": "REMOTE_DOWNLOADABLE",
                "is_personalized": False,
                "total_records": 1197,
                "compatible_models": ["ProductivityModel"],
                "promotion_verdict": "OFFLINE_CANDIDATE_STAGING",
            })

        # 2. Scheduling Benchmark Scenarios
        catalog.append({
            "dataset_id": "benchmark-task-scheduling-scenarios",
            "name": "Combinatorial Task Scheduling Benchmark Suite",
            "source_url": "internal://benchmark/scheduling/v1",
            "license": "Apache 2.0",
            "status": "DETERMINISTIC_LOCAL_FIXTURE",
            "is_personalized": False,
            "total_records": 5,
            "compatible_models": ["RLScheduler", "ClassicalOptimizer", "ExactClassicalSolver", "QAOAEngine"],
            "promotion_verdict": "BENCHMARK_ONLY",
        })

        # 3. OpenML Desharnais (Research reference)
        catalog.append({
            "dataset_id": "openml-desharnais-software-effort",
            "name": "Software Project Effort & Duration (Desharnais 1117)",
            "source_url": "https://www.openml.org/d/1117",
            "license": "Public Domain (CC0)",
            "status": "RESEARCH_CATALOG_REFERENCE",
            "is_personalized": False,
            "total_records": 81,
            "compatible_models": [],
            "promotion_verdict": "UNSUITABLE_FOR_PERSONAL_DURATION",
        })

        return catalog

    def get_scheduling_benchmark_scenarios(self) -> Dict[str, Dict[str, Any]]:
        """Return canonical combinatorial scheduling benchmark scenarios for controlled evaluation."""
        return {
            "scenario_light_load": {
                "name": "Light Load Scenario",
                "description": "4 non-conflicting tasks within a single workday with clear priority differentiation.",
                "available_hours": list(range(9, 18)),  # 9:00 to 17:00
                "is_mathematically_feasible": True,
                "total_demanded_hours": 5.0,
                "horizon_hours": 9.0,
                "behavior_patterns": {
                    "average_productivity": 75.0,
                    "average_energy_level": 80.0,
                    "best_focus_hours": [9, 10, 11],
                    "preferred_task_types": ["coding", "research"],
                    "hourly_productivity": {9: 85.0, 10: 90.0, 11: 88.0, 14: 75.0, 15: 70.0, 16: 65.0},
                },
                "tasks": [
                    {
                        "task_id": "T1",
                        "title": "Core Algorithm Implementation",
                        "task_type": "coding",
                        "priority": 5,
                        "estimated_duration": 2.0,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 90.0,
                        "deadline_hour": 14,
                    },
                    {
                        "task_id": "T2",
                        "title": "Quantum QUBO Specification",
                        "task_type": "research",
                        "priority": 4,
                        "estimated_duration": 1.5,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 85.0,
                        "deadline_hour": 16,
                    },
                    {
                        "task_id": "T3",
                        "title": "Documentation & Review",
                        "task_type": "writing",
                        "priority": 3,
                        "estimated_duration": 1.0,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 70.0,
                        "deadline_hour": 17,
                    },
                    {
                        "task_id": "T4",
                        "title": "Sprint Sync Meeting",
                        "task_type": "meeting",
                        "priority": 2,
                        "estimated_duration": 0.5,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 60.0,
                        "deadline_hour": 18,
                    },
                ],
            },
            "scenario_deadline_pressure": {
                "name": "Tight Deadline Pressure Scenario",
                "description": "5 urgent tasks competing for early morning focus hours with strict deadlines.",
                "available_hours": list(range(8, 18)),
                "is_mathematically_feasible": True,
                "total_demanded_hours": 6.5,
                "horizon_hours": 10.0,
                "behavior_patterns": {
                    "average_productivity": 70.0,
                    "average_energy_level": 75.0,
                    "best_focus_hours": [9, 10, 14],
                    "preferred_task_types": ["coding"],
                    "hourly_productivity": {8: 60.0, 9: 85.0, 10: 88.0, 11: 75.0, 13: 65.0, 14: 80.0, 15: 70.0},
                },
                "tasks": [
                    {
                        "task_id": "T1",
                        "title": "Critical Hotfix Deployment",
                        "task_type": "coding",
                        "priority": 5,
                        "estimated_duration": 1.0,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 88.0,
                        "deadline_hour": 10,
                    },
                    {
                        "task_id": "T2",
                        "title": "Security Vulnerability Patch",
                        "task_type": "coding",
                        "priority": 5,
                        "estimated_duration": 1.5,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 85.0,
                        "deadline_hour": 12,
                    },
                    {
                        "task_id": "T3",
                        "title": "Stakeholder Status Briefing",
                        "task_type": "meeting",
                        "priority": 4,
                        "estimated_duration": 1.0,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 75.0,
                        "deadline_hour": 13,
                    },
                    {
                        "task_id": "T4",
                        "title": "System Regression Testing",
                        "task_type": "research",
                        "priority": 3,
                        "estimated_duration": 2.0,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 70.0,
                        "deadline_hour": 16,
                    },
                    {
                        "task_id": "T5",
                        "title": "Backlog Grooming",
                        "task_type": "admin",
                        "priority": 2,
                        "estimated_duration": 1.0,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 60.0,
                        "deadline_hour": 17,
                    },
                ],
            },
            "scenario_heavy_conflict": {
                "name": "Overloaded Infeasibility Stress Test (12h Demanded / 8h Horizon)",
                "description": "8 mandatory sequential tasks demanding 12 total hours within an 8-hour workday [9:00-17:00). Strictly mathematically infeasible for collision-free single-resource execution. Used as an explicit infeasibility stress test to verify policy behavior under overloaded conditions.",
                "available_hours": list(range(9, 17)),
                "is_mathematically_feasible": False,
                "total_demanded_hours": 12.0,
                "horizon_hours": 8.0,
                "behavior_patterns": {
                    "average_productivity": 65.0,
                    "average_energy_level": 70.0,
                    "best_focus_hours": [9, 10, 11],
                    "preferred_task_types": ["coding", "research"],
                    "hourly_productivity": {9: 80.0, 10: 85.0, 11: 82.0, 13: 65.0, 14: 70.0, 15: 65.0, 16: 55.0},
                },
                "tasks": [
                    {
                        "task_id": "T1",
                        "title": "Architecture Redesign",
                        "task_type": "research",
                        "priority": 5,
                        "estimated_duration": 2.0,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 85.0,
                        "deadline_hour": 13,
                    },
                    {
                        "task_id": "T2",
                        "title": "Feature Refactoring",
                        "task_type": "coding",
                        "priority": 4,
                        "estimated_duration": 2.5,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 80.0,
                        "deadline_hour": 15,
                    },
                    {
                        "task_id": "T3",
                        "title": "Team Technical Discussion",
                        "task_type": "meeting",
                        "priority": 3,
                        "estimated_duration": 1.0,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 70.0,
                        "deadline_hour": 14,
                    },
                    {
                        "task_id": "T4",
                        "title": "Code Review Pipeline",
                        "task_type": "coding",
                        "priority": 4,
                        "estimated_duration": 1.5,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 75.0,
                        "deadline_hour": 16,
                    },
                    {
                        "task_id": "T5",
                        "title": "API Documentation",
                        "task_type": "writing",
                        "priority": 2,
                        "estimated_duration": 1.5,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 60.0,
                        "deadline_hour": 17,
                    },
                    {
                        "task_id": "T6",
                        "title": "Database Maintenance",
                        "task_type": "admin",
                        "priority": 3,
                        "estimated_duration": 1.0,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 65.0,
                        "deadline_hour": 17,
                    },
                    {
                        "task_id": "T7",
                        "title": "Incident Retrospective",
                        "task_type": "meeting",
                        "priority": 4,
                        "estimated_duration": 1.0,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 70.0,
                        "deadline_hour": 16,
                    },
                    {
                        "task_id": "T8",
                        "title": "Ad-hoc User Support",
                        "task_type": "admin",
                        "priority": 1,
                        "estimated_duration": 1.5,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 50.0,
                        "deadline_hour": 17,
                    },
                ],
            },
            "scenario_high_load_feasible": {
                "name": "High Load Feasible Workday Scenario",
                "description": "6 non-conflicting tasks demanding 7.5 total hours within an 8-hour workday [9:00-17:00). Mathematically feasible high-load schedule test.",
                "available_hours": list(range(9, 17)),
                "is_mathematically_feasible": True,
                "total_demanded_hours": 7.5,
                "horizon_hours": 8.0,
                "behavior_patterns": {
                    "average_productivity": 70.0,
                    "average_energy_level": 75.0,
                    "best_focus_hours": [9, 10, 11],
                    "preferred_task_types": ["coding", "research"],
                    "hourly_productivity": {9: 85.0, 10: 90.0, 11: 85.0, 13: 70.0, 14: 75.0, 15: 70.0, 16: 60.0},
                },
                "tasks": [
                    {
                        "task_id": "T1",
                        "title": "Architecture Spike",
                        "task_type": "coding",
                        "priority": 5,
                        "estimated_duration": 2.0,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 85.0,
                        "deadline_hour": 12,
                    },
                    {
                        "task_id": "T2",
                        "title": "Client Demo Prep",
                        "task_type": "research",
                        "priority": 4,
                        "estimated_duration": 1.5,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 80.0,
                        "deadline_hour": 14,
                    },
                    {
                        "task_id": "T3",
                        "title": "Team Sync",
                        "task_type": "meeting",
                        "priority": 3,
                        "estimated_duration": 1.0,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 70.0,
                        "deadline_hour": 12,
                    },
                    {
                        "task_id": "T4",
                        "title": "Bug Triage",
                        "task_type": "admin",
                        "priority": 3,
                        "estimated_duration": 0.5,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 65.0,
                        "deadline_hour": 15,
                    },
                    {
                        "task_id": "T5",
                        "title": "Code Review",
                        "task_type": "coding",
                        "priority": 4,
                        "estimated_duration": 1.0,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 75.0,
                        "deadline_hour": 16,
                    },
                    {
                        "task_id": "T6",
                        "title": "Release Documentation",
                        "task_type": "writing",
                        "priority": 2,
                        "estimated_duration": 1.5,
                        "estimated_duration_unit": "hours",
                        "estimated_duration_source": "benchmark",
                        "predicted_productivity": 60.0,
                        "deadline_hour": 17,
                    },
                ],
            },
        }

