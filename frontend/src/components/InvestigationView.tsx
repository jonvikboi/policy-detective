import React, { useState, useEffect, useRef } from 'react';
import { 
  CheckCircle2, 
  Circle, 
  Loader2, 
  Terminal, 
  FileText, 
  Layers, 
  ShieldAlert, 
  ArrowRight,
  Database,
  Globe,
  Radio,
  ExternalLink,
  ChevronDown
} from 'lucide-react';
import { Scan, ScanEvent } from '../types';

interface InvestigationViewProps {
  scan: Scan;
  events: ScanEvent[];
  onViewReport: () => void;
  onCancelScan?: () => void;
}

const STAGES = [
  { id: 'discovering_policies', label: 'Policy Discovery', icon: FileText, desc: 'Discovering privacy & cookie policies' },
  { id: 'extracting_claims', label: 'Claim Extraction', icon: Terminal, desc: 'Extracting testable policy commitments' },
  { id: 'pre_consent_experiment', label: 'Pre-Consent Audit', icon: Layers, desc: 'Capturing baseline cookies & network calls' },
  { id: 'accept_experiment', label: 'Accept-All Audit', icon: Layers, desc: 'Simulating consent approval & tracking activation' },
  { id: 'reject_experiment', label: 'Reject-All Audit', icon: Layers, desc: 'Simulating consent rejection & enforcement' },
  { id: 'analyzing_evidence', label: 'Evidence Analysis', icon: Database, desc: 'Classifying trackers & diffing observations' },
  { id: 'generating_verdicts', label: 'Verdict Generation', icon: ShieldAlert, desc: 'Computing evidence-backed verdicts' },
];

