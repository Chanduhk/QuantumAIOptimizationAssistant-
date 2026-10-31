import * as React from "react";
import { useSearchParams } from "react-router-dom";
import { AnimatePresence } from "framer-motion";
import { CheckCircle2, ListChecks, MessageSquareDot, PlayCircle, Plus, Search, SearchX } from "lucide-react";
import type { Task } from "@/api/endpoints";
import { useTasks } from "@/api/hooks";
import { Page, PageHeader } from "@/components/layout/Page";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { Segmented } from "@/components/ui/Tabs";
import { Stat } from "@/components/ui/Stat";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/Feedback";
import { TaskRow } from "@/features/tasks/TaskRow";
import { TaskCreateDialog } from "@/features/tasks/TaskCreateDialog";
import { FeedbackDialog } from "@/features/tasks/FeedbackDialog";
import { hasFeedback, lifecycle, sortTasks } from "@/features/tasks/taskUtils";
import { formatDuration } from "@/utils/formatters";

type Filter = "all" | "created" | "started" | "completed" | "feedback";
type Sort = "priority" | "recent" | "duration";

export function TasksPage() {
  const { data, isLoading, isError, error, refetch } = useTasks();
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = React.useState<Filter>("all");
  const [sort, setSort] = React.useState<Sort>("priority");
  const [query, setQuery] = React.useState("");
  const [feedbackTask, setFeedbackTask] = React.useState<Task | null>(null);
  const createOpen = params.get("new") === "1";

  const setCreateOpen = (open: boolean) => {
    const next = new URLSearchParams(params);
    if (open) next.set("new", "1");
    else next.delete("new");
    setParams(next, { replace: true });
  };

  const tasks = React.useMemo(() => data?.tasks ?? [], [data]);
  const counts = React.useMemo(() => {
    const c = { all: tasks.length, created: 0, started: 0, completed: 0, feedback: 0, plannedMinutes: 0 };
    for (const t of tasks) {
      const s = lifecycle(t);
      if (s === "created") {
        c.created++;
        c.plannedMinutes += t.estimated_duration ?? 0;
      } else if (s === "started") c.started++;
      else if (s === "completed") {
        c.completed++;
        if (!hasFeedback(t)) c.feedback++;
      }
    }
    return c;
  }, [tasks]);

  const visible = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = tasks.filter((t) => {
      const s = lifecycle(t);
      if (filter === "feedback" && !(s === "completed" && !hasFeedback(t))) return false;
      if (filter !== "all" && filter !== "feedback" && s !== filter) return false;
      return !q || t.title.toLowerCase().includes(q) || t.task_type.toLowerCase().includes(q);
    });
    // Keep in-progress work on top regardless of sort.
    const sorted = sortTasks(filtered, sort);
    return [...sorted.filter((t) => lifecycle(t) === "started"), ...sorted.filter((t) => lifecycle(t) !== "started")];
  }, [tasks, filter, sort, query]);

  return (
    <Page>
      <PageHeader
        layers="L1 · L10"
        title="Tasks"
        description="Everything HELIOX optimizes starts here. Capture work with explicit estimates, run it through its lifecycle, and rate the outcome so the models can learn."
        actions={<Button leftIcon={<Plus />} onClick={() => setCreateOpen(true)}>New task</Button>}
      />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Planned" value={counts.created} loading={isLoading} icon={<ListChecks />} sub={`${formatDuration(counts.plannedMinutes)} of estimated work`} />
        <Stat label="In progress" value={counts.started} loading={isLoading} icon={<PlayCircle />} accent="primary" sub="Live execution (Layer 10)" />
        <Stat label="Completed" value={counts.completed} loading={isLoading} icon={<CheckCircle2 />} accent="success" sub="Actual outcomes (Layer 11)" />
        <Stat label="Awaiting feedback" value={counts.feedback} loading={isLoading} icon={<MessageSquareDot />} accent={counts.feedback ? "warning" : "neutral"} sub="Ratings feed Layer 12" />
      </div>

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Segmented<Filter>
          ariaLabel="Filter tasks"
          value={filter}
          onChange={setFilter}
          items={[
            { value: "all", label: "All", count: counts.all },
            { value: "created", label: "Planned", count: counts.created },
            { value: "started", label: "In progress", count: counts.started },
            { value: "completed", label: "Completed", count: counts.completed },
            { value: "feedback", label: "Needs feedback", count: counts.feedback },
          ]}
        />
        <div className="flex gap-2">
          <div className="relative flex-1 lg:w-64 lg:flex-none">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" />
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search title or type" className="pl-9" aria-label="Search tasks" />
          </div>
          <Select value={sort} onChange={(e) => setSort(e.target.value as Sort)} className="w-36" aria-label="Sort tasks">
            <option value="priority">Priority</option>
            <option value="recent">Newest</option>
            <option value="duration">Longest</option>
          </Select>
        </div>
      </div>

      {isLoading ? (
        <SkeletonRows rows={5} />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : tasks.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border">
          <EmptyState
            icon={<ListChecks />}
            title="No tasks yet"
            description="Create your first task, or describe your day to JAM and accept the plan it proposes."
            action={<Button leftIcon={<Plus />} onClick={() => setCreateOpen(true)}>Create a task</Button>}
          />
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border">
          <EmptyState compact icon={<SearchX />} title="Nothing matches" description="Try a different filter or search term." />
        </div>
      ) : (
        <ul className="space-y-2" aria-label="Task list">
          <AnimatePresence initial={false}>
            {visible.map((task) => (
              <TaskRow key={task.id} task={task} onRequestFeedback={setFeedbackTask} />
            ))}
          </AnimatePresence>
        </ul>
      )}

      <TaskCreateDialog isOpen={createOpen} onClose={() => setCreateOpen(false)} />
      <FeedbackDialog task={feedbackTask} isOpen={feedbackTask !== null} onClose={() => setFeedbackTask(null)} />
    </Page>
  );
}
