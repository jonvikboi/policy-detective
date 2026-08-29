import React from 'react';
import { ShieldCheck, Terminal, Compass, BookOpen, RefreshCw } from 'lucide-react';

interface NavbarProps {
  onNewScan: () => void;
  activeView: 'landing' | 'investigation' | 'report';
  backendHealthy: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({ onNewScan, activeView, backendHealthy }) => {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Logo and Brand */}
        <div 
          onClick={onNewScan}
          className="flex items-center space-x-3 cursor-pointer group select-none"
        >
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-600 via-brand-500 to-accent-blue p-0.5 shadow-lg shadow-brand-500/20 group-hover:shadow-brand-500/40 transition-all duration-300">
            <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-brand-400 group-hover:scale-110 transition-transform duration-300" />
            </div>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-lg tracking-tight text-white group-hover:text-brand-300 transition-colors">
                Policy Detective
              </span>
              <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-400 border border-brand-500/20">
                Agentic Web
              </span>
            </div>
            <p className="text-xs text-slate-400">Verifiable Policy vs. Reality Auditor</p>
          </div>
        </div>

        {/* Right action & engine badges */}
        <div className="flex items-center space-x-3 sm:space-x-4">
          {/* WebCMD Engine Badge */}
          <div className="hidden md:flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300">
            <Terminal className="w-3.5 h-3.5 text-accent-blue" />
            <span>WebCMD Engine:</span>
            <span className="font-mono text-[11px] text-accent-blue font-medium">Cloak v146</span>
          </div>

          {/* Backend Status Indicator */}
          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-slate-900/90 border border-slate-800/80 text-xs">
            <span className={`w-2 h-2 rounded-full ${backendHealthy ? 'bg-brand-400 animate-pulse' : 'bg-accent-rose'}`} />
            <span className="text-slate-400 hidden sm:inline">
              {backendHealthy ? 'API Active' : 'Connecting...'}
            </span>
          </div>

          {/* New Investigation Button */}
          {activeView !== 'landing' && (
            <button
              onClick={onNewScan}
              className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-slate-950 font-semibold text-xs transition-all shadow-md shadow-brand-500/20 hover:shadow-brand-500/40"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>New Audit</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
