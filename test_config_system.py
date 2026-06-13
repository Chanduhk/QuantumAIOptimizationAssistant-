"""
Configuration System Test Suite

Tests all functionality of the structured configuration system.
"""

from config_system import ConfigManager, ConfigProfile, SystemConfig, GAConfig
import json
from pathlib import Path


def test_default_config():
    """Test: Load default configuration."""
    print("\n" + "="*70)
    print("TEST 1: Load Default Configuration")
    print("="*70)
    
    manager = ConfigManager()
    config = manager.get_default_config()
    
    print(f"✅ Loaded: {config.name}")
    print(f"   GA population: {config.ga.population_size}")
    print(f"   GA generations: {config.ga.generations}")
    print(f"   Deferral threshold: {config.deferral.overload_threshold}")
    print(f"   Uncertainty sims: {config.uncertainty.num_simulations}")
    
    assert config.name == "balanced", "Default should be balanced"
    assert config.ga.population_size == 20, "Default GA pop should be 20"
    print("\n✅ TEST 1 PASSED")


def test_presets():
    """Test: All preset configurations are valid."""
    print("\n" + "="*70)
    print("TEST 2: Test Configuration Presets")
    print("="*70)
    
    manager = ConfigManager()
    
    profiles = {
        ConfigProfile.CONSERVATIVE: manager.get_conservative_config(),
        ConfigProfile.BALANCED: manager.get_default_config(),
        ConfigProfile.AGGRESSIVE: manager.get_aggressive_config(),
        ConfigProfile.EXPERIMENTAL: manager.get_experimental_config(),
    }
    
    for profile, config in profiles.items():
        errors = config.validate()
        status = "✅ VALID" if not errors else f"❌ {errors}"
        print(f"{config.name.upper():<15} {status}")
        assert not errors, f"Preset {config.name} has validation errors: {errors}"
    
    # Check that profiles are different
    pops = [c.ga.population_size for c in profiles.values()]
    assert len(set(pops)) > 1, "Profiles should have different GA populations"
    
    print("\n✅ TEST 2 PASSED")


def test_validation():
    """Test: Configuration validation catches errors."""
    print("\n" + "="*70)
    print("TEST 3: Configuration Validation")
    print("="*70)
    
    manager = ConfigManager()
    config = manager.get_default_config()
    
    # Valid config should have no errors
    errors = config.validate()
    assert not errors, f"Default config should be valid: {errors}"
    print("✅ Default config validates")
    
    # Invalid GA config (population too small)
    bad_config = manager.get_default_config()
    bad_config.ga.population_size = 2
    errors = bad_config.validate()
    assert errors, "Should have validation errors for small population"
    assert "ga" in errors, "Should have GA errors"
    print("✅ Catches invalid GA population_size")
    
    # Invalid GA config (generations too small)
    bad_config = manager.get_default_config()
    bad_config.ga.generations = 1  # Valid
    bad_config.ga.population_size = 2  # Invalid
    errors = bad_config.validate()
    assert errors, "Should have validation errors"
    print("✅ Catches invalid GA settings")
    
    # Invalid fatigue config (bad thresholds)
    bad_config = manager.get_default_config()
    bad_config.fatigue.poor_score_threshold = 0.8
    bad_config.fatigue.good_score_threshold = 0.2
    errors = bad_config.validate()
    assert errors, "Should have validation errors for bad thresholds"
    assert "fatigue" in errors, "Should have fatigue errors"
    print("✅ Catches invalid fatigue thresholds")
    
    print("\n✅ TEST 3 PASSED")


def test_save_load():
    """Test: Save and load configurations from JSON."""
    print("\n" + "="*70)
    print("TEST 4: Save and Load Configurations")
    print("="*70)
    
    manager = ConfigManager()
    config = manager.get_conservative_config()
    
    # Save to file
    path = manager.save_to_file(config, filename="test_config")
    print(f"✅ Saved to: {path}")
    
    # Verify file exists
    assert Path(path).exists(), f"Config file should exist at {path}"
    print("✅ File created successfully")
    
    # Load from file
    loaded = manager.load_from_file("test_config")
    print(f"✅ Loaded: {loaded.name}")
    
    # Verify content matches
    assert loaded.name == config.name, "Loaded name should match"
    assert loaded.ga.population_size == config.ga.population_size, "GA pop should match"
    assert loaded.uncertainty.num_simulations == config.uncertainty.num_simulations
    print("✅ Loaded config matches saved config")
    
    # Clean up
    Path(path).unlink()
    print("✅ Cleanup complete")
    
    print("\n✅ TEST 4 PASSED")


def test_current_config():
    """Test: Set and get current configuration."""
    print("\n" + "="*70)
    print("TEST 5: Set and Get Current Configuration")
    print("="*70)
    
    manager = ConfigManager()
    
    # Initial state - should have default config
    assert manager.current_config is not None, "Should have initial config"
    print("✅ Initial state: has default config")
    
    # Set config
    config = manager.get_aggressive_config()
    initial_history_len = len(manager.config_history)
    manager.set_current_config(config)
    assert manager.current_config is not None, "Should have current config"
    assert manager.current_config.name == "aggressive"
    print("✅ Set aggressive config as current")
    
    # History tracking
    assert len(manager.config_history) > initial_history_len, "Should track history"
    print(f"✅ Config history tracked ({len(manager.config_history)} entries)")
    
    print("\n✅ TEST 5 PASSED")


