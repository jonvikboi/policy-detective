import React from 'react';
import { ShieldCheck, Terminal, Heart } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer className="border-t border-slate-850 bg-slate-950/80 mt-16 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-4">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-slate-400">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-brand-400" />
            <span className="font-semibold text-slate-200">Policy Detective</span>
            <span>—</span>
            <span>Autonomous Web Compliance & Privacy Policy Auditor</span>
          </div>

          <div className="flex items-center space-x-4">
            <span className="flex items-center space-x-1">
              <Terminal className="w-3.5 h-3.5 text-accent-blue" />
              <span>WebCMD v0.7.4 Engine</span>
            </span>
            <span>•</span>
            <span>QuickJS Sandbox</span>
            <span>•</span>
            <span>CloakBrowser Stealth Chromium</span>
          </div>
        </div>

        <p className="text-[11px] text-slate-400 leading-relaxed text-center md:text-left">
          <strong>Notice:</strong> Policy Detective provides technical observations and policy alignment analysis. Findings indicate potential technical deviations between stated disclosures and observable client-side telemetry. Results do not constitute definitive legal determinations.
        </p>
      </div>
    </footer>
  );
};
