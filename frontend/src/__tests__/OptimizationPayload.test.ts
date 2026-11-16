import { describe, expect, it } from "vitest";
import { mapTasksToOrchestratorInput } from "@/features/optimization/useOptimization";
import { normalizeErrorMessage } from "@/utils/formatters";
import type { Task } from "@/api/endpoints";

describe("Optimization Payload & Dependency Normalization", () => {
  it("serializes tasks without dependencies to empty array depends_on_task_ids: []", () => {
    const rawTasks: Task[] = [
      {
        id: 31,
        user_id: 1,
        title: "Research Paper",
        description: "Review literature",
        task_type: "RESEARCH",
        priority: 2,
        estimated_duration: 45,
        estimated_duration_unit: "minutes",
        estimated_duration_source: "manual",
        deadline: null,
        dependencies: [],
        lifecycle_state: "planned",
        completed: false,
        created_at: "2026-11-14T10:00:00Z",
      },
    ];

    const mapped = mapTasksToOrchestratorInput(rawTasks);
    expect(mapped).toHaveLength(1);
    expect(mapped[0].id).toBe("31");
    expect(mapped[0].title).toBe("Research Paper");
    expect(mapped[0].depends_on_task_ids).toEqual([]);
    expect(mapped[0].dependencies).toEqual([]);
  });

  it("normalizes numeric and string dependencies into clean non-empty string arrays", () => {
    const rawTasks: Task[] = [
      {
        id: 32,
        user_id: 1,
        title: "Quantum Software",
        task_type: "PROJECT",
        priority: 3,
        estimated_duration: 90,
        estimated_duration_unit: "minutes",
        // Mixed numeric and string types as might come from DB or user input
        dependencies: [31 as unknown as number, " 30 ", null as unknown as string, "" as unknown as string],
        lifecycle_state: "planned",
        completed: false,
        created_at: "2026-11-14T10:00:00Z",
      },
    ];

    const mapped = mapTasksToOrchestratorInput(rawTasks);
    expect(mapped).toHaveLength(1);
    expect(mapped[0].id).toBe("32");
    expect(mapped[0].depends_on_task_ids).toEqual(["31", "30"]);
    expect(mapped[0].dependencies).toEqual(["31", "30"]);
  });

  it("handles null or undefined dependencies safely without throwing", () => {
    const rawTasks: Task[] = [
      {
        id: 33,
        user_id: 1,
        title: "Documentation",
        task_type: "WRITING",
        priority: 1,
        estimated_duration: 30,
        estimated_duration_unit: "minutes",
        dependencies: undefined,
        lifecycle_state: "planned",
        completed: false,
        created_at: "2026-11-14T10:00:00Z",
      },
    ];

    const mapped = mapTasksToOrchestratorInput(rawTasks);
    expect(mapped[0].depends_on_task_ids).toEqual([]);
    expect(mapped[0].dependencies).toEqual([]);
  });

  it("formats dependency validation errors into actionable human messages", () => {
    const err = normalizeErrorMessage("depends_on_task_ids must contain non-empty strings.");
    expect(err.title).toBe("Task Dependency Issue");
    expect(err.explanation).toContain("depends_on_task_ids must contain non-empty strings.");
    expect(err.actionSuggestion).toContain("prerequisites");
    expect(err.isRetryable).toBe(true);

    const cycleErr = normalizeErrorMessage("Circular dependency detected among tasks: 31 -> 32 -> 31");
    expect(cycleErr.title).toBe("Task Dependency Issue");
    expect(cycleErr.explanation).toContain("Circular dependency");
    expect(cycleErr.isRetryable).toBe(true);
  });
});
