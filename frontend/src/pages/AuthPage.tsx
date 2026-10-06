import { FormEvent, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { getApiErrorMessage } from "@/api/client";
import { CURRENT_USER_QUERY_KEY, useCurrentUser } from "@/api/hooks";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Spinner } from "@/components/ui/Spinner";
import { useUserStore } from "@/stores/userStore";

export function AuthPage() {
  const isSignup = useLocation().pathname === "/signup";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: currentUser, isLoading: checkingSession } = useCurrentUser();
  const setUserId = useUserStore((state) => state.setUserId);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (checkingSession) return <div className="flex min-h-screen items-center justify-center"><Spinner size="lg" /></div>;
  if (currentUser) return <Navigate to="/" replace />;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (isSignup && password.length < 12) {
      setError("Use at least 12 characters for your password.");
      return;
    }
    try {
      setSubmitting(true);
      const session = isSignup
        ? await api.auth.register({ email, password })
        : await api.auth.login({ email, password });
      setUserId(session.user.id);
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, session.user);
      await navigate("/", { replace: true });
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, isSignup ? "Registration failed." : "Login failed."));
    } finally {
      setSubmitting(false);
      setPassword("");
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <p className="text-sm font-bold tracking-wider text-primary">HELIOX AI</p>
          <CardTitle className="text-2xl">{isSignup ? "Create your account" : "Sign in to JAM"}</CardTitle>
          <p className="text-sm text-content-secondary">Your account secures access to your tasks and assistant history.</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <p role="alert" className="rounded-md border border-status-error/20 bg-status-error/10 p-3 text-sm text-status-error">{error}</p>}
            <div className="space-y-1.5">
              <label htmlFor="auth-email" className="text-sm font-medium">Email</label>
              <Input id="auth-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required maxLength={320} disabled={submitting} />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="auth-password" className="text-sm font-medium">Password</label>
              <Input id="auth-password" type="password" autoComplete={isSignup ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} required minLength={12} maxLength={1024} disabled={submitting} />
              {isSignup && <p className="text-xs text-content-tertiary">At least 12 characters.</p>}
            </div>
            <Button className="w-full" type="submit" disabled={submitting} isLoading={submitting}>{isSignup ? "Create account" : "Sign in"}</Button>
          </form>
          <p className="mt-5 text-center text-sm text-content-secondary">
            {isSignup ? "Already registered? " : "New to HELIOX AI? "}
            <Link className="font-medium text-primary hover:underline" to={isSignup ? "/login" : "/signup"}>{isSignup ? "Sign in" : "Create an account"}</Link>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
