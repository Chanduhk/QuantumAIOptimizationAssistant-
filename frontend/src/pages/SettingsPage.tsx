import * as React from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { KeyRound, LogOut, Monitor, Moon, Palette, PlugZap, Sun, UserRound } from "lucide-react";
import { CURRENT_USER_QUERY_KEY, useCurrentUser, useProviderStatus, useSystemHealth, useTestProvider } from "@/api/hooks";
import { api } from "@/api/endpoints";
import { getApiErrorMessage } from "@/api/client";
import { Page, PageHeader } from "@/components/layout/Page";
import { Card, CardBody, CardHeader, KeyValue } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout, ErrorState, SkeletonRows } from "@/components/ui/Feedback";
import { Segmented } from "@/components/ui/Tabs";
import { useUIStore, type Theme } from "@/stores/uiStore";
import { useUserStore } from "@/stores/userStore";
import { useJamStore } from "@/stores/jamStore";
import { providerState } from "@/lib/status";
import { formatLocalDateTime } from "@/utils/formatters";

export function SettingsPage() {
  const { data: user } = useCurrentUser();
  const provider = useProviderStatus();
  const test = useTestProvider();
  const health = useSystemHealth();
  const { theme, setTheme } = useUIStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setUserId = useUserStore((s) => s.setUserId);
  const [signingOut, setSigningOut] = React.useState(false);
  const info = providerState(provider.data);

  const signOut = async () => {
    setSigningOut(true);
    try {
      await api.auth.logout();
    } catch {
      // Clear locally even if the session already expired.
    }
    setUserId(null);
    useJamStore.getState().clearMessages();
    queryClient.clear();
    queryClient.setQueryData(CURRENT_USER_QUERY_KEY, null);
    navigate("/login", { replace: true });
  };

  return (
    <Page>
      <PageHeader title="Settings" description="Your account, appearance and the language provider behind JAM." />

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader icon={<UserRound />} title="Account" />
          <CardBody className="space-y-5">
            <dl className="grid grid-cols-2 gap-4">
              <KeyValue label="Email" value={user?.email ?? "—"} className="col-span-2" />
              <KeyValue label="User ID" value={user?.id ?? "—"} mono />
              <KeyValue label="Member since" value={user ? formatLocalDateTime(user.created_at) : "—"} />
            </dl>
            <Callout tone="neutral" icon={<KeyRound className="size-4 text-content-tertiary" />}>
              Password reset and multi-factor authentication aren't available in the current API.
            </Callout>
            <Button variant="danger" leftIcon={<LogOut />} isLoading={signingOut} onClick={() => void signOut()}>Sign out</Button>
          </CardBody>
        </Card>

        <Card>
          <CardHeader icon={<Palette />} title="Appearance" description="Theme preference is stored on this device." />
          <CardBody>
            <Segmented<Theme>
              ariaLabel="Theme"
              value={theme}
              onChange={setTheme}
              items={[
                { value: "system", label: "System", icon: <Monitor /> },
                { value: "dark", label: "Dark", icon: <Moon /> },
                { value: "light", label: "Light", icon: <Sun /> },
              ]}
            />
            <div className="mt-5 grid grid-cols-3 gap-2">
              {(["system", "dark", "light"] as Theme[]).map((t) => (
                <button key={t} type="button" onClick={() => setTheme(t)} aria-label={`Use ${t} theme`} className={`overflow-hidden rounded-xl border-2 transition-colors ${theme === t ? "border-primary" : "border-transparent hover:border-border"}`}>
                  <div className={`flex h-16 ${t === "light" ? "bg-[#f8f6f2]" : t === "dark" ? "bg-[#0a0d13]" : "bg-gradient-to-r from-[#f8f6f2] from-50% to-[#0a0d13] to-50%"}`}>
                    <div className="m-2 h-auto w-1/4 rounded bg-[#f5a524]/70" />
                    <div className="my-2 mr-2 flex-1 rounded bg-[#888]/20" />
                  </div>
                </button>
              ))}
            </div>
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader
            icon={<PlugZap />}
            title="Language provider"
            description="JAM uses an LLM for structured extraction when one is reachable, and its deterministic rule-based parser otherwise."
            action={<Badge tone={info.tone} dot size="md">{info.short}</Badge>}
          />
          <CardBody className="space-y-5">
            {provider.isLoading ? <SkeletonRows rows={2} /> : provider.isError ? <ErrorState error={provider.error} onRetry={() => void provider.refetch()} /> : provider.data && (
              <>
                <p className="text-[13px] text-content-secondary">{info.detail}</p>
                <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
                  <KeyValue label="Provider" value={provider.data.provider} />
                  <KeyValue label="Model" value={provider.data.model} mono />
                  <KeyValue label="API key" value={provider.data.has_api_key ? provider.data.masked_key : "Not set"} mono />
                  <KeyValue label="Timeout" value={`${provider.data.timeout_seconds}s`} mono />
                  <KeyValue label="Endpoint" value={provider.data.endpoint} mono className="col-span-2" />
                  <KeyValue label="Status" value={provider.data.status_label} className="col-span-2" />
                </dl>
                {provider.data.last_error && <Callout tone="warning" title={`Last error${provider.data.error_category ? ` (${provider.data.error_category})` : ""}`}>{provider.data.last_error}</Callout>}
                <div className="flex flex-col gap-3 border-t border-border-subtle pt-4 dark:border-border sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs text-content-tertiary">Sends one small live request to verify the key. This may count toward your provider usage.</p>
                  <Button variant="secondary" isLoading={test.isPending} onClick={() => test.mutate()} disabled={!provider.data.has_api_key}>Test connection</Button>
                </div>
                {test.data && (
                  <Callout tone={test.data.success ? "success" : "warning"} title={test.data.success ? "Connection verified" : "Connection failed"}>
                    {test.data.message}{test.data.last_error ? ` — ${test.data.last_error}` : ""}
                  </Callout>
                )}
                {test.isError && <ErrorState error={test.error} title={getApiErrorMessage(test.error)} />}
              </>
            )}
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardBody className="flex flex-wrap items-center justify-between gap-3 text-xs text-content-tertiary">
            <span>HELIOX AI · Quantum-aware personal optimization</span>
            <span>API {health.data?.status ?? "unknown"} · {import.meta.env.VITE_API_URL || "same-origin proxy"}</span>
          </CardBody>
        </Card>
      </div>
    </Page>
  );
}
