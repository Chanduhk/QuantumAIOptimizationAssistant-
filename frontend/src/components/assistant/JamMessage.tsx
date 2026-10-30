import React, { useState } from 'react';
import { 
  AlertCircle, 
  Sparkles, 
  CheckCircle2, 
  Clock, 
  Calendar, 
  Zap, 
  AlertTriangle, 
  Check, 
  ListTodo, 
  ArrowRight,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  X,
  XCircle,
  CornerDownRight,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { JamMessage as JamMessageType } from '@/stores/jamStore';
import { Button } from '@/components/ui/Button';
import { useAcceptPlan, useRejectPlan, useAICommand } from '@/api/hooks';
import { useUserStore } from '@/stores/userStore';
import { normalizeErrorMessage, formatLocalTime } from '@/utils/formatters';

interface JamMessageProps {
  message: JamMessageType;
  onRetry?: () => void;
  onRefine?: (text: string) => void;
}

export function JamMessage({ message, onRetry, onRefine }: JamMessageProps) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="w-full flex justify-end mb-6">
        <div className="max-w-[85%] bg-primary/10 border border-primary/25 rounded-2xl rounded-tr-none px-5 py-4 text-content-primary shadow-sm">
          <p className="whitespace-pre-wrap">{message.command}</p>
          <div className="text-xs text-content-tertiary mt-2 text-right opacity-70">
            {formatLocalTime(message.timestamp)}
          </div>
        </div>
      </div>
    );
  }

  const result = message.result;
  const isScheduleProposal = Boolean(
    result && Array.isArray(result.schedule) && result.schedule.length > 0 &&
    (message.intent === 'plan_day' || message.intent === 'optimize_schedule' || result.schedule)
  );
  const isTaskCreated = Boolean(result && (result.action === 'task_created' || (result.task && message.intent === 'create_task')));
  const isGeneralAnswer = Boolean(result && (result.action === 'general_answer' || result.answer));
  const isTaskList = Boolean(
    result && Array.isArray(result.tasks || result.prioritized_tasks) &&
    (message.intent === 'list_tasks' || message.intent === 'prioritize_tasks')
  );
  const isPlanAccepted = Boolean(result && result.action === 'plan_accepted');

  return (
    <div className="w-full flex justify-start mb-6">
      <div className="max-w-[95%] sm:max-w-[88%] flex gap-4 w-full">
        <div className="flex-shrink-0 mt-1">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary/20 to-quantum/20 border border-primary/30 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-primary" />
          </div>
        </div>
        <div className="flex-1 min-w-0 bg-transparent">
          <div className="text-sm font-medium text-content-tertiary mb-1 flex items-center gap-2">
            <span>JAM</span>
            {message.intent && (
              <span className="px-2 py-0.5 rounded bg-primary/10 border border-primary/25 text-primary text-xs uppercase tracking-wider font-semibold">
                {message.intent.replace(/_/g, ' ')}
              </span>
            )}
          </div>
          
          <div className="text-content-primary">
            {message.isError ? (() => {
              const norm = normalizeErrorMessage(message.errorMessage, "JAM couldn't complete that command.");
              return (
                <div className="flex items-start gap-3 p-4 rounded-xl border border-red-500/20 bg-red-500/5 text-red-400">
                  <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                  <div className="space-y-1.5 w-full">
                    <p className="text-xs font-semibold uppercase tracking-wider">{norm.title}</p>
                    <p className="text-sm text-red-300 leading-relaxed">{norm.explanation}</p>
                    {norm.actionSuggestion && (
                      <p className="text-xs text-red-300/80">Next step: {norm.actionSuggestion}</p>
                    )}
                    {onRetry && (
                      <div className="pt-1">
                        <Button size="sm" variant="secondary" onClick={onRetry}>Retry</Button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })() : message.isPending ? (
              <div role="status" className="p-4 rounded-xl border border-border/70 bg-surface-1/50 text-sm text-content-tertiary flex items-center gap-3">
                <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                <span>JAM is processing: evaluating intelligence models and optimizing plan…</span>
              </div>
            ) : (
              <div className="space-y-4">
                {isPlanAccepted ? (
                  <PlanAcceptedCard result={result!} />
                ) : isScheduleProposal ? (
                  <PlanProposalCard result={result!} onRefine={onRefine} />
                ) : isTaskCreated ? (
                  <TaskCreatedCard result={result!} />
                ) : isTaskList ? (
                  <TaskListCard result={result!} intent={message.intent} />
                ) : isGeneralAnswer ? (
                  <div className="p-4 rounded-xl border border-border/70 bg-surface-1/50 space-y-3">
                    <p className="text-sm text-content-primary leading-relaxed whitespace-pre-wrap">
                      {String(result?.answer || result?.executive_summary || "")}
                    </p>
                    {Boolean(result?.provenance) && (
                      <div className="flex items-center gap-1.5 text-xs text-content-tertiary pt-2 border-t border-border/40">
                        <Sparkles className="w-3.5 h-3.5 text-primary" />
                        <span>Source: {String(result?.provenance).replace(/_/g, ' ')}</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-4 rounded-xl border border-border/70 bg-surface-1/50 space-y-4">
                    {Boolean(result?.executive_summary) && (
                      <p className="text-sm font-medium text-content-primary leading-relaxed">
                        {String(result?.executive_summary)}
                      </p>
                    )}
                    <ResultRenderer result={result} />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function PlanProposalCard({ 
  result, 
  onRefine 
}: { 
  result: Record<string, unknown>; 
  onRefine?: (text: string) => void;
}) {
  const schedule = (result.schedule || []) as Array<Record<string, unknown>>;
  const unscheduledTasks = (result.unscheduled_tasks || []) as Array<Record<string, unknown>>;
  const reasonsForPrioritization = (result.reasons_for_prioritization || []) as string[];
  const tradeOffs = (result.trade_offs || []) as string[];
  const alternativeActions = (result.alternative_actions || []) as string[];
  
  const feasibilityStatus = String(result.feasibility_status || 'FEASIBLE');
  const isFeasible = feasibilityStatus === 'FEASIBLE';
  const demandedHours = Number(result.total_demanded_hours || 0);
  const availableHours = Number(result.available_hours || 8);
  const infeasibleTasks = (result.infeasible_tasks || []) as Array<Record<string, unknown>>;
  const provenance = String(result.behavioral_provenance || 'DETERMINISTIC_FALLBACK');
  const provenanceDetails = String(result.behavioral_details || '');
  const quantumSuitability = String(result.quantum_suitability || 'CLASSICAL_ONLY');
  const executiveSummary = String(result.executive_summary || 'Plan generated using classical optimization baseline.');
  const proposalId = String(result.proposal_id || '');
  const proposalVersion = Number(result.proposal_version || 1);
  const proposalStatus = String(result.proposal_status || 'PROPOSED');
  const parserProvenance = String(result.parser_provenance || (result.provenance as Record<string, unknown> | undefined)?.parser_provenance || 'deterministic_fallback');

  const [accepted, setAccepted] = useState(false);
  const [rejected, setRejected] = useState(false);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const [showRationale, setShowRationale] = useState(true);
  const [refineInput, setRefineInput] = useState('');
  
  const acceptMutation = useAcceptPlan();
  const rejectMutation = useRejectPlan();
  const aiCommand = useAICommand();
  const userId = useUserStore((state) => state.userId);

  const handleAccept = async () => {
    try {
      await acceptMutation.mutateAsync({
        schedule,
        proposal_id: proposalId || undefined,
        version: proposalVersion || undefined,
      });
      setAccepted(true);
    } catch {
      // Error handled by mutation
    }
  };

  const handleReject = async () => {
    try {
      if (proposalId) {
        await rejectMutation.mutateAsync({ proposal_id: proposalId });
      } else if (onRefine) {
        onRefine("Reject plan proposal");
      } else if (userId !== null) {
        await aiCommand.mutateAsync({
          user_id: userId,
          command: "Reject plan proposal",
        });
      }
      setRejected(true);
    } catch {
      // Handled
    }
  };

  const handleRefineSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = refineInput.trim();
    if (!text) return;
    if (onRefine) {
      onRefine(text);
    } else if (userId !== null) {
      aiCommand.mutate({
        user_id: userId,
        command: text,
      });
    }
    setRefineInput('');
  };

  const handleQuickRefine = (instruction: string) => {
    if (onRefine) {
      onRefine(instruction);
    } else if (userId !== null) {
      aiCommand.mutate({
        user_id: userId,
        command: instruction,
      });
    }
  };

  const formatHour = (hourVal: unknown) => {
    if (typeof hourVal !== 'number') return String(hourVal || '00:00');
    const h = Math.floor(hourVal);
    const m = Math.round((hourVal % 1) * 60);
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  };

  const getPriorityBadge = (priority: unknown) => {
    const p = Number(priority || 3);
    if (p >= 5) return 'bg-rose-500/15 text-rose-400 border-rose-500/30';
    if (p === 4) return 'bg-amber-500/15 text-amber-400 border-amber-500/30';
    if (p === 3) return 'bg-primary/15 text-primary border-primary/30';
    return 'bg-slate-500/15 text-slate-400 border-slate-500/30';
  };

  const getProvenanceLabel = (source: unknown) => {
    const s = String(source || '');
    if (s === 'deterministic_parser') return 'Deterministic NL';
    if (s === 'personal_model') return 'Personal Model (ML)';
    if (s === 'historical_pattern') return 'Historical Pattern';
    return 'Heuristic Baseline';
  };

  return (
    <div className="rounded-2xl border border-border/70 bg-surface-1 shadow-lg overflow-hidden transition-all">
      {/* Header Banner */}
      <div className="px-5 py-4 border-b border-border/70 bg-gradient-to-r from-primary/15 via-quantum/10 to-transparent flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Calendar className="w-5 h-5 text-primary" />
          <h3 className="text-sm font-semibold text-content-primary">
            Proposed Execution Plan
          </h3>
          {proposalId && (
            <span className="px-2 py-0.5 rounded bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 text-[11px] font-mono font-medium">
              v{proposalVersion} • {proposalId.slice(0, 8)}
            </span>
          )}
          {parserProvenance.includes('openai') ? (
            <span className="px-2 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-[11px] font-medium">
              OpenAI
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded bg-slate-500/15 border border-slate-500/30 text-slate-300 text-[11px] font-medium">
              Deterministic
            </span>
          )}
          <span className="text-xs text-content-tertiary">
            ({schedule.length} scheduled{unscheduledTasks.length > 0 ? `, ${unscheduledTasks.length} deferred` : ''})
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isFeasible ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Feasible Schedule
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
              <AlertTriangle className="w-3.5 h-3.5" />
              Overload Detected
            </span>
          )}
        </div>
      </div>

      {/* Executive Summary */}
      <div className="px-5 py-3.5 bg-black/10 border-b border-border/70 text-sm text-content-primary leading-relaxed">
        {executiveSummary}
      </div>

      {/* Metrics Row */}
      <div className="px-5 py-3 border-b border-border/70 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div>
          <span className="text-content-tertiary block">Available Horizon</span>
          <span className="font-semibold text-content-primary flex items-center gap-1 mt-0.5">
            <Clock className="w-3 h-3 text-primary" />
            {availableHours.toFixed(1)} hrs
          </span>
        </div>
        <div>
          <span className="text-content-tertiary block">Demanded Workload</span>
          <span className={`font-semibold mt-0.5 block ${demandedHours > availableHours ? 'text-amber-400' : 'text-content-primary'}`}>
            {demandedHours.toFixed(1)} hrs
          </span>
        </div>
        <div>
          <span className="text-content-tertiary block">Optimizer Algorithm</span>
          <span className="font-semibold text-content-primary mt-0.5 block truncate">
            Deterministic EDF + Priority
          </span>
        </div>
        <div>
          <span className="text-content-tertiary block">Behavioral Provenance</span>
          <span className="font-semibold text-primary mt-0.5 block truncate" title={provenanceDetails}>
            {provenance === 'PERSONAL_MODEL' ? 'Personal Model (ML)' : 'Heuristic Gate'}
          </span>
        </div>
      </div>

      {/* Overload Warning Box */}
      {!isFeasible && infeasibleTasks.length > 0 && (
        <div className="m-4 p-4 rounded-xl border border-amber-500/25 bg-amber-500/10 text-xs space-y-2">
          <div className="flex items-center gap-2 font-semibold text-amber-400">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>Capacity Constraint Conflict: {infeasibleTasks.length} task(s) exceed available horizon</span>
          </div>
          <p className="text-content-tertiary">
            The requested workload ({demandedHours.toFixed(1)}h) exceeds your declared working window ({availableHours.toFixed(1)}h).
            The following tasks could not be scheduled within today's window:
          </p>
          <ul className="list-disc list-inside space-y-1 text-amber-300 font-medium pl-1">
            {infeasibleTasks.map((task, i) => (
              <li key={i}>
                {String(task.title || `Task #${task.task_id}`)} (duration: {Number(task.estimated_duration || 1).toFixed(1)}h
                {task.deadline_expression ? `, deadline: ${task.deadline_expression}` : ''})
              </li>
            ))}
          </ul>
          {alternativeActions.length > 0 && (
            <div className="pt-2 border-t border-amber-500/20 text-amber-200">
              <span className="font-semibold block mb-1">Recommended Alternatives:</span>
              <ul className="list-disc list-inside space-y-0.5 text-[11px] opacity-90">
                {alternativeActions.map((alt, i) => (
                  <li key={i}>{alt}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Schedule Items List */}
      <div className="p-4 space-y-2.5">
        <div className="text-xs font-semibold tracking-wider uppercase text-content-tertiary px-1">
          Chronological Task Schedule
        </div>
        <div className="space-y-2.5">
          {schedule.map((item, idx) => {
            const startStr = formatHour(item.scheduled_hour);
            const endStr = formatHour(item.scheduled_end_hour);
            const fits = item.fits_in_horizon !== false;
            const isProposed = item.origin === 'proposed';
            const deadlineExpr = item.deadline_expression || item.deadline;
            const hasDeadlineConflict = item.deadline_feasible === false;

            return (
              <div 
                key={idx}
                className={`p-3.5 rounded-xl border transition-colors space-y-2 ${
                  fits 
                    ? 'border-border/70 bg-surface-2/60 hover:bg-surface-2' 
                    : 'border-amber-500/30 bg-amber-500/5'
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-start sm:items-center gap-3">
                    <div className="flex flex-col items-center justify-center min-w-[76px] px-2.5 py-1.5 rounded-lg bg-surface-1 border border-border/70 text-center">
                      <span className="text-xs font-mono font-bold text-primary">{startStr}</span>
                      <span className="text-[10px] text-content-tertiary leading-none mt-0.5">to {endStr}</span>
                    </div>

                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-content-primary">
                          {String(item.title || `Task #${item.task_id}`)}
                        </span>
                        
                        {/* Origin Badge */}
                        {isProposed ? (
                          <span className="px-2 py-0.5 text-[10px] font-semibold bg-indigo-500/15 text-primary border border-indigo-500/30 rounded-full">
                            Proposed New
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 text-[10px] font-semibold bg-slate-500/15 text-slate-300 border border-slate-500/30 rounded-full">
                            Existing
                          </span>
                        )}

                        {!fits && (
                          <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-amber-500/20 text-amber-400 rounded">
                            Over Horizon
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-2 text-xs text-content-tertiary mt-1">
                        <span className="capitalize">{String(item.task_type || 'general')}</span>
                        <span>•</span>
                        <span>{Number(item.estimated_duration || 1).toFixed(1)} hrs</span>
                        <span>•</span>
                        <span className="text-[11px] opacity-75">
                          {getProvenanceLabel(item.duration_source)}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 sm:self-center">
                    {/* Deadline Badge */}
                    {Boolean(deadlineExpr) && (
                      <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                        hasDeadlineConflict
                          ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                          : 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                      }`}>
                        <Clock className="w-3 h-3" />
                        Due: {String(deadlineExpr)}
                      </span>
                    )}

                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${getPriorityBadge(item.priority)}`}>
                      Priority {Number(item.priority || 3)}
                    </span>
                  </div>
                </div>

                {/* Subtext info: Reason for order, dependencies, deadline warnings */}
                <div className="pt-2 border-t border-border/70/50 flex flex-col gap-1 text-[11px] text-content-tertiary">
                  {Boolean(item.reason_for_order) && (
                    <div className="flex items-center gap-1.5 text-indigo-300/90">
                      <ArrowRight className="w-3 h-3 flex-shrink-0 text-primary" />
                      <span>{String(item.reason_for_order)}</span>
                    </div>
                  )}

                  {Array.isArray(item.dependencies) && item.dependencies.length > 0 && (
                    <div className="flex items-center gap-1 text-slate-400">
                      <span>Prerequisites: Task #{item.dependencies.join(', #')}</span>
                    </div>
                  )}

                  {Boolean(item.deadline_warning) && (
                    <div className="flex items-center gap-1.5 text-rose-400 font-medium">
                      <AlertCircle className="w-3 h-3 flex-shrink-0" />
                      <span>{String(item.deadline_warning)}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Unscheduled Work Section */}
      {unscheduledTasks.length > 0 && (
        <div className="mx-4 mb-4 p-3.5 rounded-xl border border-slate-500/25 bg-slate-500/10 text-xs space-y-2">
          <div className="flex items-center justify-between font-semibold text-slate-300">
            <span className="flex items-center gap-1.5">
              <Clock className="w-4 h-4 text-slate-400" />
              Unscheduled / Deferred Work ({unscheduledTasks.length})
            </span>
            <span className="text-[11px] text-content-tertiary">Outside horizon</span>
          </div>
          <div className="space-y-1.5">
            {unscheduledTasks.map((t, idx) => (
              <div key={idx} className="flex items-center justify-between p-2 rounded-lg bg-surface-1 border border-border/70 text-content-primary">
                <div>
                  <span className="font-medium">{String(t.title)}</span>
                  <span className="text-[11px] text-content-tertiary ml-2">
                    ({Number(t.estimated_duration || 1).toFixed(1)} hrs)
                  </span>
                </div>
                {Boolean(t.deadline_expression) && (
                  <span className="text-[11px] text-amber-300">
                    Due: {String(t.deadline_expression)}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Prioritization Rationale & Trade-offs */}
      {(reasonsForPrioritization.length > 0 || tradeOffs.length > 0) && (
        <div className="px-5 py-3 border-t border-border/70 bg-black/5">
          <button
            type="button"
            onClick={() => setShowRationale(!showRationale)}
            className="w-full flex items-center justify-between text-xs font-semibold text-content-tertiary hover:text-content-primary py-1"
          >
            <span className="flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              Explainable Prioritization & Trade-offs
            </span>
            {showRationale ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>

          {showRationale && (
            <div className="mt-2.5 space-y-2 text-xs text-content-tertiary">
              {reasonsForPrioritization.length > 0 && (
                <div>
                  <span className="font-semibold text-content-primary block mb-1">Ordering Drivers:</span>
                  <ul className="list-disc list-inside space-y-1 pl-1 text-[11px]">
                    {reasonsForPrioritization.map((r, i) => (
                      <li key={i} className="leading-snug">{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {tradeOffs.length > 0 && (
                <div className="pt-1.5">
                  <span className="font-semibold text-content-primary block mb-1">Key Trade-offs:</span>
                  <ul className="list-disc list-inside space-y-1 pl-1 text-[11px] text-amber-300/90">
                    {tradeOffs.map((t, i) => (
                      <li key={i} className="leading-snug">{t}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Conversational Refinement Options */}
      {!accepted && !rejected && (
        <div className="px-5 py-3.5 border-t border-border/70 bg-surface-1/60 space-y-2.5">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-content-tertiary">
            <CornerDownRight className="w-3.5 h-3.5 text-primary" />
            <span>Refine This Schedule Conversationally</span>
          </div>
          
          {/* Quick Refinement Chips */}
          <div className="flex flex-wrap gap-1.5">
            {[
              "I only have two hours available now. Adjust the plan.",
              "Move the assignment ahead of my exam preparation.",
              "Move the assignment first.",
              "Show me another feasible option.",
              "Prioritize the exam instead.",
              "Leave 30 minutes for revision.",
              "Use my existing tasks and goals.",
            ].map((chip, i) => (
              <button
                key={i}
                type="button"
                onClick={() => handleQuickRefine(chip)}
                className="text-[11px] px-2.5 py-1 rounded-lg bg-surface-1 hover:bg-indigo-500/10 border border-border/70 hover:border-indigo-500/30 text-content-tertiary hover:text-indigo-300 transition-all text-left"
              >
                "{chip}"
              </button>
            ))}
          </div>

          {/* Direct Refinement Input */}
          <form onSubmit={handleRefineSubmit} className="flex items-center gap-2 pt-1">
            <input
              type="text"
              value={refineInput}
              onChange={(e) => setRefineInput(e.target.value)}
              placeholder="e.g. Move the exam before the assignment, or add 1h buffer..."
              className="flex-1 bg-surface-2/60 border border-border/70 rounded-xl px-3 py-1.5 text-xs text-content-primary placeholder:text-content-muted focus:outline-none focus:border-primary"
            />
            <Button
              type="submit"
              disabled={!refineInput.trim()}
              className="text-xs px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl disabled:opacity-40"
            >
              Refine
            </Button>
          </form>
        </div>
      )}

      {/* Technical Provenance Toggle */}
      <div className="px-5 py-2.5 bg-black/5 border-t border-border/70">
        <button
          type="button"
          onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
          className="text-xs text-content-tertiary hover:text-content-primary flex items-center gap-1.5 focus:outline-none"
        >
          <ShieldCheck className="w-3.5 h-3.5 text-primary" />
          <span>Governance & Estimation Provenance</span>
          {showTechnicalDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>

        {showTechnicalDetails && (
          <div className="mt-3 p-3 rounded-xl bg-black/20 border border-border/70 text-xs space-y-2 text-content-tertiary">
            <div>
              <span className="font-semibold text-content-primary">Language Understanding: </span>
              {parserProvenance.includes('openai') ? (
                <span className="text-emerald-400 font-medium">OpenAI Structured Interpretation ({parserProvenance})</span>
              ) : (
                <span className="text-slate-300 font-medium">Deterministic Rule-Based Parser (Fallback Active)</span>
              )}
            </div>
            <div>
              <span className="font-semibold text-content-primary">Behavioral Engine: </span>
              {provenanceDetails || provenance}
            </div>
            <div>
              <span className="font-semibold text-content-primary">Quantum Suitability: </span>
              Decision: <code className="text-primary">{quantumSuitability}</code>.
              Classical deterministic optimization retained as authoritative solution.
            </div>
            <div>
              <span className="font-semibold text-content-primary">Interval Guarantee: </span>
              Multi-hour tasks reserved with non-overlapping slot intervals and strict dependency preservation.
            </div>
          </div>
        )}
      </div>

      {/* Card Action Footer */}
      <div className="px-5 py-4 border-t border-border/70 bg-surface-1/80 flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs text-content-tertiary">
          {accepted 
            ? "Plan accepted. Tasks and scheduled intervals written to your database." 
            : rejected 
            ? "Proposal rejected. No tasks or database records were changed."
            : "Review proposed schedule and deadlines before accepting."}
        </div>

        <div className="flex items-center gap-2">
          {accepted ? (
            <div className="flex items-center gap-2 text-emerald-400 font-semibold text-xs px-4 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
              <Check className="w-4 h-4" />
              <span>Plan Accepted & Persisted</span>
            </div>
          ) : rejected ? (
            <div className="flex items-center gap-2 text-rose-400 font-semibold text-xs px-4 py-2 rounded-xl bg-rose-500/10 border border-rose-500/30">
              <X className="w-4 h-4" />
              <span>Proposal Rejected</span>
            </div>
          ) : (
            <>
              <Button
                onClick={handleReject}
                type="button"
                className="bg-transparent hover:bg-rose-500/10 text-rose-300 border border-rose-500/30 text-xs px-4 py-2 rounded-xl transition-all flex items-center gap-1.5"
              >
                <XCircle className="w-3.5 h-3.5 text-rose-400" />
                <span>Reject</span>
              </Button>

              <Button
                onClick={handleAccept}
                disabled={acceptMutation.isPending}
                className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs px-5 py-2 rounded-xl shadow-md transition-all flex items-center gap-2"
              >
                {acceptMutation.isPending ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Persisting Plan…</span>
                  </>
                ) : (
                  <>
                    <Check className="w-4 h-4" />
                    <span>Accept Proposal</span>
                  </>
                )}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function TaskCreatedCard({ result }: { result: Record<string, unknown> }) {
  const task = (result.task || {}) as Record<string, unknown>;
  const title = String(task.title || 'New Task');
  const priority = Number(task.priority || 3);
  const duration = Number(task.estimated_duration || 60);
  const taskType = String(task.task_type || 'general');

  return (
    <div className="p-4 rounded-2xl border border-emerald-500/30 bg-emerald-500/5 shadow-md flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center flex-shrink-0 mt-0.5">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
        </div>
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-emerald-400 mb-0.5">
            Task Created
          </div>
          <h4 className="text-sm font-bold text-content-primary">
            {title}
          </h4>
          <div className="flex items-center gap-3 text-xs text-content-tertiary mt-1">
            <span className="capitalize">{taskType}</span>
            <span>•</span>
            <span>Priority {priority}</span>
            <span>•</span>
            <span>{duration} min</span>
          </div>
        </div>
      </div>

      <div className="self-end sm:self-center">
        <Link 
          to="/tasks"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-emerald-400 hover:text-emerald-300 rounded-lg border border-emerald-500/30 hover:border-emerald-500/50 bg-emerald-500/10 transition-colors"
        >
          <span>View in Tasks</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
}

function TaskListCard({ result, intent }: { result: Record<string, unknown>; intent?: string }) {
  const rawTasks = (result.prioritized_tasks || result.tasks || []) as Array<Record<string, unknown>>;
  const isPrioritized = intent === 'prioritize_tasks' || Boolean(result.prioritized_tasks);
  const summary = String(result.executive_summary || `Found ${rawTasks.length} task(s).`);

  return (
    <div className="rounded-2xl border border-border/70 bg-surface-1 shadow-md overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border/70 flex items-center justify-between gap-3 bg-gradient-to-r from-primary/15 via-quantum/5 to-transparent">
        <div className="flex items-center gap-2">
          <ListTodo className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-semibold text-content-primary">
            {isPrioritized ? 'Prioritized Task Queue' : 'Workspace Pending Tasks'}
          </h3>
          <span className="text-xs text-content-tertiary">
            ({rawTasks.length})
          </span>
        </div>
        <Link 
          to="/tasks"
          className="text-xs text-primary hover:text-primary/80 flex items-center gap-1"
        >
          <span>Manage Tasks</span>
          <ArrowRight className="w-3 h-3" />
        </Link>
      </div>

      <div className="px-5 py-2.5 text-xs text-content-tertiary border-b border-border/70 bg-black/5">
        {summary}
      </div>

      <div className="p-3 divide-y divide-border/60">
        {rawTasks.length === 0 ? (
          <div className="p-4 text-center text-xs text-content-tertiary italic">
            No active tasks found in your workspace.
          </div>
        ) : (
          rawTasks.map((task, i) => (
            <div key={i} className="py-2.5 px-2 flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="w-6 h-6 rounded-full bg-surface-1 border border-border/70 flex items-center justify-center text-xs font-mono font-semibold text-content-tertiary">
                  {i + 1}
                </span>
                <div>
                  <span className="text-sm font-medium text-content-primary block">
                    {String(task.title || `Task #${task.id}`)}
                  </span>
                  <span className="text-xs text-content-tertiary capitalize">
                    {String(task.task_type || 'general')} • {Number(task.estimated_duration || 60)} {String(task.estimated_duration_unit || 'min')}
                  </span>
                </div>
              </div>
              <span className="px-2 py-0.5 text-xs font-semibold rounded bg-primary/15 text-primary border border-primary/30">
                P{Number(task.priority || 3)}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function PlanAcceptedCard({ result }: { result: Record<string, unknown> }) {
  const summary = String(result.executive_summary || 'Plan accepted and persisted.');
  const persistedIds = (result.persisted_task_ids || []) as unknown[];

  return (
    <div className="p-5 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 shadow-lg space-y-3">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
          <Check className="w-5 h-5" />
        </div>
        <div>
          <h4 className="text-sm font-bold text-emerald-400">
            Schedule Committed to Database
          </h4>
          <p className="text-xs text-content-primary mt-0.5">
            {summary}
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between pt-2 border-t border-emerald-500/20 text-xs text-content-tertiary">
        <span>{persistedIds.length} task interval(s) saved</span>
        <div className="flex items-center gap-3">
          <Link to="/tasks" className="text-emerald-400 hover:underline">
            View Tasks
          </Link>
          <Link to="/planning" className="text-emerald-400 hover:underline">
            Open Planning
          </Link>
        </div>
      </div>
    </div>
  );
}

// Fallback recursive renderer for arbitrary structured result data
function ResultRenderer({ result }: { result?: Record<string, unknown> }) {
  if (!result || Object.keys(result).length === 0) {
    return <p className="text-content-tertiary italic text-sm">No result data returned.</p>;
  }

  return (
    <div className="space-y-4 text-sm w-full overflow-hidden">
      {Object.entries(result).map(([key, value]) => (
        <ResultItem key={key} label={key} value={value} />
      ))}
    </div>
  );
}

function ResultItem({ label, value }: { label: string; value: unknown }) {
  const formatLabel = (str: string) => {
    return str.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value === 'boolean') {
    return (
      <div className="flex gap-2">
        <span className="text-content-tertiary font-medium w-1/3 flex-shrink-0">{formatLabel(label)}:</span>
        <span className="text-content-primary">{value ? 'Yes' : 'No'}</span>
      </div>
    );
  }

  if (typeof value === 'string' || typeof value === 'number') {
    return (
      <div className="flex flex-col sm:flex-row sm:gap-2">
        <span className="text-content-tertiary font-medium sm:w-1/3 flex-shrink-0">{formatLabel(label)}:</span>
        <span className="text-content-primary break-words">{value}</span>
      </div>
    );
  }

  if (Array.isArray(value)) {
    return (
      <div className="space-y-2">
        <span className="text-content-tertiary font-medium block">{formatLabel(label)}:</span>
        <ul className="list-disc list-inside space-y-1 pl-2 text-content-primary">
          {value.map((item, idx) => (
            <li key={idx}>
              {typeof item === 'object' && item !== null ? (
                <div className="pl-4 mt-2 mb-2 border-l-2 border-border/70">
                  <ResultRenderer result={item as Record<string, unknown>} />
                </div>
              ) : (
                String(item)
              )}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (typeof value === 'object') {
    return (
      <div className="space-y-2">
        <span className="text-content-tertiary font-medium block">{formatLabel(label)}:</span>
        <div className="pl-4 border-l-2 border-border/70">
          <ResultRenderer result={value as Record<string, unknown>} />
        </div>
      </div>
    );
  }

  return null;
}

