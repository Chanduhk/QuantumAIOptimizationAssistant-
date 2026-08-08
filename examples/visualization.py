import matplotlib.pyplot as plt


def plot_system_metrics(day_scores, entropy_values, csi_values, penalty_values):
    plt.figure()
    plt.plot(range(1, len(day_scores) + 1), day_scores, marker='o')
    plt.title("Daily Productivity Score")
    plt.xlabel("Day")
    plt.ylabel("Score")
    plt.grid(True)

    plt.figure()
    plt.plot(range(1, len(penalty_values) + 1), penalty_values, marker='o')
    plt.title("Penalty Recovery Curve")
    plt.xlabel("Day")
    plt.ylabel("Average Penalty")
    plt.grid(True)

    plt.figure()
    plt.plot(range(1, len(entropy_values) + 1), entropy_values, marker='o')
    plt.title("Penalty Entropy Over Time")
    plt.xlabel("Day")
    plt.ylabel("Entropy")
    plt.grid(True)

    plt.figure()
    plt.plot(range(1, len(csi_values) + 1), csi_values, marker='o')
    plt.title("Convergence Speed Index")
    plt.xlabel("Day")
    plt.ylabel("CSI")
    plt.grid(True)

    plt.show()
