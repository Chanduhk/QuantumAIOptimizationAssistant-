"""
Configuration System Demo and Examples

Shows how to use the new structured configuration system.
"""

from pathlib import Path
from config_system import ConfigManager, ConfigProfile, SystemConfig
from forecast import MultiDayForecaster
from day_model import Day
from scheduler import Scheduler
from models import EnergyProfile


def demo_basic_usage():
    """Demonstrate basic configuration usage."""
    print("\n" + "="*60)
    print("DEMO 1: Basic Configuration Usage")
    print("="*60 + "\n")
    
    # Create config manager
    manager = ConfigManager()
    
    # Load default (balanced) configuration
    config = manager.get_default_config()
    print(f"Loaded config: {config.name}")
    print(f"GA population size: {config.ga.population_size}")
    print(f"GA generations: {config.ga.generations}")
    print(f"Deferral threshold: {config.deferral.overload_threshold}x")
    
    # Validate configuration
    errors = config.validate()
    print(f"Validation: {'✅ VALID' if not errors else '❌ INVALID'}")


def demo_presets():
    """Demonstrate configuration presets."""
    print("\n" + "="*60)
    print("DEMO 2: Configuration Presets")
    print("="*60 + "\n")
    
    manager = ConfigManager()
    
    profiles = [
        ConfigProfile.CONSERVATIVE,
        ConfigProfile.BALANCED,
        ConfigProfile.AGGRESSIVE,
        ConfigProfile.EXPERIMENTAL,
    ]
    
    print("Comparing GA parameters across profiles:\n")
    print(f"{'Profile':<15} {'Population':<12} {'Generations':<12} {'Mutation Rate'}")
    print("-" * 55)
    
    for profile in profiles:
        config = manager.load_preset(profile)
        print(f"{config.name:<15} {config.ga.population_size:<12} "
              f"{config.ga.generations:<12} {config.ga.mutation_rate:.1%}")
    
    print("\nComparing Deferral parameters across profiles:\n")
    print(f"{'Profile':<15} {'Threshold':<12} {'Target Deferrals':<18}")
    print("-" * 45)
    
    for profile in profiles:
        config = manager.load_preset(profile)
        print(f"{config.name:<15} {config.deferral.overload_threshold:<12.1f}x "
              f"{config.deferral.deferral_count_target:<18}")


def demo_save_load():
    """Demonstrate saving and loading configurations."""
    print("\n" + "="*60)
    print("DEMO 3: Saving and Loading Configurations")
    print("="*60 + "\n")
    
    manager = ConfigManager()
    
    # Get aggressive config
    config = manager.get_aggressive_config()
    
    # Save to file
    path = manager.save_to_file(config, filename="demo_aggressive")
    print(f"✅ Saved to: {path}")
    
    # Load from file
    loaded = manager.load_from_file("demo_aggressive")
    print(f"✅ Loaded: {loaded.name}")
    print(f"   GA population: {loaded.ga.population_size}")
    print(f"   Uncertainty simulations: {loaded.uncertainty.num_simulations}")


def demo_runtime_update():
    """Demonstrate runtime parameter updates."""
    print("\n" + "="*60)
    print("DEMO 4: Runtime Parameter Updates")
    print("="*60 + "\n")
    
    manager = ConfigManager()
    config = manager.get_default_config()
    manager.set_current_config(config)
    
    print(f"Current GA population: {manager.current_config.ga.population_size}")
    
    # Update single parameter
    manager.update_parameter("ga", "population_size", 30)
    print(f"After update: {manager.current_config.ga.population_size}")
    
    # Try invalid update (will fail)
    try:
        manager.update_parameter("ga", "population_size", 2)  # Too small
        print("Update succeeded")
    except ValueError as e:
        print(f"❌ Update failed (expected): {e}")


def demo_configuration_report():
    """Demonstrate configuration reporting."""
    print("\n" + "="*60)
    print("DEMO 5: Configuration Report")
    print("="*60)
    
    manager = ConfigManager()
    config = manager.get_default_config() if hasattr(manager, 'get_balanced_config') is False else manager.get_balanced_config()
    manager.set_current_config(config)
    
    print(manager.get_report())


def demo_config_comparison():
    """Demonstrate configuration comparison."""
    print("\n" + "="*60)
    print("DEMO 6: Configuration Comparison")
    print("="*60 + "\n")
    
    manager = ConfigManager()
    
    conservative = manager.get_conservative_config()
    aggressive = manager.get_aggressive_config()
    
    print(manager.compare_configs(conservative, aggressive))


def demo_with_forecast():
    """Demonstrate using configuration with forecast."""
    print("\n" + "="*60)
    print("DEMO 7: Using Configuration with Forecast")
    print("="*60 + "\n")
    
    # Create sample day
    day = Day(available_hours=8.0, sleep_hours=7.0)
    energy = EnergyProfile()
    scheduler = Scheduler(day, energy)
    
    # Add some sample tasks
    from models import Task
    from datetime import datetime, timedelta
    
    day.tasks = [
        Task("Task 1", 2.0, 8, datetime.now() + timedelta(hours=4)),
        Task("Task 2", 1.5, 7, datetime.now() + timedelta(hours=6)),
        Task("Task 3", 2.5, 9, datetime.now() + timedelta(hours=8)),
    ]
    
    # Test with different configurations
    configs = {
        "Conservative": ConfigManager().get_conservative_config(),
        "Aggressive": ConfigManager().get_aggressive_config(),
    }
    
    for config_name, config in configs.items():
        print(f"\nTesting with {config_name} configuration:")
        print(f"  GA: {config.ga.population_size} population, "
              f"{config.ga.generations} generations")
        print(f"  Deferral: {config.deferral.overload_threshold}x threshold")
        print(f"  Uncertainty: {config.uncertainty.num_simulations} simulations")
        
        # Create forecaster with config
        forecaster = MultiDayForecaster(day, scheduler, days=2, config=config)
        print(f"  Forecaster initialized with {config_name} config ✅")
        
        # Create forecaster with config
        forecaster = MultiDayForecaster(day, scheduler, days=2, config=config)
        print(f"  Forecaster initialized with {config_name} config ✅")


def main():
    """Run all demos."""
    print("\n" + "="*60)
    print("QUANTUM LIFE AI - CONFIGURATION SYSTEM DEMO")
    print("="*60)
    
    demo_basic_usage()
    demo_presets()
    demo_save_load()
    demo_runtime_update()
    demo_configuration_report()
    demo_config_comparison()
    demo_with_forecast()
    
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
