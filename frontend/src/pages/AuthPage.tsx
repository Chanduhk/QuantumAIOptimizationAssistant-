import { FormEvent, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Atom, BrainCircuit, Eye, EyeOff, GraduationCap, Workflow } from "lucide-react";
import { api } from "@/api/endpoints";
import { getApiErrorMessage } from "@/api/client";
import { CURRENT_USER_QUERY_KEY, useCurrentUser } from "@/api/hooks";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Spinner } from "@/components/ui/Feedback";
import { HelioxWordmark } from "@/components/brand/HelioxMark";
import { OrbitalSystem } from "@/components/brand/OrbitalSystem";
import { useUserStore } from "@/stores/userStore";

const PILLARS = [
  { icon: BrainCircuit, title: "Understands your work", text: "Natural-language planning, behaviour patterns and duration predictions." },
  { icon: Workflow, title: "Optimizes honestly", text: "Classical scheduling first; quantum (QAOA) only when the problem actually fits." },
  { icon: Atom, title: "Explains every decision", text: "Evidence, risk and trade-offs from the Executive Cognitive Brain." },
  { icon: GraduationCap, title: "Learns from outcomes", text: "Your real results and ratings train personal models over time." },
];

export function AuthPage() {
  const isSignup = useLocation().pathname === "/signup";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: currentUser, isLoading: checkingSession } = useCurrentUser();
  const setUserId = useUserStore((state) => state.setUserId);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (checkingSession) return <div className="grid min-h-dvh place-items-center bg-background"><Spinner size="lg" /></div>;
  if (currentUser) return <Navigate to="/" replace />;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!email.trim()) return setError("Enter your email address.");
    if (isSignup && password.length < 12) return setError("Use at least 12 characters for your password.");
    try {
      setSubmitting(true);
      const session = isSignup ? await api.auth.register({ email: email.trim(), password }) : await api.auth.login({ email: email.trim(), password });
      setUserId(session.user.id);
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, session.user);
      await navigate("/", { replace: true });
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, isSignup ? "Registration failed." : "Login failed."));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid min-h-dvh bg-background lg:grid-cols-[1.05fr_1fr]">
      {/* Brand panel */}
      <section className="relative hidden overflow-hidden border-r border-border bg-surface-1 lg:flex lg:flex-col dark:bg-surface-1/40">
        <div className="bg-grid absolute inset-0 opacity-60 [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]" />
        <div className="relative z-10 p-10">
          <HelioxWordmark />
        </div>
        <div className="relative z-10 flex flex-1 items-center justify-center">
          <OrbitalSystem className="w-[min(420px,80%)]" />
        </div>
        <div className="relative z-10 grid grid-cols-2 gap-x-8 gap-y-6 p-10 pt-0">
          {PILLARS.map((p, i) => (
            <motion.div key={p.title} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 + i * 0.07 }}>
              <p.icon className="mb-2 size-4 text-primary" />
              <p className="text-sm font-medium text-content-primary">{p.title}</p>
              <p className="mt-1 text-[13px] leading-relaxed text-content-tertiary">{p.text}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Form */}
      <section className="flex flex-col px-5 py-8 sm:px-10">
        <div className="lg:hidden">
          <HelioxWordmark />
        </div>
        <div className="flex flex-1 items-center justify-center py-10">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="w-full max-w-sm">
            <h1 className="text-[28px] font-semibold tracking-[-0.02em]">{isSignup ? "Create your workspace" : "Welcome back"}</h1>
            <p className="mt-2 text-sm text-content-tertiary">
              {isSignup ? "Your tasks, outcomes and models stay isolated to your account." : "Sign in to continue optimizing your day."}
            </p>

            <form onSubmit={handleSubmit} className="mt-8 space-y-4" noValidate>
              <Field label="Email" htmlFor="auth-email">
                <Input id="auth-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required disabled={submitting} className="h-10" />
              </Field>
              <Field label="Password" htmlFor="auth-password" hint={isSignup ? "At least 12 characters." : undefined}>
                <div className="relative">
                  <Input
                    id="auth-password"
                    type={showPassword ? "text" : "password"}
                    autoComplete={isSignup ? "new-password" : "current-password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={isSignup ? 12 : undefined}
                    disabled={submitting}
                    className="h-10 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="absolute right-1.5 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-md text-content-muted hover:text-content-primary"
                  >
                    {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </Field>
              {error && <p role="alert" className="rounded-lg border border-status-error/25 bg-status-error/[0.06] px-3 py-2 text-[13px] text-status-error">{error}</p>}
              <Button type="submit" size="lg" className="w-full" isLoading={submitting}>
                {isSignup ? "Create account" : "Sign in"}
              </Button>
            </form>

            <p className="mt-6 text-center text-sm text-content-tertiary">
              {isSignup ? "Already have an account?" : "New to HELIOX?"}{" "}
              <Link to={isSignup ? "/login" : "/signup"} className="font-medium text-primary hover:underline">
                {isSignup ? "Sign in" : "Create an account"}
              </Link>
            </p>
          </motion.div>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-center text-xs text-content-muted">
          <span>HttpOnly & CSRF Protected</span>
          <span>·</span>
          <Link to="/about" className="hover:text-content-secondary transition-colors">About Heliox AI</Link>
          <span>·</span>
          <Link to="/terms" className="hover:text-content-secondary transition-colors">Terms & Conditions</Link>
        </div>
      </section>
    </div>
  );
}
