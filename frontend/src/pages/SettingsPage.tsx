import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useCurrentUser, useSystemHealth } from "@/api/hooks";
import { getApiErrorMessage } from "@/api/client";
import { useUserStore } from "@/stores/userStore";
import { Settings } from "lucide-react";

export function SettingsPage() {
  const { data, isLoading, error } = useSystemHealth();
  const { data: user } = useCurrentUser();
  const userId = useUserStore((state) => state.userId);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-content-primary">System Settings</h2>
        <p className="text-content-secondary">Frontend API connection and current development identity.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Settings className="h-5 w-5" />FastAPI connection</CardTitle></CardHeader>
          <CardContent>
            {isLoading ? <Spinner size="sm" /> : error ? (
              <p role="alert" className="text-status-error">Unavailable: {getApiErrorMessage(error)}</p>
            ) : (
              <div className="space-y-1 text-sm">
                <p>API: <span className="font-medium">{data?.status ?? "Unknown"}</span></p>
                <p>Database via backend: <span className="font-medium">{data?.database_connected ? "Connected" : "Unavailable"}</span></p>
              </div>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Authentication</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p className="font-medium text-emerald-300">Authenticated session active</p>
            <p className="text-content-secondary">Signed in as {user?.email ?? "loading account"}. User identity is resolved from the HttpOnly session cookie ({userId ?? "loading"}).</p>
            <p className="text-content-secondary">Use Sign out in the top bar to revoke this session.</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
