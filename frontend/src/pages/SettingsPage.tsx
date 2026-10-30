import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { getApiErrorMessage } from "@/api/client";
import { useCurrentUser, useMLModelStatus, useQuantumStatus, useSystemHealth, useProviderStatus, useTestProvider } from "@/api/hooks";
import { CURRENT_USER_QUERY_KEY } from "@/api/hooks";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useUserStore } from "@/stores/userStore";
import { useJamStore } from "@/stores/jamStore";
import { useToastStore } from "@/stores/toastStore";
import { Activity, Atom, Database, LogOut, ShieldCheck, SlidersHorizontal, UserRound, Sparkles } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

import { formatStatus } from "@/utils/formatters";

export function SettingsPage() {
  const health = useSystemHealth();
  const { data: user, isLoading: userLoading } = useCurrentUser();
  const model = useMLModelStatus();
  const quantum = useQuantumStatus();
  const { data: providerStatus, refetch: refetchProvider } = useProviderStatus();
  const { mutateAsync: testProvider, isPending: testingProvider } = useTestProvider();
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const setUserId = useUserStore((state) => state.setUserId);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const addToast = useToastStore((state) => state.addToast);
  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState<string | null>(null);

  const modelStatus = formatStatus(model.data?.status ?? (model.isError ? "ERROR" : "UNINITIALIZED"));
  const healthStatus = formatStatus(health.data?.status ?? (health.isError ? "ERROR" : "UNKNOWN"));

  const handleTestConnection = async () => {
    setTestResult(null);
    try {
      const res = await testProvider();
      setTestResult(res);
      addToast({
        type: res.success ? "success" : "warning",
        title: res.success ? "Connection Successful" : "Connection Diagnostic",
        message: res.message,
      });
      void refetchProvider();
    } catch (err) {
      const msg = getApiErrorMessage(err, "Failed to run connection test.");
      setTestResult({ success: false, message: msg });
      addToast({ type: "error", title: "Test Failed", message: msg });
    }
  };

  const signOut = async () => {
    setSigningOut(true);
    setSignOutError(null);
    try {
      await api.auth.logout();
      setUserId(null);
      useJamStore.getState().clearMessages();
      queryClient.clear();
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, null);
      await navigate("/login", { replace: true });
    } catch (error) {
      const message = getApiErrorMessage(error, "Sign out failed.");
      setSignOutError(message);
      addToast({ type: "error", title: "Sign out failed", message });
    } finally {
      setSigningOut(false);
    }
  };

  return (
    <div className="space-y-6 pb-8 sm:space-y-8">
      <header><p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Account · connection · runtime</p><h2 className="mt-2 text-2xl font-bold tracking-tight text-content-primary sm:text-3xl">Settings</h2><p className="mt-2 text-sm text-content-secondary">Session identity and non-sensitive service configuration.</p></header>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card><CardHeader><CardTitle className="flex items-center gap-2"><UserRound className="h-5 w-5 text-primary" />Authenticated account</CardTitle></CardHeader><CardContent className="space-y-4"><div className="flex items-center gap-3 rounded-lg bg-surface-2 p-4"><div className="rounded-full bg-primary/10 p-3 text-primary"><UserRound className="h-5 w-5" /></div><div className="min-w-0"><p className="truncate font-medium text-content-primary">{userLoading ? "Loading account…" : user?.email ?? "Not signed in"}</p><p className="mt-1 text-xs text-content-secondary">{user?.id ? `Account ID ${user.id}` : "Identity not available"}</p></div><Badge variant={user ? "success" : "warning"} className="ml-auto shrink-0">{user ? "Session active" : "Unavailable"}</Badge></div><p className="text-xs leading-relaxed text-content-secondary">Authentication uses the server-managed HttpOnly session cookie. The browser does not store or display a bearer token. Session expiry and revocation are controlled by the backend.</p>{signOutError && <p role="alert" className="text-sm text-status-error">{signOutError}</p>}<Button variant="danger" onClick={signOut} disabled={signingOut || !user} isLoading={signingOut}><LogOut className="mr-2 h-4 w-4" />Sign out safely</Button></CardContent></Card>

        <Card><CardHeader><CardTitle className="flex items-center gap-2"><Activity className="h-5 w-5 text-primary" />API & database service health</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><span className="text-content-secondary">API base URL</span><code className="break-all rounded bg-surface-2 px-2 py-1 text-xs">{API_BASE}</code></div><div className="flex items-center justify-between gap-3"><span className="text-content-secondary">API health</span>{health.isLoading ? <Spinner size="sm" /> : <Badge variant={healthStatus.variant as any}>{healthStatus.label}</Badge>}</div><div className="flex items-center justify-between gap-3"><span className="flex items-center gap-2 text-content-secondary"><Database className="h-4 w-4" />Database via FastAPI</span>{health.data ? <Badge variant={health.data.database_connected ? "success" : "error"}>{health.data.database_connected ? "Connected" : "Disconnected"}</Badge> : <Badge variant="secondary">{health.isError ? "Unavailable" : "Checking"}</Badge>}</div><p className="text-xs text-content-tertiary">Operational API service health confirms backend connectivity, independent of whether AI models have completed training.</p></CardContent></Card>

        <Card><CardHeader><CardTitle className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-primary" />LLM Provider & Assistant Intelligence</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><div className="flex items-center justify-between gap-3"><span className="text-content-secondary">Configured Provider</span><span className="font-medium text-content-primary capitalize">{providerStatus?.provider ?? "OpenAI"}</span></div><div className="flex items-center justify-between gap-3"><span className="text-content-secondary">Target Model</span><code className="rounded bg-surface-2 px-2 py-0.5 text-xs">{providerStatus?.model ?? "gpt-4o-mini"}</code></div><div className="flex items-center justify-between gap-3"><span className="text-content-secondary">API Key Config</span><span className="text-xs text-content-secondary font-mono">{providerStatus?.has_api_key ? providerStatus.masked_key : "Not configured in backend .env"}</span></div><div className="flex items-center justify-between gap-3"><span className="text-content-secondary">Operational Status</span>{providerStatus ? <Badge variant={providerStatus.status === "openai_configured_and_available" ? "success" : providerStatus.status === "openai_rate_limited" ? "warning" : providerStatus.is_configured ? "primary" : "secondary"}>{providerStatus.status_label}</Badge> : <Badge variant="secondary">Checking…</Badge>}</div>{providerStatus?.last_error && <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200"><p className="font-semibold">Provider Notice</p><p className="mt-1">{providerStatus.last_error}</p><p className="mt-1.5 opacity-80">HELIOX is automatically utilizing its local deterministic engine so planning and task operations remain fully functional.</p></div>}{testResult && <div className={`rounded-md border p-3 text-xs ${testResult.success ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200" : "border-amber-500/30 bg-amber-500/10 text-amber-200"}`}><p className="font-semibold">{testResult.success ? "Connection Verified" : "Diagnostic Output"}</p><p className="mt-1">{testResult.message}</p></div>}<div className="pt-2"><Button variant="secondary" size="sm" onClick={handleTestConnection} disabled={testingProvider || !providerStatus?.is_configured} isLoading={testingProvider}>Test Provider Connectivity</Button></div><p className="text-xs text-content-tertiary">API credentials are read securely from the backend environment and never stored or logged in client storage.</p></CardContent></Card>

        <Card><CardHeader><CardTitle className="flex items-center gap-2"><SlidersHorizontal className="h-5 w-5 text-primary" />AI model readiness & registry</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><div className="flex items-center justify-between gap-3"><span className="text-content-secondary">Model registry status</span><Badge variant={modelStatus.variant as any}>{modelStatus.label}</Badge></div><p className="text-xs text-content-secondary">{model.data ? `${model.data.models_registered} registered · ${model.data.in_memory_only ? "in-memory registry" : "persistence active"}` : "Model registry details are not available."}</p><p className="text-xs text-content-tertiary">Service health is distinct from AI model readiness: an operational API can serve heuristic baselines while personalized models await sufficient task data.</p></CardContent></Card>

        <Card><CardHeader><CardTitle className="flex items-center gap-2"><Atom className="h-5 w-5 text-quantum" />Quantum simulation capability</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><div className="flex items-center justify-between gap-3"><span className="text-content-secondary">Simulator configuration</span><Badge variant={quantum.data?.available ? "success" : "warning"}>{quantum.data ? quantum.data.available ? "Available" : "Unavailable" : quantum.isError ? "Unavailable" : "Checking"}</Badge></div>{quantum.data?.qaoa_config && <p className="text-content-secondary">Local QAOA variable limit: <strong>{String(quantum.data.qaoa_config.max_qubits ?? "Not reported")}</strong></p>}<p className="text-xs text-content-tertiary">Local software simulation only. No physical or cloud quantum hardware is used or claimed.</p></CardContent></Card>
      </div>
      <div className="flex items-start gap-2 rounded-lg border border-border bg-surface-2/50 p-4 text-xs leading-relaxed text-content-tertiary"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-status-success" />Sensitive credentials are not displayed here. The CSRF token is used internally by the API client for authenticated state-changing requests.</div>
    </div>
  );
}