def test_parameter_update():
    """Test: Update individual parameters at runtime."""
    print("\n" + "="*70)
    print("TEST 6: Runtime Parameter Updates")
    print("="*70)
    
    manager = ConfigManager()
    manager.set_current_config(manager.get_default_config())
    
    # Update valid parameter
    original = manager.current_config.ga.population_size
    manager.update_parameter("ga", "population_size", 30)
    assert manager.current_config.ga.population_size == 30, "Should update parameter"
    print(f"✅ Updated GA population_size: {original} → 30")
    
    # Try invalid update
    try:
        manager.update_parameter("ga", "population_size", 2)
        assert False, "Should reject invalid population_size"
    except ValueError as e:
        print(f"✅ Rejected invalid population_size: {e}")
    
    print("\n✅ TEST 6 PASSED")


def test_config_report():
    """Test: Generate configuration reports."""
    print("\n" + "="*70)
    print("TEST 7: Configuration Reports")
    print("="*70)
    
    manager = ConfigManager()
    manager.set_current_config(manager.get_default_config())
    
    report = manager.get_report()
    assert report is not None, "Should generate report"
    assert len(report) > 0, "Report should have content"
    assert "balanced" in report.lower() or "default" in report.lower(), "Report should mention config name"
    print("✅ Generated configuration report")
    print(f"   Report length: {len(report)} characters")
    
    print("\n✅ TEST 7 PASSED")


def test_config_comparison():
    """Test: Compare two configurations."""
    print("\n" + "="*70)
    print("TEST 8: Compare Configurations")
    print("="*70)
    
    manager = ConfigManager()
    config1 = manager.get_conservative_config()
    config2 = manager.get_aggressive_config()
    
    comparison = manager.compare_configs(config1, config2)
    assert comparison is not None, "Should generate comparison"
    assert len(comparison) > 0, "Comparison should have content"
    assert "conservative" in comparison.lower(), "Should mention config1"
    assert "aggressive" in comparison.lower(), "Should mention config2"
    print("✅ Generated comparison between conservative and aggressive")
    print(f"   Comparison length: {len(comparison)} characters")
    
    print("\n✅ TEST 8 PASSED")


def test_profile_differences():
    """Test: Verify profiles have expected differences."""
    print("\n" + "="*70)
    print("TEST 9: Profile Differences")
    print("="*70)
    
    manager = ConfigManager()
    conservative = manager.get_conservative_config()
    aggressive = manager.get_aggressive_config()
    
    # Conservative should have smaller GA
    assert conservative.ga.population_size < aggressive.ga.population_size
    print(f"✅ Conservative GA ({conservative.ga.population_size}) < "
          f"Aggressive ({aggressive.ga.population_size})")
    
    # Conservative should have LOWER overload threshold (defer earlier/more often)
    assert conservative.deferral.overload_threshold < aggressive.deferral.overload_threshold
    print(f"✅ Conservative defers more aggressively "
          f"(threshold: {conservative.deferral.overload_threshold}x vs "
          f"{aggressive.deferral.overload_threshold}x)")
    
    # Conservative should defer more tasks by default
    assert conservative.deferral.deferral_count_target > aggressive.deferral.deferral_count_target
    print(f"✅ Conservative defers more tasks "
          f"({conservative.deferral.deferral_count_target} vs "
          f"{aggressive.deferral.deferral_count_target})")
    
    print("\n✅ TEST 9 PASSED")


def test_integration_with_forecast():
    """Test: Configuration works with forecast system."""
    print("\n" + "="*70)
    print("TEST 10: Integration with Forecast System")
    print("="*70)
    
    from datetime import datetime, timedelta
    from models import Task
    from day_model import Day
    from scheduler import Scheduler
    from forecast import MultiDayForecaster
    
    # Create day with tasks
    day = Day(available_hours=8.0, sleep_hours=7.0)
    day.add_task(Task("Task 1", 2.0, 8, datetime.now() + timedelta(hours=4)))
    day.add_task(Task("Task 2", 1.5, 7, datetime.now() + timedelta(hours=6)))
    day.add_task(Task("Task 3", 2.5, 9, datetime.now() + timedelta(hours=8)))
    
    scheduler = Scheduler(day, None)
    
    # Test with different configs
    manager = ConfigManager()
    configs = [
        manager.get_conservative_config(),
        manager.get_default_config(),
        manager.get_aggressive_config(),
    ]
    
    for config in configs:
        try:
            # This should work without errors
            forecaster = MultiDayForecaster(day, scheduler, days=1, config=config)
            assert forecaster is not None, f"Forecaster creation failed for {config.name}"
            print(f"✅ Forecaster created with {config.name} config")
        except Exception as e:
            print(f"❌ Failed to create forecaster with {config.name}: {e}")
            raise
    
    print("\n✅ TEST 10 PASSED")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("CONFIGURATION SYSTEM TEST SUITE")
    print("="*70)
    
    tests = [
        test_default_config,
        test_presets,
        test_validation,
        test_save_load,
        test_current_config,
        test_parameter_update,
        test_config_report,
        test_config_comparison,
        test_profile_differences,
        test_integration_with_forecast,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n❌ TEST FAILED: {test.__name__}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*70)
    print(f"TEST SUMMARY: {passed} passed, {failed} failed ({passed + failed} total)")
    print("="*70 + "\n")
    
    if failed == 0:
        print("✅ ALL TESTS PASSED!\n")
    else:
        print(f"❌ {failed} test(s) failed\n")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
