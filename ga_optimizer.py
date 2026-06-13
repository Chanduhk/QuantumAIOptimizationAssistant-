import random
from evaluation import DayEvaluator

class GeneticOptimizer:
    def __init__(self, day, scheduler, population_size=20, generations=50, mutation_rate=0.1):
        self.day = day
        self.scheduler = scheduler
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate

    def create_individual(self):
        individual = self.day.tasks[:]
        random.shuffle(individual)
        return individual

    def create_population(self):
        return [self.create_individual() for _ in range(self.population_size)]

    def fitness(self, individual):
        schedule = self.scheduler.generate_from_order(individual)
        evaluator = DayEvaluator(self.day, schedule)
        return evaluator.total_score()

    def selection(self, population):
        population.sort(key=lambda ind: self.fitness(ind), reverse=True)
        return population[:self.population_size // 2]

    def crossover(self, parent1, parent2):
        size = len(parent1)
        start, end = sorted(random.sample(range(size), 2))
        child = [None] * size
        child[start:end] = parent1[start:end]

        pointer = 0
        for gene in parent2:
            if gene not in child:
                while child[pointer] is not None:
                    pointer += 1
                child[pointer] = gene

        return child

    def mutate(self, individual):
        if random.random() < self.mutation_rate:
            i, j = random.sample(range(len(individual)), 2)
            individual[i], individual[j] = individual[j], individual[i]
        return individual

    def evolve(self):
        if len(self.day.tasks) < 2:
           # Not enough tasks to evolve
           schedule = self.scheduler.generate_from_order(self.day.tasks)
           evaluator = DayEvaluator(self.day, schedule)
           return schedule, evaluator.total_score()

        population = self.create_population()

        for _ in range(self.generations):
            selected = self.selection(population)
            next_generation = selected[:]

            while len(next_generation) < self.population_size:
                parent1, parent2 = random.sample(selected, 2)
                child = self.crossover(parent1, parent2)
                child = self.mutate(child)
                next_generation.append(child)

            population = next_generation

        best_individual = max(population, key=lambda ind: self.fitness(ind))
        best_schedule = self.scheduler.generate_from_order(best_individual)
        best_score = self.fitness(best_individual)

        return best_schedule, best_score
