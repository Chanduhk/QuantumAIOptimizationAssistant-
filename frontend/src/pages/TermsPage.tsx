import * as React from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Database,
  ExternalLink,
  Eye,
  FileCheck,
  FileText,
  HelpCircle,
  Info,
  Lock,
  Printer,
  Scale,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Page, PageHeader, SectionTitle } from "@/components/layout/Page";
import { Card, CardBody, CardHeader, CardFooter } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Feedback";
import { Input } from "@/components/ui/Field";
import { FadeIn, StaggerContainer, StaggerItem } from "@/components/motion";
import { cn } from "@/lib/utils";

interface TermsSection {
  id: string;
  number: string;
  title: string;
  summary: string;
  clauses: {
    heading: string;
    body: string;
    bulletPoints?: string[];
    importantNotice?: string;
  }[];
}

const TERMS_SECTIONS: TermsSection[] = [
  {
    id: "acceptance",
    number: "1.0",
    title: "Acceptance of Terms & Eligibility",
    summary:
      "Conditions governing your access to and interaction with the Heliox AI platform.",
    clauses: [
      {
        heading: "1.1 Binding Agreement",
        body:
          "By accessing, registering an account on, or interacting with the Heliox AI platform (the “Service”), you acknowledge that you have read, understood, and agreed to be bound by these Terms and Conditions (the “Terms”). If you do not agree to all terms and conditions set forth herein, you must immediately cease accessing or using the Service.",
      },
      {
        heading: "1.2 Platform Scope & Purpose",
        body:
          "Heliox AI is engineered as the “Quantum AI Personal Optimization Assistant,” designed to assist individual users in task structuring, multi-criteria prioritization, cognitive energy budgeting, and schedule optimization.",
      },
      {
        heading: "1.3 Age & Capacity",
        body:
          "You affirm that you possess the legal capacity to enter into these Terms under the laws of your jurisdiction and are of legal age to form a binding contract.",
      },
    ],
  },
  {
    id: "account-security",
    number: "2.0",
    title: "Account Security & User Responsibilities",
    summary:
      "Requirements for workspace authentication, password complexity, and credential safeguarding.",
    clauses: [
      {
        heading: "2.1 Workspace Isolation & Registration",
        body:
          "Access to your Heliox AI workspace requires an active user account associated with a valid email address and password. Each account creates an isolated workspace within the local relational database.",
        bulletPoints: [
          "Password complexity: You are required to create a password containing at least 12 characters.",
          "Single-user workspaces: Accounts are intended for personal workspace use and may not be shared, rented, or distributed to third parties.",
          "Accurate registration: You agree to provide accurate, current, and complete registration information.",
        ],
      },
      {
        heading: "2.2 Safeguarding Credentials",
        body:
          "You maintain sole responsibility for preserving the confidentiality of your login credentials. You agree to notify administrators immediately of any unauthorized access, session compromise, or suspected security breach in your workspace.",
      },
      {
        heading: "2.3 User Accountability",
        body:
          "You are strictly accountable for all activities, data entries, task definitions, and schedule adjustments executed under your account session.",
      },
    ],
  },
  {
    id: "data-handling",
    number: "3.0",
    title: "Task, Goal & Workspace Data Handling",
    summary:
      "How user tasks, estimates, behavioral feedback, and sessions are stored, handled, and protected.",
    clauses: [
      {
        heading: "3.1 Local Relational Data Storage",
        body:
          "All task records, estimated durations, actual completion times, dependency mappings, goal descriptions, cognitive energy metrics, and subjective feedback ratings are stored within the application's local relational database (SQLite / behavior_engine.db).",
        bulletPoints: [
          "Data Isolation: Task and behavioral feedback tables are scoped by user identity to prevent cross-account data bleeding.",
          "Session Security: Authentication sessions are maintained via encrypted HttpOnly SameSite cookies accompanied by double-submit CSRF verification tokens.",
          "Data Retention: Your task history and behavioral analytics persist locally until explicitly modified or deleted through the platform interface or database administration.",
        ],
      },
      {
        heading: "3.2 No Commercial Monetization or Selling of Data",
        body:
          "Heliox AI does not sell, lease, monetize, or disclose your personal productivity data, task titles, or behavioral ratings to advertising brokers, market research firms, or commercial tracking syndicates.",
      },
      {
        heading: "3.3 AI Model Context Transmission",
        body:
          "When you query the JAM Assistant or invoke cognitive optimization features, relevant task metadata (such as task titles, deadlines, and duration constraints) is transmitted to the configured Google Gemini API (gemini-3.8-flash) solely for the purpose of generating conversational responses and structured plan proposals. API keys and configuration secrets are strictly isolated on the backend server and never sent to your browser.",
        importantNotice:
          "Do not submit sensitive personal identifiers, confidential company trade secrets, or regulated health information within task titles or assistant chat prompts.",
      },
    ],
  },
  {
    id: "ai-disclaimer",
    number: "4.0",
    title: "AI-Generated Recommendations & Advisory Nature",
    summary:
      "Clarification of the advisory role of Gemini 3.8 Flash, the JAM Assistant, and the Executive Brain.",
    clauses: [
      {
        heading: "4.1 Advisory Nature of Recommendations",
        body:
          "All suggestions, priority rankings, duration estimates, risk classifications, and schedule adjustments produced by the JAM Assistant (powered by Gemini 3.8 Flash), the Multi-Criteria Prioritizer (MCDA), or the Executive Cognitive Brain are heuristic recommendations intended solely for personal productivity support.",
        importantNotice:
          "AI recommendations do NOT constitute professional medical, psychological, legal, employment, financial, or certified management advice. You retain sole discretion and accountability for all decisions made or actions taken.",
      },
      {
        heading: "4.2 Human Authority & Oversight",
        body:
          "You maintain final executive control over all tasks, commitments, and schedules. Heliox AI will never irreversibly reschedule or modify tasks without either your direct action or explicit confirmation through structured proposal cards.",
      },
      {
        heading: "4.3 Inherent Limitations of Large Language Models",
        body:
          "While Gemini 3.8 Flash is configured with strict system instructions, probabilistic language models may occasionally generate incomplete, imprecise, or contextually misaligned outputs. You agree to review and verify all generated schedules before relying upon them for mission-critical deadlines.",
      },
    ],
  },
  {
    id: "optimization-disclaimer",
    number: "5.0",
    title: "Optimization Solvers & Heuristics Disclaimers",
    summary:
      "Mathematical scope and practical constraints of classical and quantum-inspired optimization algorithms.",
    clauses: [
      {
        heading: "5.1 Heuristic Approximation",
        body:
          "Heliox AI employs classical constraint satisfaction heuristics, multi-criteria decision matrices, and quantum-inspired combinatorial formulations (including Quadratic Unconstrained Binary Optimization / QUBO and simulated Quantum Approximate Optimization Algorithm / QAOA). These methods compute mathematical approximations under user-defined constraints.",
      },
      {
        heading: "5.2 No Guarantee of Universal Optimality",
        body:
          "Real-world productivity involves dynamic factors beyond algorithmic modeling—including human physiological variations, unplanned interruptions, and external emergencies. Heliox AI does not guarantee that following an optimized schedule will eliminate deadline slippage or ensure academic/professional success.",
      },
      {
        heading: "5.3 Simulated Quantum Computation",
        body:
          "Quantum optimization components within the platform execute via classical numerical simulation of quantum states and variational circuits. They do not claim physical quantum supremacy or execution on physical quantum hardware unless an external quantum processing unit (QPU) provider is specifically configured.",
      },
    ],
  },
  {
    id: "service-availability",
    number: "6.0",
    title: "Service Availability & Fallback Operational Modes",
    summary:
      "Operational availability, provider dependencies, and automated fallback capabilities.",
    clauses: [
      {
        heading: "6.1 “As Is” and “As Available” Provision",
        body:
          "The Service is provided on an “AS IS” and “AS AVAILABLE” basis. To the maximum extent permitted under applicable law, the platform creators disclaim all warranties, express or implied, including warranties of merchantability, fitness for a particular purpose, and non-infringement.",
      },
      {
        heading: "6.2 High-Availability Fallback Architecture",
        body:
          "Heliox AI incorporates deterministic fallback mechanisms. If the primary language provider (Gemini 3.8 Flash) is unreachable due to network disruption or rate limiting, the platform automatically switches to local rule-based intent parsing and deterministic scheduling heuristics. During fallback periods, conversational depth may be reduced while core task operations remain intact.",
      },
      {
        heading: "6.3 Service Maintenance & Downtime",
        body:
          "Administrators reserve the right to perform scheduled or emergency maintenance, database migrations, and software updates that may temporarily interrupt platform availability.",
      },
    ],
  },
  {
    id: "acceptable-use",
    number: "7.0",
    title: "Acceptable Use Policy",
    summary:
      "Standards of conduct and prohibited activities across the application and API interfaces.",
    clauses: [
      {
        heading: "7.1 Prohibited Activities",
        body:
          "You agree that you will not engage in any of the following restricted activities:",
        bulletPoints: [
          "Security Probing: Attempting to bypass, disable, or circumvent authentication controls, CSRF validation, or API rate limiters.",
          "Malicious Injection: Submitting malicious scripts, SQL injections, or prompt injection payloads intended to subvert backend servers or language model safety guardrails.",
          "Unauthorized Access: Accessing or attempting to access other users’ workspaces, relational database files, or administrative endpoints without authorization.",
          "Automated Abuse: Deploying automated scrapers, denial-of-service floods, or unauthorized bots against the platform's API endpoints.",
          "Unlawful Usage: Utilizing the platform for any illegal, harassing, defamatory, fraudulent, or harmful purposes.",
        ],
      },
      {
        heading: "7.2 Right of Account Suspension",
        body:
          "Violation of this Acceptable Use Policy may result in immediate suspension or termination of your account session and revocation of access to the platform.",
      },
    ],
  },
  {
    id: "intellectual-property",
    number: "8.0",
    title: "Intellectual Property & Academic Demonstration",
    summary:
      "Rights, attribution, and academic project designation of Heliox AI.",
    clauses: [
      {
        heading: "8.1 Academic Project Identity",
        body:
          "Heliox AI is developed as the “Quantum AI Personal Optimization Assistant,” an academic and technological demonstration showcasing multi-layered cognitive architectures, hybrid classical-quantum scheduling, and autonomous continuous learning loops.",
      },
      {
        heading: "8.2 Proprietary Code & Design Rights",
        body:
          "All intellectual property rights in the software architecture, user interface designs, custom orbital visual components, multi-criteria decision algorithms, and documentation are reserved by the project authors and copyright holders.",
      },
      {
        heading: "8.3 User Ownership of Task Content",
        body:
          "You retain full ownership and intellectual property rights in all proprietary data, task descriptions, and goal statements you author and enter into your workspace.",
      },
    ],
  },
  {
    id: "liability",
    number: "9.0",
    title: "Limitation of Liability",
    summary:
      "Legal boundaries regarding incidental, consequential, and indirect damages.",
    clauses: [
      {
        heading: "9.1 Cap on Liability",
        body:
          "To the maximum extent permitted by applicable law, in no event shall Heliox AI, its contributors, authors, academic sponsors, or software maintainers be liable for any indirect, incidental, special, consequential, exemplary, or punitive damages whatsoever.",
        bulletPoints: [
          "Missed personal, academic, or professional deadlines or project deliverables.",
          "Loss of productivity, profits, revenue, or business opportunities.",
          "Loss or corruption of task records, estimates, or behavioral analytics data.",
          "Any damages resulting from reliance on AI recommendations or optimization proposals.",
          "Downtime or service unavailability caused by local server issues or third-party AI provider outages.",
        ],
      },
      {
        heading: "9.2 Aggregate Liability Limit",
        body:
          "In any circumstance where liability cannot be fully disclaimed under applicable law, the aggregate liability of the platform creators for any claim arising out of or related to these Terms shall not exceed the amount of fifty US dollars ($50.00 USD) or the amount you paid to access the platform in the preceding twelve months, whichever is lesser.",
      },
    ],
  },
  {
    id: "modifications",
    number: "10.0",
    title: "Modifications to Service & Terms",
    summary:
      "Procedures for policy updates, feature changes, and ongoing governance.",
    clauses: [
      {
        heading: "10.1 Updates to These Terms",
        body:
          "We reserve the right to revise or update these Terms periodically to reflect evolving platform capabilities, new algorithmic models, or regulatory requirements. Any modifications become effective immediately upon publication on this page, with the “Last Updated” date adjusted accordingly.",
      },
      {
        heading: "10.2 Continuous Feature Evolution",
        body:
          "Heliox AI is continuously developed and upgraded. We reserve the right to improve, modify, or deprecate features, algorithms, or API routes as needed to enhance platform performance and security.",
      },
      {
        heading: "10.3 Contact & Queries",
        body:
          "If you have questions, feedback, or inquiries regarding these Terms and Conditions or the platform's operational guidelines, please review the System Status page or contact the platform maintainers through the official repository.",
      },
    ],
  },
];

