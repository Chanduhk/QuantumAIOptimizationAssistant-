import * as React from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { KeyRound, LogOut, Monitor, Moon, Palette, PlugZap, Sun, UserRound } from "lucide-react";
import { CURRENT_USER_QUERY_KEY, useCurrentUser, useProviderStatus, useSystemHealth, useTestProvider } from "@/api/hooks";
import { api } from "@/api/endpoints";
import { Page, PageHeader } from "@/components/layout/Page";
import { Card, CardBody, CardHeader, KeyValue } from "@/components/ui/Card";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout, ErrorState, SkeletonRows } from "@/components/ui/Feedback";
import { Segmented } from "@/components/ui/Tabs";
import { useUIStore, type Theme } from "@/stores/uiStore";
import { useUserStore } from "@/stores/userStore";
import { useJamStore } from "@/stores/jamStore";
import { formatLocalDateTime } from "@/utils/formatters";

const DEFAULT_AI_MODEL_LABEL = "Gemini 3.8 Flash";
const SAFE_MODEL_DISPLAY_NAMES: Record<string, string> = {
  "gemini-3.8-flash": "Gemini 3.8 Flash",
  "gemini-2.5-flash": "Gemini 2.5 Flash",
  "gemini-2.0-flash": "Gemini 2.0 Flash",
  "gemini-1.5-flash": "Gemini 1.5 Flash",
  "gemini-1.5-pro": "Gemini 1.5 Pro",
  "gpt-4o-mini": "GPT-4o mini",
  "gpt-4o": "GPT-4o",
};

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

  const displayModel =
    provider.data?.display_model ||
    (provider.data?.model ? SAFE_MODEL_DISPLAY_NAMES[provider.data.model.toLowerCase()] || DEFAULT_AI_MODEL_LABEL : DEFAULT_AI_MODEL_LABEL);

  let statusLabel = "Not configured";
  let statusTone: BadgeTone = "neutral";

  if (test.data) {
    if (test.data.success) {
      statusLabel = "Verified";
      statusTone = "success";
    } else {
      statusLabel = "Connection failed";
      statusTone = "warning";
    }
  } else if (test.isError) {
    statusLabel = "Connection error";
    statusTone = "error";
  } else if (provider.data?.status?.endsWith("_configured_and_available")) {
    statusLabel = "Verified";
    statusTone = "success";
  } else if (provider.data?.is_configured) {
    statusLabel = "Configured";
    statusTone = "quantum";
  }

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
            title="Language Provider"
            action={<Badge tone={statusTone} dot size="md">{statusLabel}</Badge>}
          />
          <CardBody className="space-y-5">
            {provider.isLoading ? (
              <SkeletonRows rows={2} />
            ) : provider.isError ? (
              <ErrorState error={provider.error} onRetry={() => void provider.refetch()} />
            ) : (
              <>
                <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <KeyValue label="AI Model" value={displayModel} />
                  <KeyValue label="Status" value={statusLabel} />
                </dl>

                <div className="flex flex-col gap-3 border-t border-border-subtle pt-4 dark:border-border sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs text-content-tertiary">
                    Verify model connectivity and availability.
                  </p>
                  <Button
                    variant="secondary"
                    isLoading={test.isPending}
                    onClick={() => test.mutate()}
                    disabled={!provider.data?.is_configured}
                  >
                    Test connection
                  </Button>
                </div>

                {test.data && (
                  <Callout
                    tone={test.data.success ? "success" : "warning"}
                    title={test.data.success ? "Connection verified" : "Connection failed"}
                  >
                    {test.data.message}
                  </Callout>
                )}

                {test.isError && (
                  <Callout tone="error" title="Connection error">
                    Unable to reach the provider service.
                  </Callout>
                )}
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
