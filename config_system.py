"""
Structured Configuration System for Quantum Life AI

Centralizes all configuration parameters across all 6 stages.
Supports loading/saving configurations, presets, and runtime modifications.

Key Features:
  - Unified configuration schema (all parameters in one place)
  - Multiple configuration presets (conservative, balanced, aggressive)
  - Load/save from JSON files
  - Runtime validation
  - Configuration history tracking
  - Per-stage configuration access
  - Environment-based config selection
"""

from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
from datetime import datetime
from enum import Enum


class ConfigProfile(Enum):
    """Predefined configuration profiles."""
    CONSERVATIVE = "conservative"  # Safe, reliable, lower scores
    BALANCED = "balanced"          # Mix of quality and reliability
    AGGRESSIVE = "aggressive"      # Maximize quality, take risks
    EXPERIMENTAL = "experimental"  # Try new approaches


@dataclass
class GAConfig:
    """Genetic Algorithm Configuration (Stage 1)."""
    
    population_size: int = 20           # Number of schedules per generation
    generations: int = 40               # Evolution cycles
    mutation_rate: float = 0.15         # Per-gene mutation probability
    crossover_rate: float = 0.7         # Crossover probability
    elite_size: int = 2                 # Top schedules preserved
    tournament_size: int = 3            # Tournament selection size
    
    def validate(self) -> List[str]:
        """Return validation errors, if any."""
        errors = []
        if self.population_size < 5:
            errors.append("GA: population_size must be >= 5")
        if self.generations < 1:
            errors.append("GA: generations must be >= 1")
        if not (0 < self.mutation_rate < 1):
            errors.append("GA: mutation_rate must be between 0 and 1")
        if not (0 < self.crossover_rate < 1):
            errors.append("GA: crossover_rate must be between 0 and 1")
        if self.elite_size >= self.population_size:
            errors.append("GA: elite_size must be < population_size")
        return errors


@dataclass
class MCLConfig:
    """Multi-Candidate Lookahead Configuration (Stage 2)."""
    
    num_candidates: int = 3             # Number of diverse candidates
    lookahead_days: int = 2             # Days to simulate ahead
    weight_quality: float = 0.5          # Weight for schedule quality
    weight_stability: float = 0.5        # Weight for stability metric
    
    def validate(self) -> List[str]:
        errors = []
        if self.num_candidates < 1:
            errors.append("MCL: num_candidates must be >= 1")
        if self.lookahead_days < 1:
            errors.append("MCL: lookahead_days must be >= 1")
        total_weight = self.weight_quality + self.weight_stability
        if abs(total_weight - 1.0) > 0.01:
            errors.append("MCL: quality and stability weights must sum to ~1.0")
        return errors


@dataclass
class DeferralConfig:
    """Strategic Deferral Configuration (Stage 3)."""
    
    overload_threshold: float = 2.0     # When to start deferring (2.0 = 200% load)
    deferral_reduction: float = 0.7     # Reduce urgency to this level (70%)
    fairness_window: int = 3            # Days before re-enabling deferred
    max_deferrals_per_task: int = 2     # Max consecutive deferrals
    deferral_count_target: int = 2      # Typical number to defer
    
    def validate(self) -> List[str]:
        errors = []
        if self.overload_threshold < 1.0:
            errors.append("Deferral: overload_threshold must be >= 1.0")
        if not (0 < self.deferral_reduction < 1):
            errors.append("Deferral: deferral_reduction must be between 0 and 1")
        if self.fairness_window < 1:
            errors.append("Deferral: fairness_window must be >= 1")
        if self.max_deferrals_per_task < 1:
            errors.append("Deferral: max_deferrals_per_task must be >= 1")
        return errors


@dataclass
class FatigueConfig:
    """Fatigue-Based Capacity Configuration (Stage 4)."""
    
    original_capacity: float = 8.0      # Baseline daily capacity (hours)
    poor_score_threshold: float = 0.4   # Reduce if score < this
    good_score_threshold: float = 0.75  # Restore if score > this
    min_capacity: float = 4.0           # Minimum capacity floor
    max_capacity: float = 10.0          # Maximum capacity ceiling
    reduction_factor: float = 0.2       # Reduce by 20% per poor day
    recovery_factor: float = 0.05       # Restore by 5% per good day
    
    def validate(self) -> List[str]:
        errors = []
        if self.original_capacity <= 0:
            errors.append("Fatigue: original_capacity must be > 0")
        if not (0 < self.poor_score_threshold < 1):
            errors.append("Fatigue: poor_score_threshold must be between 0 and 1")
        if not (0 < self.good_score_threshold < 1):
            errors.append("Fatigue: good_score_threshold must be between 0 and 1")
        if self.poor_score_threshold >= self.good_score_threshold:
            errors.append("Fatigue: poor_threshold must be < good_threshold")
        if self.min_capacity <= 0 or self.max_capacity <= 0:
            errors.append("Fatigue: capacities must be > 0")
        if self.min_capacity >= self.max_capacity:
            errors.append("Fatigue: min_capacity must be < max_capacity")
        if not (0 < self.reduction_factor < 1):
            errors.append("Fatigue: reduction_factor must be between 0 and 1")
        if not (0 < self.recovery_factor < 1):
            errors.append("Fatigue: recovery_factor must be between 0 and 1")
        return errors


