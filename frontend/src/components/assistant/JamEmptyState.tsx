import React from 'react';
import { Sparkles, Activity, LayoutList, GitMerge } from 'lucide-react';

interface JamEmptyStateProps {
  onSuggestionClick: (suggestion: string) => void;
}

export function JamEmptyState({ onSuggestionClick }: JamEmptyStateProps) {
  const suggestions = [
    {
      icon: <LayoutList className="w-5 h-5" />,
      text: "Plan my day around my three most important tasks",
    },
    {
      icon: <Activity className="w-5 h-5" />,
      text: "I have four hours available today. Arrange my pending work.",
    },
    {
      icon: <Sparkles className="w-5 h-5" />,
      text: "Which tasks should I complete first?",
    },
    {
      icon: <GitMerge className="w-5 h-5" />,
      text: "List my pending tasks",
    }
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full w-full max-w-2xl mx-auto px-6 py-12 animate-in fade-in duration-500">
      <div className="mb-8 flex flex-col items-center">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/15 to-quantum/15 border border-border/70 flex items-center justify-center mb-6 shadow-glass">
          <Sparkles className="w-8 h-8 text-primary" />
        </div>
        
        <h1 className="text-3xl font-light tracking-tight text-content-primary mb-2">
          JAM
        </h1>
        <p className="text-content-tertiary text-xs uppercase tracking-widest font-semibold mb-6 text-center">
          Personal Intelligence Assistant
        </p>

        <div className="flex flex-wrap justify-center gap-x-4 gap-y-2 text-sm text-content-secondary font-light mb-8">
          <span>Understand</span>
          <span className="text-content-muted">•</span>
          <span>Plan</span>
          <span className="text-content-muted">•</span>
          <span>Analyze</span>
          <span className="text-content-muted">•</span>
          <span>Optimize</span>
        </div>

        <p className="text-lg text-content-primary font-medium mb-6">
          "How can I help you today?"
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 w-full">
        {suggestions.map((suggestion, idx) => (
          <button
            key={idx}
            onClick={() => onSuggestionClick(suggestion.text)}
            className="flex items-center gap-3.5 p-4 rounded-xl border border-border/70 bg-surface-1/80 hover:bg-surface-2/90 hover:border-primary/40 transition-all duration-200 group text-left shadow-sm"
          >
            <div className="text-content-tertiary group-hover:text-primary transition-colors shrink-0">
              {suggestion.icon}
            </div>
            <span className="text-sm text-content-primary font-medium">
              {suggestion.text}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
