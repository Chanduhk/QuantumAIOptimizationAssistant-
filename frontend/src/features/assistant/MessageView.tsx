import * as React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowRight, CheckCircle2, ChevronDown, ListTodo, OctagonAlert, RotateCw } from "lucide-react";
import type { JamMessage } from "@/stores/jamStore";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { HelioxMark } from "@/components/brand/HelioxMark";
import { normalizeErrorMessage, formatLocalTime } from "@/utils/formatters";
import { humanize, num, rec, recs, str, type Rec } from "@/lib/data";
import { priorityMeta } from "@/features/tasks/taskUtils";
import { cn } from "@/lib/utils";
import { JAMThinkingIndicator } from "@/components/motion";
import { ProposalCard } from "./ProposalCard";

function Surface({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("rounded-2xl border border-border bg-surface-1 p-4 shadow-card transition-all duration-300 hover:border-content-muted/30 hover:shadow-lift", className)}>{children}</div>;
}

function TaskCreated({ result }: { result: Rec }) {
  const task = rec(result.task) ?? {};
  const p = priorityMeta(num(task.priority) ?? 3);
  return (
    <Surface className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <span className="grid size-9 place-items-center rounded-xl bg-status-success/10 text-status-success"><CheckCircle2 className="size-5" /></span>
        <div>
          <p className="text-sm font-medium">{str(task.title, "Task created")}</p>
          <p className="text-xs text-content-tertiary"><span className="capitalize">{str(task.task_type, "general")}</span> · {str(task.estimated_duration)} {str(task.estimated_duration_unit, "min")} · <span>P{num(task.priority) ?? 3} {p.label}</span></p>
        </div>
      </div>
      <Link to="/tasks"><Button size="sm" variant="secondary" rightIcon={<ArrowRight />}>Open tasks</Button></Link>
    </Surface>
  );
}

function TaskList({ result, intent }: { result: Rec; intent?: string }) {
  const tasks = recs(result.prioritized_tasks).length ? recs(result.prioritized_tasks) : recs(result.tasks);
  return (
    <Surface className="p-0">
      <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3 dark:border-border">
        <p className="flex items-center gap-2 text-sm font-semibold"><ListTodo className="size-4 text-primary" />{intent === "prioritize_tasks" ? "Suggested order" : "Your open tasks"}</p>
        <Badge tone="neutral">{tasks.length}</Badge>
      </div>
      {str(result.executive_summary) && <p className="px-4 pt-3 text-[13px] text-content-secondary">{str(result.executive_summary)}</p>}
      <ol className="divide-y divide-border-subtle p-2 dark:divide-border">
        {tasks.length === 0 && <li className="px-2 py-4 text-center text-[13px] text-content-tertiary">No open tasks.</li>}
        {tasks.map((t, i) => (
          <li key={i} className="flex items-center gap-3 px-2 py-2.5">
            <span className="tabular grid size-6 shrink-0 place-items-center rounded-md bg-surface-2 font-mono text-[11px] text-content-tertiary">{i + 1}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-medium">{str(t.title, `Task ${str(t.id)}`)}</span>
              <span className="text-xs capitalize text-content-tertiary">{str(t.task_type, "general")} · {str(t.estimated_duration)} {str(t.estimated_duration_unit, "min")}</span>
            </span>
            <Badge tone={priorityMeta(num(t.priority) ?? 3).tone} className="font-mono">P{num(t.priority) ?? 3}</Badge>
          </li>
        ))}
      </ol>
    </Surface>
  );
}

function PlanAccepted({ result }: { result: Rec }) {
  const count = num(result.persisted_count) ?? recs(result.persisted_task_ids).length;
  return (
    <Surface className="border-status-success/30 bg-status-success/[0.05]">
      <p className="flex items-center gap-2 text-sm font-semibold"><CheckCircle2 className="size-4 text-status-success" />Schedule committed</p>
      <p className="mt-1 text-[13px] text-content-secondary">{str(result.executive_summary, "Plan accepted and persisted.")}</p>
      <div className="mt-3 flex items-center gap-3 text-xs">
        <span className="text-content-tertiary">{count} interval(s) saved</span>
        <Link to="/tasks" className="font-medium text-primary hover:underline">View tasks</Link>
      </div>
    </Surface>
  );
}