@dataclass
class LearningConfig:
    """Variance Minimization (Learning) Configuration (Stage 5)."""
    
    variance_window_size: int = 5       # Days of scores to collect
    target_variance: float = 0.02       # Target variance threshold
    learning_rate: float = 0.08         # Adjustment magnitude (8%)
    convergence_threshold: float = 0.0001  # Variance improvement threshold
    min_iterations_for_convergence: int = 2  # Iterations to declare convergence
    
    def validate(self) -> List[str]:
        errors = []
        if self.variance_window_size < 3:
            errors.append("Learning: variance_window_size must be >= 3")
        if self.target_variance <= 0:
            errors.append("Learning: target_variance must be > 0")
        if not (0 < self.learning_rate < 1):
            errors.append("Learning: learning_rate must be between 0 and 1")
        if self.convergence_threshold <= 0:
            errors.append("Learning: convergence_threshold must be > 0")
        return errors


@dataclass
class UncertaintyConfig:
    """Stochastic Uncertainty Configuration (Stage 6)."""
    
    num_simulations: int = 500          # Monte Carlo trials per day
    duration_std_dev: float = 0.3       # Task duration σ (as fraction of mean)
    interruption_probability: float = 0.05  # 5% chance per task
    failure_probability: float = 0.02   # 2% chance per task
    failure_threshold: float = 0.30     # Score < this is failure
    penalty_magnitude: float = 0.2      # Max 20% penalty for high risk
    
    def validate(self) -> List[str]:
        errors = []
        if self.num_simulations < 50:
            errors.append("Uncertainty: num_simulations must be >= 50")
        if self.duration_std_dev <= 0:
            errors.append("Uncertainty: duration_std_dev must be > 0")
        if not (0 <= self.interruption_probability < 1):
            errors.append("Uncertainty: interruption_probability must be [0, 1)")
        if not (0 <= self.failure_probability < 1):
            errors.append("Uncertainty: failure_probability must be [0, 1)")
        if self.interruption_probability + self.failure_probability >= 1:
            errors.append("Uncertainty: combined probabilities must be < 1")
        if not (0 < self.failure_threshold < 1):
            errors.append("Uncertainty: failure_threshold must be between 0 and 1")
        if not (0 < self.penalty_magnitude < 1):
            errors.append("Uncertainty: penalty_magnitude must be between 0 and 1")
        return errors


@dataclass
class ForecastConfig:
    """Overall Forecast Configuration."""
    
    num_days: int = 5                   # Days to forecast
    risk_weight: float = 0.2            # Future risk penalty weight
    risk_weight_decay: float = 0.85     # Decrease rate under stress
    shock_probability: float = 0.2      # Probability of task injection
    
    def validate(self) -> List[str]:
        errors = []
        if self.num_days < 1:
            errors.append("Forecast: num_days must be >= 1")
        if not (0 < self.risk_weight < 1):
            errors.append("Forecast: risk_weight must be between 0 and 1")
        if not (0 < self.risk_weight_decay < 1):
            errors.append("Forecast: risk_weight_decay must be between 0 and 1")
        if not (0 <= self.shock_probability <= 1):
            errors.append("Forecast: shock_probability must be in [0, 1]")
        return errors


