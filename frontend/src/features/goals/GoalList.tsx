import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Calendar, CheckCircle2, ListChecks, Pencil, Plus, Target } from "lucide-react";
import type { Goal, Task } from "@/api/endpoints";
import { useGoals, useTasks } from "@/api/hooks";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/Feedback";
import { GoalDialog } from "./GoalDialog";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

export function GoalList({ onSelectGoal }: { onSelectGoal?: (goal: Goal) => void }) {
  const { data, isLoading, isError, error, refetch } = useGoals();
  const tasksQuery = useTasks();

  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [editingGoal, setEditingGoal] = React.useState<Goal | null>(null);

  const goals = React.useMemo(() => data?.goals ?? [], [data]);
  const tasks = React.useMemo(() => tasksQuery.data?.tasks ?? [], [tasksQuery.data]);

  // Compute linked tasks map: goal_id -> count of tasks & completed tasks
  const goalStats = React.useMemo(() => {
    const map = new Map<number, { total: number; completed: number }>();
    for (const t of tasks) {
      if (t.goal_id) {
        const cur = map.get(t.goal_id) || { total: 0, completed: 0 };
        cur.total++;
        if (t.completed) cur.completed++;
        map.set(t.goal_id, cur);
      }
    }
    return map;
  }, [tasks]);

  const handleCreate = () => {
    setEditingGoal(null);
    setDialogOpen(true);
  };

  const handleEdit = (g: Goal) => {
    setEditingGoal(g);
    setDialogOpen(true);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-content-primary">Strategic Goals</h2>
          <p className="text-xs text-content-tertiary">
            Define objectives and target dates to organize and focus your planning.
          </p>
        </div>
        <Button size="sm" leftIcon={<Plus className="size-3.5" />} onClick={handleCreate}>
          New Goal
        </Button>
      </div>

      {isLoading ? (
        <SkeletonRows rows={3} />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : goals.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border p-6 text-center">
          <EmptyState
            compact
            icon={<Target className="size-8" />}
            title="No goals defined yet"
            description="Create your first goal to anchor your daily task prioritization."
            action={
              <Button size="sm" leftIcon={<Plus className="size-3.5" />} onClick={handleCreate}>
                Create Goal
              </Button>
            }
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <AnimatePresence initial={false}>
            {goals.map((g) => {
              const stats = goalStats.get(g.id) || { total: 0, completed: 0 };
              const progressPct = Math.round((g.progress ?? 0) * 100);
              const targetDate = g.target_date ? new Date(g.target_date) : null;
              const isPastTarget = targetDate && targetDate.getTime() < Date.now() && g.status !== "completed";

              return (
                <motion.div
                  key={g.id}
                  layout="position"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="relative flex flex-col justify-between overflow-hidden rounded-xl border border-border-subtle bg-surface-1 p-4 transition-colors hover:border-border dark:border-border dark:hover:border-content-muted/30"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <h3 className="truncate text-sm font-semibold text-content-primary">
                            {g.title}
                          </h3>
                          <Badge
                            tone={g.status === "completed" ? "success" : g.status === "paused" ? "warning" : "primary"}
                            className="capitalize text-[10px]"
                          >
                            {g.status}
                          </Badge>
                          <Badge tone="neutral" className="font-mono text-[10px]">
                            P{g.priority}
                          </Badge>
                        </div>
                        {g.category && (
                          <span className="text-[11px] text-content-tertiary capitalize">
                            {g.category}
                          </span>
                        )}
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleEdit(g)}
                        aria-label={`Edit ${g.title}`}
                        className="text-content-tertiary hover:text-content-primary p-1.5 h-auto"
                      >
                        <Pencil className="size-3.5" />
                      </Button>
                    </div>

                    {g.description && (
                      <p className="mt-2 line-clamp-2 text-xs text-content-secondary">
                        {g.description}
                      </p>
                    )}
                  </div>

                  <div className="mt-4 space-y-2 pt-2 border-t border-border-subtle">
                    {/* Progress bar */}
                    <div>
                      <div className="flex justify-between text-[11px] text-content-tertiary mb-1">
                        <span>Progress</span>
                        <span className="font-mono font-medium">{progressPct}%</span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-surface-2 overflow-hidden">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all duration-300",
                            progressPct >= 100
                              ? "bg-status-success"
                              : progressPct > 50
                              ? "bg-primary"
                              : "bg-quantum"
                          )}
                          style={{ width: `${progressPct}%` }}
                        />
                      </div>
                    </div>

                    {/* Meta info: target date & linked tasks */}
                    <div className="flex items-center justify-between text-[11px] text-content-tertiary">
                      <span className="inline-flex items-center gap-1">
                        <ListChecks className="size-3" />
                        {stats.total > 0
                          ? `${stats.completed}/${stats.total} tasks`
                          : "No tasks linked"}
                      </span>
                      {targetDate && (
                        <span
                          className={cn(
                            "inline-flex items-center gap-1",
                            isPastTarget ? "text-status-error font-medium" : "text-content-tertiary"
                          )}
                        >
                          <Calendar className="size-3" />
                          {isPastTarget ? "Overdue" : `Target ${formatRelative(g.target_date)}`}
                        </span>
                      )}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}

      <GoalDialog
        goal={editingGoal}
        isOpen={dialogOpen}
        onClose={() => {
          setDialogOpen(false);
          setEditingGoal(null);
        }}
      />
    </div>
  );
}

