import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { api, type DecisionPipelineResponse } from "@/api/endpoints";
import { getApiErrorMessage } from "@/api/client";
import { useUserStore } from "@/stores/userStore";
import { Brain, Calendar, Target, Clock, Zap } from "lucide-react";

function textField(value: unknown, fallback = "—"): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : fallback;
}

function numberField(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

export function PlanningPage() {
  const userId = useUserStore((state) => state.userId);
  const [planRequested, setPlanRequested] = useState(false);
  const { data: plan, isLoading, isFetching, error, refetch } = useQuery<DecisionPipelineResponse>({
    queryKey: ["planning", userId],
    queryFn: () => {
      if (userId === null) throw new Error("Sign in to generate a plan.");
      return api.ai.runDecisionPipeline({ user_id: userId, goal: "plan my day", days_back: 90 });
    },
    enabled: planRequested && userId !== null,
    retry: false,
    refetchOnWindowFocus: false,
  });

  const handleGeneratePlan = async () => {
    if (userId === null) {
      return;
    }
    if (!planRequested) setPlanRequested(true);
    else await refetch();
  };

  const tasks = plan?.tasks ?? [];
  const schedule = plan?.schedule ?? [];
  const predictions = plan?.predictions ?? [];

  return (
    <div className="space-y-6 h-full flex flex-col">
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-content-primary">Strategic Planning</h2>
          <p className="text-content-secondary">Executive orchestration and adaptive scheduling workspace.</p>
        </div>
        <Button onClick={handleGeneratePlan} disabled={isFetching || userId === null} className="gap-2">
          {isFetching ? <Spinner size="sm" /> : <Brain className="w-4 h-4" />}
          {plan ? "Refresh Plan" : "Generate Plan"}
        </Button>
      </div>

      {userId === null && (
        <Card role="alert" className="border-red-500/20 bg-red-500/10 shrink-0">
          <CardContent className="p-4 text-red-400">Sign in to generate a user-specific plan.</CardContent>
        </Card>
      )}

      {error && (
        <Card role="alert" className="border-red-500/20 bg-red-500/10 shrink-0">
          <CardContent className="p-4 text-red-400">{getApiErrorMessage(error, "Failed to generate a plan.")}</CardContent>
        </Card>
      )}

      {!plan && !isLoading && !error ? (
        <Card className="flex-1 flex flex-col items-center justify-center border-dashed">
          <CardContent className="flex flex-col items-center gap-4 py-12 text-center text-content-secondary">
            <Calendar className="w-12 h-12 text-content-tertiary" />
            <div className="space-y-1">
              <h3 className="text-lg font-medium text-content-primary">No Active Plan</h3>
              <p>Generate a plan using the existing FastAPI decision pipeline.</p>
            </div>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <div className="flex min-h-64 items-center justify-center"><Spinner size="lg" /></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 flex-1 min-h-0">
          <Card className="flex flex-col min-h-0">
            <CardHeader className="pb-3 shrink-0"><CardTitle className="text-lg flex items-center gap-2"><Target className="w-5 h-5 text-primary-500" />Backlog</CardTitle></CardHeader>
            <CardContent className="flex-1 overflow-y-auto space-y-3">
              {tasks.length === 0 ? <p className="text-sm text-content-secondary">No tasks returned.</p> : tasks.map((task, idx) => (
                <div key={textField(task.id, String(idx))} className="p-3 rounded-md bg-background-tertiary/50 border border-border-primary">
                  <div className="font-medium text-content-primary mb-1">{textField(task.title)}</div>
                  <div className="flex items-center justify-between text-xs text-content-secondary">
                    <Badge variant="outline" className="capitalize">{textField(task.task_type)}</Badge>
                    <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{textField(task.estimated_duration)} {textField(task.estimated_duration_unit, "unit unspecified")}</span>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="flex flex-col min-h-0">
            <CardHeader className="pb-3 shrink-0"><CardTitle className="text-lg flex items-center gap-2"><Calendar className="w-5 h-5 text-primary-500" />AI Timeline</CardTitle></CardHeader>
            <CardContent className="flex-1 overflow-y-auto space-y-4">
              {schedule.length === 0 ? <p className="text-sm text-content-secondary">No schedule returned.</p> : schedule.map((item, idx) => {
                const start = numberField(item.scheduled_hour);
                const end = numberField(item.scheduled_end_hour);
                return (
                  <div key={textField(item.task_id, String(idx))} className="relative pl-6 pb-4 last:pb-0">
                    <div className="absolute left-1.5 top-1 bottom-0 w-px bg-border-primary" />
                    <div className="absolute left-0 top-1 w-3 h-3 rounded-full bg-primary-500 ring-4 ring-background-secondary" />
                    <div className="text-sm font-medium text-primary-400 mb-1">{start === undefined ? "Time unavailable" : `${start}:00`}{end === undefined ? "" : ` - ${end}:00`}</div>
                    <div className="p-3 rounded-md bg-background-tertiary/50 border border-border-primary">
                      <div className="font-medium text-content-primary mb-1">{textField(item.title)}</div>
                      <div className="text-xs text-content-secondary flex justify-between items-center">
                        <span>Priority {textField(item.priority)}</span>
                        {item.is_locked === true && <Badge variant="default" className="text-[10px] h-4">Locked</Badge>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>

          <Card className="flex flex-col min-h-0">
            <CardHeader className="pb-3 shrink-0"><CardTitle className="text-lg flex items-center gap-2"><Brain className="w-5 h-5 text-primary-500" />Intelligence</CardTitle></CardHeader>
            <CardContent className="flex-1 overflow-y-auto space-y-3">
              {predictions.length === 0 ? <p className="text-sm text-content-secondary">No predictions returned.</p> : predictions.map((prediction, idx) => {
                const productivity = numberField(prediction.predicted_productivity);
                return (
                  <div key={textField(prediction.task_id, String(idx))} className="p-3 rounded-md bg-primary-500/5 border border-primary-500/20">
                    <div className="font-medium text-content-primary mb-2 truncate" title={textField(prediction.title)}>{textField(prediction.title)}</div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-content-secondary flex items-center gap-1"><Zap className="w-4 h-4 text-yellow-500" />Predicted Focus</span>
                      <span className="font-mono font-medium text-primary-400">{productivity === undefined ? "Unavailable" : `${productivity.toFixed(1)}%`}</span>
                    </div>
                    {typeof prediction.reasoning === "string" && <div className="mt-2 text-xs text-content-tertiary italic">“{prediction.reasoning}”</div>}
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