@dataclass
class SystemConfig:
    """Complete system configuration (all stages)."""
    
    # Stage configurations
    ga: GAConfig = field(default_factory=GAConfig)
    mcl: MCLConfig = field(default_factory=MCLConfig)
    deferral: DeferralConfig = field(default_factory=DeferralConfig)
    fatigue: FatigueConfig = field(default_factory=FatigueConfig)
    learning: LearningConfig = field(default_factory=LearningConfig)
    uncertainty: UncertaintyConfig = field(default_factory=UncertaintyConfig)
    forecast: ForecastConfig = field(default_factory=ForecastConfig)
    
    # Metadata
    name: str = "default"
    description: str = ""
    version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def validate(self) -> Dict[str, List[str]]:
        """Validate all configurations."""
        errors = {}
        
        # Validate each stage
        ga_errors = self.ga.validate()
        if ga_errors:
            errors["ga"] = ga_errors
        
        mcl_errors = self.mcl.validate()
        if mcl_errors:
            errors["mcl"] = mcl_errors
        
        deferral_errors = self.deferral.validate()
        if deferral_errors:
            errors["deferral"] = deferral_errors
        
        fatigue_errors = self.fatigue.validate()
        if fatigue_errors:
            errors["fatigue"] = fatigue_errors
        
        learning_errors = self.learning.validate()
        if learning_errors:
            errors["learning"] = learning_errors
        
        uncertainty_errors = self.uncertainty.validate()
        if uncertainty_errors:
            errors["uncertainty"] = uncertainty_errors
        
        forecast_errors = self.forecast.validate()
        if forecast_errors:
            errors["forecast"] = forecast_errors
        
        return errors
    
    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return len(self.validate()) == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "ga": asdict(self.ga),
            "mcl": asdict(self.mcl),
            "deferral": asdict(self.deferral),
            "fatigue": asdict(self.fatigue),
            "learning": asdict(self.learning),
            "uncertainty": asdict(self.uncertainty),
            "forecast": asdict(self.forecast),
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "SystemConfig":
        """Create config from dictionary."""
        return SystemConfig(
            name=data.get("name", "default"),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            modified_at=data.get("modified_at", datetime.now().isoformat()),
            ga=GAConfig(**data.get("ga", {})),
            mcl=MCLConfig(**data.get("mcl", {})),
            deferral=DeferralConfig(**data.get("deferral", {})),
            fatigue=FatigueConfig(**data.get("fatigue", {})),
            learning=LearningConfig(**data.get("learning", {})),
            uncertainty=UncertaintyConfig(**data.get("uncertainty", {})),
            forecast=ForecastConfig(**data.get("forecast", {})),
        )


