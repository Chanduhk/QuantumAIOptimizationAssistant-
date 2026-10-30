import * as React from "react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface TabsProps {
  tabs: { id: string; label: string; content: React.ReactNode }[];
  defaultTab?: string;
  activeTab?: string;
  onTabChange?: (tabId: string) => void;
  className?: string;
}

export function Tabs({ tabs, defaultTab, activeTab: controlledTab, onTabChange, className }: TabsProps) {
  const [internalTab, setInternalTab] = React.useState(defaultTab || tabs[0]?.id);
  const activeTab = controlledTab ?? internalTab;

  const activeContent = React.useMemo(() => {
    return tabs.find((t) => t.id === activeTab)?.content || null;
  }, [tabs, activeTab]);

  return (
    <div className={cn("w-full", className)}>
      <div className="flex w-full items-center border-b border-border mb-4 overflow-x-auto scrollbar-hide">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => { if (controlledTab === undefined) setInternalTab(tab.id); onTabChange?.(tab.id); }}
              className={cn(
                "relative px-4 py-3 text-sm font-medium transition-colors focus:outline-none whitespace-nowrap",
                isActive ? "text-primary" : "text-content-secondary hover:text-content-primary"
              )}
            >
              {tab.label}
              {isActive && (
                <motion.div
                  layoutId="active-tab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary"
                  initial={false}
                  transition={{ type: "spring", stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          );
        })}
      </div>
      <div className="mt-2 outline-none" tabIndex={0}>
        {activeContent}
      </div>
    </div>
  );
}