export function TermsPage() {
  const [searchQuery, setSearchQuery] = React.useState("");
  const [expandedSections, setExpandedSections] = React.useState<Record<string, boolean>>(() => {
    // Default: expand all sections for immediate accessibility
    const initial: Record<string, boolean> = {};
    TERMS_SECTIONS.forEach((s) => {
      initial[s.id] = true;
    });
    return initial;
  });

  const toggleSection = (id: string) => {
    setExpandedSections((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const expandAll = () => {
    const allExpanded: Record<string, boolean> = {};
    TERMS_SECTIONS.forEach((s) => {
      allExpanded[s.id] = true;
    });
    setExpandedSections(allExpanded);
  };

  const collapseAll = () => {
    const allCollapsed: Record<string, boolean> = {};
    TERMS_SECTIONS.forEach((s) => {
      allCollapsed[s.id] = false;
    });
    setExpandedSections(allCollapsed);
  };

  const handlePrint = () => {
    if (typeof window !== "undefined") {
      window.print();
    }
  };

  // Filter sections and clauses by search query
  const filteredSections = React.useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return TERMS_SECTIONS;

    return TERMS_SECTIONS.map((section) => {
      const matchSection =
        section.title.toLowerCase().includes(q) || section.summary.toLowerCase().includes(q);
      const matchingClauses = section.clauses.filter(
        (c) =>
          c.heading.toLowerCase().includes(q) ||
          c.body.toLowerCase().includes(q) ||
          c.bulletPoints?.some((b) => b.toLowerCase().includes(q)) ||
          c.importantNotice?.toLowerCase().includes(q)
      );

      if (matchSection || matchingClauses.length > 0) {
        return {
          ...section,
          clauses: matchSection ? section.clauses : matchingClauses,
        };
      }
      return null;
    }).filter((s): s is TermsSection => s !== null);
  }, [searchQuery]);

  return (
    <Page wide>
      {/* Page Header */}
      <PageHeader
        layers="Governance & Legal Framework"
        title="Terms & Conditions"
        description="Comprehensive operational guidelines, user responsibilities, data privacy standards, and AI advisory disclaimers for Heliox AI."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="neutral" size="md">
              Version 2.4
            </Badge>
            <Badge tone="primary" size="md">
              Last Updated: November 2026
            </Badge>
            <Button
              variant="secondary"
              size="sm"
              leftIcon={<Printer className="size-4" />}
              onClick={handlePrint}
            >
              Print / Save PDF
            </Button>
            <Link to="/about">
              <Button variant="secondary" size="sm" leftIcon={<Info className="size-4" />}>
                About Heliox AI
              </Button>
            </Link>
          </div>
        }
      />

      {/* Summary Banner */}
      <FadeIn delay={0.05} className="mb-8">
        <div className="rounded-2xl border border-border-subtle bg-surface-1 p-5 shadow-card dark:border-border sm:p-6">
          <div className="flex items-start gap-4">
            <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
              <Scale className="size-5" />
            </div>
            <div className="space-y-2">
              <h2 className="text-base font-semibold text-content-primary">
                Executive Legal Summary
              </h2>
              <p className="text-xs leading-relaxed text-content-secondary sm:text-sm">
                These Terms govern your use of <strong>Heliox AI</strong> (the Quantum AI Personal Optimization Assistant).
                All AI-generated recommendations, schedules, and duration estimates produced by <strong>Gemini 3.8 Flash</strong>,
                the Multi-Criteria Prioritizer, and the Executive Brain are <em>strictly advisory</em>. You retain full ownership
                and authority over your tasks, and your productivity data is stored in your isolated database with zero commercial selling.
              </p>
            </div>
          </div>
        </div>
      </FadeIn>

      <div className="grid gap-8 lg:grid-cols-[280px_1fr]">
        {/* Table of Contents / Sidebar Navigator */}
        <aside className="space-y-4">
          <div className="sticky top-20 rounded-2xl border border-border-subtle bg-surface-1 p-4 shadow-card dark:border-border">
            <p className="eyebrow mb-2">Table of Contents</p>

            {/* In-page search */}
            <div className="mb-3">
              <Input
                type="search"
                placeholder="Search clauses..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 text-xs"
              />
            </div>

            {/* Quick action buttons */}
            <div className="mb-3 flex items-center justify-between border-b border-border-subtle pb-2 text-[11px] text-content-muted dark:border-border">
              <button
                type="button"
                onClick={expandAll}
                className="hover:text-content-primary transition-colors"
              >
                Expand all
              </button>
              <span>·</span>
              <button
                type="button"
                onClick={collapseAll}
                className="hover:text-content-primary transition-colors"
              >
                Collapse all
              </button>
            </div>

            <nav aria-label="Table of Contents" className="space-y-1 text-xs">
              {TERMS_SECTIONS.map((sec) => (
                <a
                  key={sec.id}
                  href={`#${sec.id}`}
                  className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-content-tertiary transition-colors hover:bg-surface-2 hover:text-content-primary"
                >
                  <span className="font-mono text-[10px] text-content-muted">{sec.number}</span>
                  <span className="truncate">{sec.title}</span>
                </a>
              ))}
            </nav>

            <div className="mt-4 border-t border-border-subtle pt-3 text-[11px] text-content-muted dark:border-border">
              <p>Platform: Heliox AI</p>
              <p>AI Core: Gemini 3.8 Flash</p>
            </div>
          </div>
        </aside>

        {/* Main Terms Sections */}
        <div className="space-y-6">
          {filteredSections.length === 0 ? (
            <div className="rounded-2xl border border-border-subtle bg-surface-1 p-8 text-center text-content-tertiary dark:border-border">
              <Search className="mx-auto size-6 text-content-muted" />
              <p className="mt-2 text-sm font-medium">No matching clauses found</p>
              <p className="text-xs text-content-muted">Try a different search term like “data”, “AI”, or “password”.</p>
              <Button
                variant="secondary"
                size="sm"
                className="mt-4"
                onClick={() => setSearchQuery("")}
              >
                Clear search
              </Button>
            </div>
          ) : (
            filteredSections.map((section) => {
              const isOpen = expandedSections[section.id] ?? true;
              return (
                <section
                  key={section.id}
                  id={section.id}
                  className="scroll-mt-20 rounded-2xl border border-border-subtle bg-surface-1 shadow-card transition-colors hover:border-border dark:border-border"
                >
                  {/* Section Title & Collapse Trigger */}
                  <button
                    type="button"
                    onClick={() => toggleSection(section.id)}
                    className="flex w-full items-start justify-between gap-4 p-5 text-left transition-colors sm:p-6"
                    aria-expanded={isOpen}
                  >
                    <div>
                      <p className="font-mono text-xs font-semibold text-primary">{section.number}</p>
                      <h2 className="mt-0.5 text-base font-semibold text-content-primary sm:text-lg">
                        {section.title}
                      </h2>
                      <p className="mt-1 text-xs text-content-tertiary sm:text-sm">{section.summary}</p>
                    </div>
                    <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-surface-2 text-content-secondary transition-transform">
                      <ChevronDown
                        className={cn("size-4 transition-transform duration-200", isOpen && "rotate-180")}
                      />
                    </div>
                  </button>

                  {/* Section Content */}
                  <AnimatePresence initial={false}>
                    {isOpen && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.25 }}
                        className="overflow-hidden"
                      >
                        <div className="space-y-5 border-t border-border-subtle p-5 text-sm leading-relaxed text-content-secondary dark:border-border sm:p-6">
                          {section.clauses.map((clause, idx) => (
                            <div key={idx} className="space-y-2">
                              <h3 className="text-sm font-semibold text-content-primary">
                                {clause.heading}
                              </h3>
                              <p className="text-xs text-content-secondary leading-relaxed sm:text-sm">
                                {clause.body}
                              </p>

                              {clause.bulletPoints && (
                                <ul className="mt-2 space-y-1.5 pl-4 text-xs text-content-tertiary sm:text-sm">
                                  {clause.bulletPoints.map((pt, pIdx) => (
                                    <li key={pIdx} className="flex items-start gap-2">
                                      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary/80" />
                                      <span>{pt}</span>
                                    </li>
                                  ))}
                                </ul>
                              )}

                              {clause.importantNotice && (
                                <Callout
                                  tone="warning"
                                  icon={<AlertTriangle className="size-4 text-status-warning" />}
                                  className="mt-3 text-xs"
                                >
                                  {clause.importantNotice}
                                </Callout>
                              )}
                            </div>
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </section>
              );
            })
          )}

          {/* Acknowledgement Card */}
          <div className="rounded-2xl border border-primary/25 bg-primary/[0.04] p-5 text-xs text-content-secondary">
            <div className="flex items-start gap-3">
              <ShieldCheck className="size-5 shrink-0 text-primary" />
              <div>
                <p className="font-semibold text-content-primary">Governance Integrity Commitment</p>
                <p className="mt-1 text-content-tertiary">
                  Heliox AI is engineered to uphold rigorous data privacy, transparent algorithmic decision-making,
                  and clear human executive authority. For questions regarding compliance, security practices, or
                  academic demonstration parameters, consult the{" "}
                  <Link to="/about" className="text-primary hover:underline font-medium">
                    About page
                  </Link>{" "}
                  or the{" "}
                  <Link to="/system" className="text-primary hover:underline font-medium">
                    System Status dashboard
                  </Link>
                  .
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Page>
  );
}