class ConfigManager:
    """
    Manages system configuration lifecycle.
    
    Handles:
      - Loading/saving configurations
      - Configuration presets
      - Runtime configuration updates
      - Configuration validation
      - Configuration history
    """
    
    def __init__(self, config_dir: Path = None):
        """
        Initialize config manager.
        
        Args:
            config_dir: Directory for storing configs (default: ./configs)
        """
        self.config_dir = config_dir or Path("configs")
        self.config_dir.mkdir(exist_ok=True)
        
        self.current_config = SystemConfig()
        self.config_history: List[SystemConfig] = []
        self.max_history = 10
    
    def get_default_config(self) -> SystemConfig:
        """Get default balanced configuration."""
        return SystemConfig(
            name="balanced",
            description="Balanced configuration for typical use"
        )
    
    def get_conservative_config(self) -> SystemConfig:
        """Get conservative configuration (safe, reliable)."""
        config = SystemConfig(
            name="conservative",
            description="Conservative: prioritize reliability over quality"
        )
        
        # Reduce ambitions
        config.ga.population_size = 15
        config.ga.generations = 30
        
        # Be more selective with candidates
        config.mcl.num_candidates = 2
        
        # Defer more aggressively
        config.deferral.overload_threshold = 1.5
        config.deferral.deferral_count_target = 3
        
        # More cautious fatigue threshold
        config.fatigue.poor_score_threshold = 0.5
        config.fatigue.reduction_factor = 0.25
        
        # More conservative learning
        config.learning.learning_rate = 0.05
        
        # Stricter uncertainty penalties
        config.uncertainty.penalty_magnitude = 0.3
        
        return config
    
    def get_aggressive_config(self) -> SystemConfig:
        """Get aggressive configuration (quality-focused, risk-taking)."""
        config = SystemConfig(
            name="aggressive",
            description="Aggressive: maximize quality, accept risks"
        )
        
        # More evolutionary power
        config.ga.population_size = 30
        config.ga.generations = 60
        
        # More candidates to choose from
        config.mcl.num_candidates = 5
        
        # Defer less often
        config.deferral.overload_threshold = 3.0
        config.deferral.deferral_count_target = 1
        
        # More aggressive fatigue adjustment
        config.fatigue.poor_score_threshold = 0.3
        config.fatigue.reduction_factor = 0.15
        config.fatigue.recovery_factor = 0.08
        
        # Faster learning
        config.learning.learning_rate = 0.12
        
        # More tolerant of uncertainty
        config.uncertainty.penalty_magnitude = 0.1
        config.uncertainty.num_simulations = 300
        
        return config
    
    def get_experimental_config(self) -> SystemConfig:
        """Get experimental configuration (try new approaches)."""
        config = SystemConfig(
            name="experimental",
            description="Experimental: test novel approaches"
        )
        
        # Maximum GA resources
        config.ga.population_size = 50
        config.ga.generations = 80
        config.ga.mutation_rate = 0.25  # Higher mutation
        
        # Extensive lookahead
        config.mcl.num_candidates = 8
        config.mcl.lookahead_days = 3
        
        # Intelligent deferral
        config.deferral.overload_threshold = 2.5
        
        # Adaptive fatigue
        config.fatigue.original_capacity = 10.0
        config.fatigue.max_capacity = 12.0
        
        # Aggressive learning
        config.learning.learning_rate = 0.15
        config.learning.convergence_threshold = 0.00001
        
        # Maximum uncertainty detail
        config.uncertainty.num_simulations = 1000
        
        return config
    
    def load_preset(self, profile: ConfigProfile) -> SystemConfig:
        """
        Load a preset configuration.
        
        Args:
            profile: ConfigProfile enum value
            
        Returns:
            Loaded SystemConfig
        """
        if profile == ConfigProfile.CONSERVATIVE:
            config = self.get_conservative_config()
        elif profile == ConfigProfile.AGGRESSIVE:
            config = self.get_aggressive_config()
        elif profile == ConfigProfile.EXPERIMENTAL:
            config = self.get_experimental_config()
        else:  # BALANCED
            config = self.get_default_config()
        
        self.set_current_config(config)
        return config
    
    def load_from_file(self, filename: str) -> SystemConfig:
        """
        Load configuration from JSON file.
        
        Args:
            filename: Name of config file (in configs directory)
            
        Returns:
            Loaded SystemConfig
        """
        filepath = self.config_dir / f"{filename}.json"
        
        if not filepath.exists():
            raise FileNotFoundError(f"Config file not found: {filepath}")
        
        with open(filepath, "r") as f:
            data = json.load(f)
        
        config = SystemConfig.from_dict(data)
        self.set_current_config(config)
        return config
    
    def save_to_file(self, config: SystemConfig = None, filename: str = None) -> Path:
        """
        Save configuration to JSON file.
        
        Args:
            config: Config to save (default: current config)
            filename: Output filename (default: config name)
            
        Returns:
            Path to saved file
        """
        config = config or self.current_config
        filename = filename or config.name
        
        filepath = self.config_dir / f"{filename}.json"
        
        with open(filepath, "w") as f:
            json.dump(config.to_dict(), f, indent=2)
        
        return filepath
    
    def set_current_config(self, config: SystemConfig) -> None:
        """
        Set current configuration and track history.
        
        Args:
            config: SystemConfig to activate
        """
        # Validate before setting
        errors = config.validate()
        if errors:
            error_msg = "\n".join(
                f"{stage}: {', '.join(msgs)}"
                for stage, msgs in errors.items()
            )
            raise ValueError(f"Invalid configuration:\n{error_msg}")
        
        # Add to history
        self.config_history.append(self.current_config)
        if len(self.config_history) > self.max_history:
            self.config_history.pop(0)
        
        # Set current
        config.modified_at = datetime.now().isoformat()
        self.current_config = config
    
    def update_parameter(self, stage: str, param: str, value: Any) -> None:
        """
        Update a single parameter at runtime.
        
        Args:
            stage: Stage name (ga, mcl, deferral, fatigue, learning, uncertainty)
            param: Parameter name
            value: New value
            
        Raises:
            ValueError: If invalid stage/parameter
        """
        stage_map = {
            "ga": self.current_config.ga,
            "mcl": self.current_config.mcl,
            "deferral": self.current_config.deferral,
            "fatigue": self.current_config.fatigue,
            "learning": self.current_config.learning,
            "uncertainty": self.current_config.uncertainty,
            "forecast": self.current_config.forecast,
        }
        
        if stage not in stage_map:
            raise ValueError(f"Unknown stage: {stage}")
        
        stage_config = stage_map[stage]
        if not hasattr(stage_config, param):
            raise ValueError(f"Unknown parameter: {stage}.{param}")
        
        # Set value
        setattr(stage_config, param, value)
        
        # Re-validate entire config
        errors = self.current_config.validate()
        if errors:
            # Revert on validation failure
            raise ValueError(f"Invalid parameter update: {errors}")
        
        self.current_config.modified_at = datetime.now().isoformat()
    
    def get_report(self) -> str:
        """Generate human-readable configuration report."""
        config = self.current_config
        errors = config.validate()
        
        report = f"""
CONFIGURATION REPORT
════════════════════════════════════════════════════════

Configuration: {config.name}
Description:  {config.description}
Version:      {config.version}
Modified:     {config.modified_at}

Validation: {'✅ VALID' if not errors else '❌ INVALID'}
"""
        
        if errors:
            report += "\nErrors:\n"
            for stage, err_list in errors.items():
                for err in err_list:
                    report += f"  - {err}\n"
        
        report += f"""
STAGE 1: Genetic Algorithm
  Population Size:     {config.ga.population_size}
  Generations:         {config.ga.generations}
  Mutation Rate:       {config.ga.mutation_rate:.1%}
  Crossover Rate:      {config.ga.crossover_rate:.1%}
  Elite Size:          {config.ga.elite_size}

STAGE 2: Multi-Candidate Lookahead
  Num Candidates:      {config.mcl.num_candidates}
  Lookahead Days:      {config.mcl.lookahead_days}
  Quality Weight:      {config.mcl.weight_quality:.1%}
  Stability Weight:    {config.mcl.weight_stability:.1%}

STAGE 3: Strategic Deferral
  Overload Threshold:  {config.deferral.overload_threshold:.1f}x
  Deferral Reduction:  {config.deferral.deferral_reduction:.1%}
  Fairness Window:     {config.deferral.fairness_window} days
  Max Deferrals:       {config.deferral.max_deferrals_per_task}
  Target Deferrals:    {config.deferral.deferral_count_target}

STAGE 4: Fatigue-Based Capacity
  Original Capacity:   {config.fatigue.original_capacity:.1f}h
  Min Capacity:        {config.fatigue.min_capacity:.1f}h
  Max Capacity:        {config.fatigue.max_capacity:.1f}h
  Poor Threshold:      {config.fatigue.poor_score_threshold:.2f}
  Good Threshold:      {config.fatigue.good_score_threshold:.2f}
  Reduction Factor:    {config.fatigue.reduction_factor:.1%}
  Recovery Factor:     {config.fatigue.recovery_factor:.1%}

STAGE 5: Variance Minimization (Learning)
  Window Size:         {config.learning.variance_window_size} days
  Target Variance:     {config.learning.target_variance:.4f}
  Learning Rate:       {config.learning.learning_rate:.1%}
  Convergence Threshold: {config.learning.convergence_threshold:.6f}

STAGE 6: Stochastic Uncertainty
  Num Simulations:     {config.uncertainty.num_simulations}
  Duration Std Dev:    {config.uncertainty.duration_std_dev:.2f}
  Interruption Prob:   {config.uncertainty.interruption_probability:.1%}
  Failure Prob:        {config.uncertainty.failure_probability:.1%}
  Failure Threshold:   {config.uncertainty.failure_threshold:.2f}
  Penalty Magnitude:   {config.uncertainty.penalty_magnitude:.1%}

FORECAST Configuration
  Num Days:            {config.forecast.num_days}
  Risk Weight:         {config.forecast.risk_weight:.1%}
  Risk Weight Decay:   {config.forecast.risk_weight_decay:.1%}
  Shock Probability:   {config.forecast.shock_probability:.1%}
"""
        
        return report
    
    def compare_configs(self, config1: SystemConfig, config2: SystemConfig) -> str:
        """Generate comparison between two configurations."""
        dict1 = config1.to_dict()
        dict2 = config2.to_dict()
        
        report = f"""
CONFIGURATION COMPARISON
════════════════════════════════════════════════════════

Config 1: {config1.name}
Config 2: {config2.name}

"""
        
        def compare_dicts(d1, d2, prefix=""):
            lines = []
            all_keys = set(list(d1.keys()) + list(d2.keys()))
            
            for key in sorted(all_keys):
                if key in ["created_at", "modified_at"]:
                    continue
                
                v1 = d1.get(key)
                v2 = d2.get(key)
                
                if isinstance(v1, dict) and isinstance(v2, dict):
                    lines.extend(compare_dicts(v1, v2, f"{prefix}{key}."))
                elif v1 != v2:
                    full_key = f"{prefix}{key}"
                    lines.append(f"  {full_key}:")
                    lines.append(f"    Config 1: {v1}")
                    lines.append(f"    Config 2: {v2}")
            
            return lines
        
        diff_lines = compare_dicts(dict1, dict2)
        
        if diff_lines:
            report += "Differences:\n"
            report += "\n".join(diff_lines)
        else:
            report += "Configurations are identical"
        
        return report