function Answer({ result }: { result: Rec }) {
  const text = str(result.answer) || str(result.executive_summary) || str(result.message);
  const [open, setOpen] = React.useState(false);
  const details = Object.entries(result).filter(([k, v]) => !["answer", "executive_summary", "message", "success", "errors", "trace", "provenance"].includes(k) && v !== null && v !== undefined && !(Array.isArray(v) && v.length === 0));
  return (
    <Surface>
      {text ? (
        <div className="prose-heliox text-[13.5px] text-content-secondary">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
        </div>
      ) : (
        <p className="text-[13px] text-content-tertiary">JAM completed the request without a narrative summary.</p>
      )}
      {details.length > 0 && (
        <div className="mt-3 border-t border-border-subtle pt-2 dark:border-border">
          <button type="button" onClick={() => setOpen((v) => !v)} className="flex items-center gap-1 text-xs text-content-tertiary hover:text-content-primary" aria-expanded={open}>
            Structured result <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} />
          </button>
          {open && (
            <dl className="mt-2 space-y-2 text-xs">
              {details.map(([k, v]) => (
                <div key={k} className="grid gap-1 sm:grid-cols-[160px_1fr]">
                  <dt className="text-content-tertiary">{humanize(k)}</dt>
                  <dd className="min-w-0 break-words text-content-secondary">
                    {typeof v === "object" ? <pre className="scrollbar-thin max-h-48 overflow-auto rounded-md bg-surface-2 p-2 font-mono text-[11px]">{JSON.stringify(v, null, 2)}</pre> : String(v)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      )}
    </Surface>
  );
}

export function MessageView({ message, onRetry, onRefine, fromHistory }: { message: JamMessage; onRetry?: () => void; onRefine?: (text: string) => void; fromHistory?: boolean }) {
  if (message.role === "user") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8, x: 8 }}
        animate={{ opacity: 1, y: 0, x: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className="flex justify-end"
      >
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary/[0.12] px-4 py-2.5 text-[14px] leading-relaxed text-content-primary shadow-sm transition-all duration-300 hover:bg-primary/[0.15] dark:bg-primary/[0.14] dark:hover:bg-primary/[0.18]">
          <p className="whitespace-pre-wrap">{message.command}</p>
          <p className="mt-1 text-right text-[10px] text-content-muted">{formatLocalTime(message.timestamp)}</p>
        </div>
      </motion.div>
    );
  }

  const result = message.result ?? {};
  const intent = message.intent;
  const isProposal = Array.isArray(result.schedule) && (result.schedule as unknown[]).length > 0 && result.action !== "plan_accepted";
  const isTaskCreated = result.action === "task_created" || (Boolean(result.task) && intent === "create_task");
  const isTaskList = (intent === "list_tasks" || intent === "prioritize_tasks") && (Array.isArray(result.tasks) || Array.isArray(result.prioritized_tasks));
  const isAccepted = result.action === "plan_accepted";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8, x: -8 }}
      animate={{ opacity: 1, y: 0, x: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="flex gap-3"
    >
      <div className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-xl border border-border bg-surface-1 transition-transform duration-300 hover:scale-105">
        <HelioxMark className="size-5" animated={message.isPending} />
      </div>
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex items-center gap-2 text-xs">
          <span className="font-semibold text-content-primary">JAM</span>
          {intent && !message.isPending && <Badge tone="outline">{humanize(intent)}</Badge>}
          <span className="text-content-muted">{formatLocalTime(message.timestamp)}</span>
        </div>
        {message.isError ? (
          (() => {
            const n = normalizeErrorMessage(message.errorMessage, "JAM couldn't complete that command.");
            return (
              <div role="alert" className="flex items-start gap-3 rounded-2xl border border-status-error/25 bg-status-error/[0.06] p-4 transition-all duration-300">
                <OctagonAlert className="mt-0.5 size-4 shrink-0 text-status-error" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{n.title}</p>
                  <p className="mt-0.5 text-[13px] text-content-secondary">{n.explanation}</p>
                  {onRetry && <Button size="xs" variant="secondary" className="mt-2" leftIcon={<RotateCw />} onClick={onRetry}>Retry</Button>}
                </div>
              </div>
            );
          })()
        ) : message.isPending ? (
          <JAMThinkingIndicator />
        ) : isAccepted ? (
          <PlanAccepted result={result} />
        ) : isProposal ? (
          <ProposalCard result={result} onRefine={onRefine} fromHistory={fromHistory} />
        ) : isTaskCreated ? (
          <TaskCreated result={result} />
        ) : isTaskList ? (
          <TaskList result={result} intent={intent} />
        ) : (
          <Answer result={result} />
        )}
      </div>
    </motion.div>
  );
}