export const InvestigationView: React.FC<InvestigationViewProps> = ({
  scan,
  events,
  onViewReport,
}) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  const isCompleted = scan.status === 'completed';
  const isFailed = scan.status === 'failed';

  // Determine stage status
  const getStageStatus = (stageId: string, index: number) => {
    if (isCompleted) return 'completed';
    if (isFailed) return 'failed';

    const stageOrder = STAGES.map(s => s.id);
    const currentIndex = stageOrder.indexOf(scan.current_stage);

    if (currentIndex === -1) {
      return index === 0 ? 'active' : 'pending';
    }

    if (index < currentIndex) return 'completed';
    if (index === currentIndex) return 'active';
    return 'pending';
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Target Site Header */}
      <div className="glass-panel rounded-2xl p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border border-slate-800">
        <div className="space-y-1">
          <div className="flex items-center space-x-2 text-xs font-mono text-slate-400">
            <span>AUDIT TARGET</span>
            <span>•</span>
            <span className="text-brand-400">{scan.domain}</span>
          </div>
          <h2 className="text-xl sm:text-2xl font-bold text-white flex items-center space-x-2">
            <span>{scan.url}</span>
            <a 
              href={scan.url} 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-slate-500 hover:text-slate-300"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
          </h2>
        </div>

        <div className="flex items-center space-x-3">
          {isCompleted ? (
            <button
              onClick={onViewReport}
              className="px-5 py-2.5 rounded-xl bg-brand-500 hover:bg-brand-400 text-slate-950 font-bold text-sm flex items-center space-x-2 shadow-lg shadow-brand-500/20 transition-all"
            >
              <span>View Full Report</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          ) : isFailed ? (
            <div className="px-4 py-2 rounded-xl bg-accent-rose/10 border border-accent-rose/30 text-accent-rose text-sm font-semibold flex items-center space-x-2">
              <ShieldAlert className="w-4 h-4" />
              <span>Investigation Stopped</span>
            </div>
          ) : (
            <div className="px-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-brand-400 text-xs font-mono flex items-center space-x-2">
              <Radio className="w-3.5 h-3.5 animate-pulse text-brand-400" />
              <span>Investigation in Progress</span>
            </div>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="glass-panel rounded-xl p-5 space-y-3 border border-slate-800">
        <div className="flex justify-between items-center text-xs">
          <div className="flex items-center space-x-2">
            <span className="text-slate-400">Current Phase:</span>
            <span className="font-semibold text-white capitalize">
              {scan.stage_details || scan.current_stage.replace(/_/g, ' ')}
            </span>
          </div>
          <span className="font-mono text-brand-400 font-bold">{Math.round(scan.progress)}%</span>
        </div>
        <div className="w-full bg-slate-900 rounded-full h-2.5 overflow-hidden border border-slate-800">
          <div 
            className="bg-gradient-to-r from-brand-500 to-accent-blue h-full rounded-full transition-all duration-500 ease-out"
            style={{ width: `${Math.max(5, scan.progress)}%` }}
          />
        </div>
      </div>

      {/* Completion Banner */}
      {isCompleted && (
        <div className="glass-panel rounded-2xl p-5 border border-brand-500/40 bg-brand-500/10 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-xl shadow-brand-500/10 animate-fade-in">
          <div className="flex items-center space-x-4">
            <div className="w-10 h-10 rounded-xl bg-brand-500/20 border border-brand-500/40 flex items-center justify-center text-brand-400">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div>
              <h4 className="text-base font-bold text-white">Investigation Complete!</h4>
              <p className="text-xs text-slate-300">Differential evidence analysis and verdicts compiled.</p>
            </div>
          </div>
          <button
            onClick={onViewReport}
            className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-brand-500 hover:bg-brand-400 text-slate-950 font-bold text-sm flex items-center justify-center space-x-2 shadow-lg shadow-brand-500/25 transition-all hover:scale-[1.02] cursor-pointer"
          >
            <span>View Full Audit Report</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Main Grid: Stages Stepper + Live Console */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Stages Stepper */}
        <div className="lg:col-span-5 space-y-3">
          <div className="glass-panel rounded-2xl p-5 border border-slate-800 space-y-4">
            <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider font-mono">
              Investigation Workflow
            </h3>

            <div className="space-y-2">
              {STAGES.map((stage, idx) => {
                const status = getStageStatus(stage.id, idx);
                const Icon = stage.icon;

                return (
                  <div
                    key={stage.id}
                    className={`p-3 rounded-xl border transition-all flex items-start space-x-3 ${
                      status === 'active'
                        ? 'bg-brand-500/10 border-brand-500/40 text-white shadow-md shadow-brand-500/5'
                        : status === 'completed'
                        ? 'bg-slate-900/60 border-slate-800 text-slate-300'
                        : 'bg-slate-950/40 border-slate-900 text-slate-500 opacity-60'
                    }`}
                  >
                    <div className="mt-0.5">
                      {status === 'completed' ? (
                        <CheckCircle2 className="w-4 h-4 text-brand-400" />
                      ) : status === 'active' ? (
                        <Loader2 className="w-4 h-4 text-brand-400 animate-spin" />
                      ) : (
                        <Circle className="w-4 h-4 text-slate-600" />
                      )}
                    </div>
                    <div>
                      <h4 className="text-xs font-semibold">{stage.label}</h4>
                      <p className="text-[11px] text-slate-400 mt-0.5">{stage.desc}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right: Live Terminal */}
        <div className="lg:col-span-7">
          <div className="glass-panel rounded-2xl p-5 border border-slate-800 flex flex-col h-[520px]">
            <div className="flex justify-between items-center pb-3 border-b border-slate-800">
              <div className="flex items-center space-x-2 text-xs font-mono text-slate-300">
                <Terminal className="w-4 h-4 text-brand-400" />
                <span>Agent Telemetry & Event Stream</span>
              </div>
              <button
                onClick={() => setAutoScroll(!autoScroll)}
                className={`text-[11px] font-mono px-2.5 py-1 rounded-md border ${
                  autoScroll 
                    ? 'bg-slate-800 border-slate-700 text-brand-400' 
                    : 'bg-slate-900 border-slate-800 text-slate-500'
                }`}
              >
                Auto-scroll: {autoScroll ? 'ON' : 'OFF'}
              </button>
            </div>

            <div 
              ref={terminalRef}
              className="flex-1 overflow-y-auto font-mono text-xs space-y-3 p-3 bg-slate-950/80 rounded-xl border border-slate-900 mt-3 scrollbar-thin scrollbar-thumb-slate-800"
            >
              {events.length === 0 ? (
                <div className="text-slate-600 italic">Waiting for agent events...</div>
              ) : (
                events.map((ev, i) => (
                  <div key={i} className="space-y-1 animate-fade-in">
                    <div className="flex items-center space-x-2 text-slate-500 text-[10px]">
                      <span>{new Date(ev.timestamp).toLocaleTimeString()}</span>
                      <span className={`px-1.5 py-0.5 rounded text-[9px] uppercase font-bold tracking-wider ${
                        ev.type === 'stage_change' 
                          ? 'bg-accent-blue/10 text-accent-blue border border-accent-blue/20'
                          : ev.type === 'policy_found'
                          ? 'bg-brand-500/10 text-brand-400 border border-brand-500/20'
                          : ev.type === 'claims_extracted'
                          ? 'bg-accent-purple/10 text-accent-purple border border-accent-purple/20'
                          : ev.type === 'consent_interaction'
                          ? 'bg-accent-amber/10 text-accent-amber border border-accent-amber/20'
                          : ev.type === 'error'
                          ? 'bg-accent-rose/10 text-accent-rose border border-accent-rose/20'
                          : 'bg-slate-800 text-slate-400'
                      }`}>
                        {ev.type.replace(/_/g, ' ')}
                      </span>
                    </div>

                    <p className="text-slate-200 pl-2 border-l border-slate-800">
                      {typeof ev.data === 'string' 
                        ? ev.data 
                        : ev.data?.message || JSON.stringify(ev.data)}
                    </p>
                  </div>
                ))
              )}

              {isCompleted && (
                <div className="pt-3 mt-2 text-brand-400 font-bold border-t border-slate-800/80 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-brand-500/10 p-3 rounded-xl border border-brand-500/30">
                  <div className="flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-brand-400" />
                    <span className="text-white">Investigation complete. Final report compiled.</span>
                  </div>
                  <button
                    onClick={onViewReport}
                    className="px-4 py-1.5 rounded-lg bg-brand-500 hover:bg-brand-400 text-slate-950 font-bold text-xs flex items-center space-x-1.5 transition-all cursor-pointer shadow-md shadow-brand-500/20"
                  >
                    <span>View Report</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
