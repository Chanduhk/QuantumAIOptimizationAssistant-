import React from "react";
import { useNavigate } from "react-router-dom";
import {
  useSystemHealth,
  useSystemStatus,
  useQuantumStatus,
  useMLModelStatus,
  useTasks,
} from "@/api/hooks";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import {
  MessageSquare,
  CheckSquare,
  Calendar,
  Zap,
  BrainCircuit,
  Database,
  Atom,
  Server,
  Activity,
  Cpu,
  Layers,
  AlertTriangle
} from "lucide-react";

// --- Section A: System Overview ---
function SystemOverview() {
  const { data, isLoading, isError } = useSystemHealth();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">System Health</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">System Health</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-2 text-status-error">
          <AlertTriangle className="h-5 w-5" />
          <span className="text-sm font-medium">Unable to retrieve current health</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center justify-between">
          <span>System Health</span>
          <StatusIndicator status={data.status === "operational" ? "online" : "warning"} />
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="flex justify-between items-center text-sm">
            <span className="text-content-secondary flex items-center gap-2">
              <Server className="h-4 w-4" /> Status
            </span>
            <span className="font-medium capitalize text-content-primary">
              {data.status}
            </span>
          </div>
          <div className="flex justify-between items-center text-sm">
            <span className="text-content-secondary flex items-center gap-2">
              <Database className="h-4 w-4" /> Database
            </span>
            <span className="font-medium text-content-primary">
              {data.database_connected ? "Connected" : "Disconnected"}
            </span>
          </div>
          <div className="flex justify-between items-center text-sm">
            <span className="text-content-secondary">Last Check</span>
            <span className="font-mono text-xs text-content-tertiary">
              {new Date(data.timestamp).toLocaleTimeString()}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// --- Section B: Intelligence Overview ---
function IntelligenceOverview() {
  const { data, isLoading, isError } = useSystemStatus();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Intelligence Metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Intelligence Metrics</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-status-error flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" />
          Unable to retrieve metrics
        </CardContent>
      </Card>
    );
  }

  const metrics = data.ai_metrics || {};
  const metricKeys = Object.keys(metrics);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center justify-between">
          <span>Intelligence Metrics</span>
          <Activity className="h-4 w-4 text-primary" />
        </CardTitle>
      </CardHeader>
      <CardContent>
        {metricKeys.length === 0 ? (
          <p className="text-sm text-content-tertiary">No AI metrics are currently available.</p>
        ) : (
          <div className="space-y-3">
            {metricKeys.map((key) => (
              <div key={key} className="flex justify-between items-center text-sm border-b border-border pb-2 last:border-0 last:pb-0">
                <span className="text-content-secondary capitalize">
                  {key.replace(/_/g, " ")}
                </span>
                <span className="font-mono font-medium text-content-primary">
                  {String(metrics[key])}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// --- Section C: Quantum Capability ---
function QuantumCapability() {
  const { data, isLoading, isError } = useQuantumStatus();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Quantum Capability</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Quantum Capability</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-status-error flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" />
          Unable to retrieve quantum status
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-quantum/20">
      <CardHeader>
        <CardTitle className="text-sm flex items-center justify-between text-quantum">
          <span className="flex items-center gap-2"><Atom className="h-4 w-4" /> Quantum Status</span>
          <Badge variant={data.available ? "quantum" : "default"}>
            {data.available ? "Available" : "Unavailable"}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {!data.direct_execution_exposed && (
            <div className="rounded-md bg-surface-2 p-3 border border-border">
              <p className="text-xs font-medium text-content-primary">Model-based quantum optimization</p>
              <p className="text-xs text-content-secondary mt-1">Direct quantum hardware execution is not exposed through the current API.</p>
            </div>
          )}
          
          {data.config && Object.keys(data.config).length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-content-tertiary uppercase tracking-wider">Configuration</h4>
              {Object.entries(data.config).map(([k, v]) => (
                <div key={k} className="flex justify-between items-center text-xs">
                  <span className="text-content-secondary capitalize">{k.replace(/_/g, " ")}</span>
                  <span className="font-mono text-content-primary">{String(v)}</span>
                </div>
              ))}
            </div>
          )}
          
          {data.qaoa_config && Object.keys(data.qaoa_config).length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-content-tertiary uppercase tracking-wider">QAOA</h4>
              {Object.entries(data.qaoa_config).map(([k, v]) => (
                <div key={k} className="flex justify-between items-center text-xs">
                  <span className="text-content-secondary capitalize">{k.replace(/_/g, " ")}</span>
                  <span className="font-mono text-content-primary">{String(v)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// --- Section D: ML Capability ---
function MLCapability() {
  const { data, isLoading, isError } = useMLModelStatus();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">ML Models</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">ML Models</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-status-error flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" />
          Unable to retrieve ML status
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center justify-between">
          <span className="flex items-center gap-2"><Cpu className="h-4 w-4 text-primary" /> ML Status</span>
          <StatusIndicator status={data.status === "operational" ? "online" : "unknown"} />
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="flex justify-between items-center text-sm">
            <span className="text-content-secondary">Status</span>
            <span className="font-medium text-content-primary capitalize">{data.status}</span>
          </div>
          
          <div className="flex justify-between items-center text-sm">
            <span className="text-content-secondary">Registry</span>
            {data.models_registered === 0 ? (
              <span className="text-content-tertiary italic">No registered models</span>
            ) : (
              <Badge variant="default">{data.models_registered} Models</Badge>
            )}
          </div>
          
          {data.in_memory_only && (
            <div className="flex items-center gap-2 text-xs text-content-tertiary bg-surface-2 p-2 rounded border border-border">
              <Layers className="h-3 w-3" />
              <span>In-memory registry active</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// --- Section E: Task Snapshot ---
function TaskSnapshot() {
  const { data, isLoading, isError } = useTasks();

  if (isLoading) {
    return (
      <Card className="md:col-span-2">
        <CardHeader>
          <CardTitle className="text-sm">Active Tasks</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card className="md:col-span-2">
        <CardHeader>
          <CardTitle className="text-sm">Active Tasks</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-status-error flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" />
          Unable to retrieve tasks for current user.
        </CardContent>
      </Card>
    );
  }

  const tasks = data.tasks || [];

  return (
    <Card className="md:col-span-2">
      <CardHeader>
        <CardTitle className="text-sm flex items-center justify-between">
          <span className="flex items-center gap-2"><CheckSquare className="h-4 w-4 text-primary" /> Active Tasks</span>
          <Badge variant="secondary">{tasks.length}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-6 text-content-tertiary">
            <CheckSquare className="h-8 w-8 mb-2 opacity-20" />
            <p className="text-sm">No active tasks.</p>
          </div>
        ) : (
          <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
            {tasks.slice(0, 5).map((task: any, idx: number) => (
              <div key={task.id || idx} className="flex items-center justify-between p-3 rounded-md bg-surface-2 border border-border hover:-translate-y-[1px] transition-transform">
                <div>
                  <h4 className="text-sm font-medium text-content-primary">{task.title || `Task #${task.id || idx}`}</h4>
                  <p className="text-xs text-content-secondary mt-1">{task.task_type || "Generic"}</p>
                </div>
                <Badge variant={task.status === "completed" ? "success" : "default"}>
                  {task.status || "Unknown"}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// --- Section F: Quick Actions ---
const quickActions = [
  { label: "JAM Assistant", path: "/assistant", icon: MessageSquare },
  { label: "Tasks", path: "/tasks", icon: CheckSquare },
  { label: "Planning", path: "/planning", icon: Calendar },
  { label: "Optimization", path: "/optimization", icon: Zap },
  { label: "Intelligence", path: "/intelligence", icon: BrainCircuit },
  { label: "Data & Learning", path: "/data-learning", icon: Database },
  { label: "Quantum Workspace", path: "/quantum", icon: Atom },
];



function QuickActions() {
  const navigate = useNavigate();

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      {quickActions.map((action) => {
        const Icon = action.icon;
        return (
          <Button
            key={action.path}
            variant="secondary"
            className="h-auto py-4 flex flex-col items-center justify-center gap-2 group"
            onClick={() => navigate(action.path)}
          >
            <Icon className="h-5 w-5 text-content-secondary group-hover:text-primary transition-colors" />
            <span className="text-xs font-medium">{action.label}</span>
          </Button>
        );
      })}
    </div>
  );
}


export function DashboardPage() {
  return (
    <div className="space-y-8 pb-10">
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-bold tracking-tight text-content-primary">HELIOX AI</h2>
        <p className="text-sm text-content-secondary max-w-2xl">
          Intelligence Overview. Mission control for intelligent personal optimization.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <SystemOverview />
        <IntelligenceOverview />
        <QuantumCapability />
        <MLCapability />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <TaskSnapshot />
      </div>

      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-content-primary tracking-wide uppercase">Quick Actions</h3>
        <QuickActions />
      </div>
    </div>
  );
}
