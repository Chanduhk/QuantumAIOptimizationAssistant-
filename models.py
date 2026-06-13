import math
from datetime import datetime

class Task:
    def __init__(self, name, duration, priority, deadline, urgency_decay_k=0.1):
        """
        Create a schedulable task.

        Example:
            task = Task("Write report", 2.0, 6, deadline, urgency_decay_k=0.1)
            # effective_priority = 6 + 0.1 * days_deferred
        """
        self.name = name
        self.duration = duration
        self.priority = priority
        self.deadline = deadline
        self.delay_count = 0
        
        # Urgency-decay metadata.
        # days_deferred increases every day a task stays in backlog.
        self.days_deferred = 0
        self.urgency_decay_k = urgency_decay_k
        
        # Strategic Deferral metadata
        self.deferred = False                   # Is task currently deferred?
        self.deferral_count = 0                 # How many times deferred?
        self.deferral_start_time = None         # When was deferral started?
        self.deferral_reason = None             # Why was it deferred?
        
        # Strategic Compression metadata
        self.freeze_penalty_factor = 1.0        # Soft-freeze penalty (1.0 = no penalty)

    def advance_time(self, hours=24):
        from datetime import timedelta
        self.deadline -= timedelta(hours=hours)

    def effective_priority(self, k=None):
        """
        Compute priority with anti-starvation urgency boost.

        Formula:
            effective_priority = base_priority + k * days_deferred
        """
        # Use per-task k unless an explicit runtime override is supplied.
        decay_k = self.urgency_decay_k if k is None else k
        return self.priority + (decay_k * self.days_deferred)

    def increment_deferred_day(self):
        """Increment deferred-day counter when task is not scheduled today."""
        self.days_deferred += 1

    def reset_deferred_days(self):
        """Reset deferred-day counter once task gets scheduled/completed."""
        self.days_deferred = 0

    def urgency_boost(self, k=None):
        """Return only the urgency boost term k * days_deferred."""
        return self.effective_priority(k=k) - self.priority

    def urgency_score(self, decay_constant=12):
        import math
        from datetime import datetime

        time_left = (self.deadline - datetime.now()).total_seconds() / 3600

        if time_left <= 0:
            base_urgency = self.priority * 10
        else:
            decay_factor = math.exp(-time_left / decay_constant)
            base_urgency = self.priority * decay_factor

        # Delay amplification
        delay_factor = 0.25   # tunable parameter
        amplified_urgency = base_urgency * (1 + delay_factor * self.delay_count)

        # Strategic deferral: reduce urgency of deferred tasks
        # Prevents false urgency explosion while task is being deferred
        # Reduces to 30% of urgency (70% reduction by default)
        if self.deferred:
            amplified_urgency = amplified_urgency * (1 - 0.7)

        # Anti-starvation: fold effective priority into urgency score
        # so deferred tasks gradually climb in all selectors.
        effective_ratio = self.effective_priority() / max(self.priority, 1e-6)
        amplified_urgency *= effective_ratio
        
        # Soft freeze: de-prioritize non-protected tasks without excluding them.
        amplified_urgency *= self.freeze_penalty_factor

        return amplified_urgency


    def __repr__(self):
        return f"{self.name} (Priority {self.priority}, {self.duration}h)"

class EnergyProfile:
    def __init__(self):
        self.slots = {
            "morning": 8,
            "afternoon": 6,
            "evening": 4
        }

    def get_energy(self, time_block):
        return self.slots.get(time_block, 5)
