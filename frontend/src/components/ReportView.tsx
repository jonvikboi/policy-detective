import React, { useState } from 'react';
import { 
  ShieldCheck, 
  AlertTriangle, 
  XCircle, 
  HelpCircle, 
  FileText, 
  Layers, 
  Database, 
  ExternalLink, 
  Download, 
  Copy, 
  Check, 
  Search, 
  Filter,
  Eye,
  Info,
  ChevronRight,
  ShieldAlert,
  ArrowUpRight
} from 'lucide-react';
import { ScanReport, VerdictType, TrackerCategory } from '../types';

interface ReportViewProps {
  report: ScanReport;
  onNewScan: () => void;
}

export const ReportView: React.FC<ReportViewProps> = ({ report, onNewScan }) => {
  const [activeTab, setActiveTab] = useState<'verdicts' | 'matrix' | 'evidence' | 'policies'>('verdicts');
  const [copied, setCopied] = useState(false);
  const [evidenceFilter, setEvidenceFilter] = useState<'all' | 'cookies' | 'network'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPolicy, setSelectedPolicy] = useState<any | null>(null);

  const { scan, policies, claims, verdicts, summary } = report;

  // Verdict badge renderer
  const renderVerdictBadge = (type: VerdictType) => {
    switch (type) {
      case 'consistent':
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-brand-500/10 text-brand-400 border border-brand-500/30 text-xs font-semibold">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Consistent</span>
          </span>
        );
      case 'potential_inconsistency':
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-accent-amber/10 text-accent-amber border border-accent-amber/30 text-xs font-semibold">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Potential Inconsistency</span>
          </span>
        );
      case 'strong_inconsistency':
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-accent-rose/10 text-accent-rose border border-accent-rose/30 text-xs font-semibold">
            <XCircle className="w-3.5 h-3.5" />
            <span>Strong Inconsistency</span>
          </span>
        );
      case 'unable_to_verify':
      default:
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-slate-800 text-slate-400 border border-slate-700 text-xs font-semibold">
            <HelpCircle className="w-3.5 h-3.5" />
            <span>Unable to Verify</span>
          </span>
        );
    }
  };

  // Category badge
  const renderCategoryBadge = (category: string) => {
    const colors: Record<string, string> = {
      analytics: 'bg-accent-blue/10 text-accent-blue border-accent-blue/20',
      advertising: 'bg-accent-rose/10 text-accent-rose border-accent-rose/20',
      social_tracking: 'bg-accent-purple/10 text-accent-purple border-accent-purple/20',
      functional: 'bg-brand-500/10 text-brand-400 border-brand-500/20',
      cdn: 'bg-slate-800 text-slate-300 border-slate-700',
      first_party: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      unknown: 'bg-slate-800 text-slate-400 border-slate-700',
    };
    const cls = colors[category] || colors.unknown;
    return (
      <span className={`px-2 py-0.5 rounded text-[11px] font-medium uppercase border ${cls}`}>
        {category.replace(/_/g, ' ')}
      </span>
    );
  };

  const handleCopyMarkdown = () => {
    let md = `# Policy Detective Investigation Report\n\n`;
    md += `**Target URL:** ${scan.url}\n`;
    md += `**Domain:** ${scan.domain}\n`;
    md += `**Audit Date:** ${new Date(scan.created_at).toLocaleString()}\n\n`;
    md += `## Summary\n`;
    md += `- Total Claims: ${summary.total_claims}\n`;
    md += `- Consistent: ${summary.consistent}\n`;
    md += `- Potential Inconsistencies: ${summary.potential_inconsistencies}\n`;
    md += `- Strong Inconsistencies: ${summary.strong_inconsistencies}\n`;
    md += `- Unable to Verify: ${summary.unable_to_verify}\n\n`;
    md += `## Findings & Verdicts\n\n`;

    claims.forEach((c) => {
      const v = verdicts.find((item) => item.claim_id === c.id);
      md += `### ${c.category.toUpperCase()}: ${c.claim_text}\n`;
      md += `- **Verdict:** ${v ? v.verdict_type : 'N/A'}\n`;
      md += `- **Confidence:** ${v ? Math.round(v.confidence * 100) : 0}%\n`;
      md += `- **Explanation:** ${v ? v.explanation : 'No explanation'}\n`;
      md += `- **Observed Behavior:** ${v ? v.observed_behavior : 'N/A'}\n\n`;
    });

    navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(report, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `policy_detective_report_${scan.domain}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Executive Summary Header */}
      <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800 space-y-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2 text-xs font-mono text-slate-400">
              <span>AUDIT REPORT</span>
              <span>•</span>
              <span className="text-brand-400">{scan.domain}</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white">
              Policy Compliance Verdict
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              Verified against real technical observations across 3 isolated WebCMD browser states.
            </p>
          </div>

          {/* Action buttons */}
          <div className="flex items-center space-x-2.5">
            <button
              onClick={handleCopyMarkdown}
              className="px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-slate-300 font-semibold flex items-center space-x-1.5 transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-brand-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied' : 'Copy Markdown'}</span>
            </button>

            <button
              onClick={handleDownloadJSON}
              className="px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-slate-300 font-semibold flex items-center space-x-1.5 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export JSON</span>
            </button>
          </div>
        </div>

        {/* High-Level Metric Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-2">
          {/* Card 1: Total Claims */}
          <div className="bg-slate-950/60 rounded-xl p-3.5 border border-slate-800/80 space-y-1">
            <p className="text-[11px] font-mono text-slate-400 uppercase">Tested Claims</p>
            <p className="text-2xl font-extrabold text-white">{summary.total_claims}</p>
          </div>

          {/* Card 2: Consistent */}
          <div className="bg-slate-950/60 rounded-xl p-3.5 border border-slate-800/80 space-y-1">
            <p className="text-[11px] font-mono text-brand-400 uppercase">Consistent</p>
            <p className="text-2xl font-extrabold text-brand-400">{summary.consistent}</p>
          </div>

          {/* Card 3: Potential Inconsistencies */}
          <div className="bg-slate-950/60 rounded-xl p-3.5 border border-slate-800/80 space-y-1">
            <p className="text-[11px] font-mono text-accent-amber uppercase">Potential Deviations</p>
            <p className="text-2xl font-extrabold text-accent-amber">{summary.potential_inconsistencies}</p>
          </div>

          {/* Card 4: Strong Inconsistencies */}
          <div className="bg-slate-950/60 rounded-xl p-3.5 border border-slate-800/80 space-y-1">
            <p className="text-[11px] font-mono text-accent-rose uppercase">Strong Deviations</p>
            <p className="text-2xl font-extrabold text-accent-rose">{summary.strong_inconsistencies}</p>
          </div>

          {/* Card 5: Observed Cookies */}
          <div className="bg-slate-950/60 rounded-xl p-3.5 border border-slate-800/80 space-y-1">
            <p className="text-[11px] font-mono text-slate-400 uppercase">Cookies Checked</p>
            <p className="text-2xl font-extrabold text-white">{summary.total_cookies_observed}</p>
          </div>

          {/* Card 6: Network Calls */}
          <div className="bg-slate-950/60 rounded-xl p-3.5 border border-slate-800/80 space-y-1">
            <p className="text-[11px] font-mono text-slate-400 uppercase">Network Calls</p>
            <p className="text-2xl font-extrabold text-white">{summary.total_network_requests}</p>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-slate-800 space-x-1 sm:space-x-4">
        {[
          { id: 'verdicts', label: 'Findings & Verdicts', icon: ShieldCheck },
          { id: 'matrix', label: '3-State Experiment Matrix', icon: Layers },
          { id: 'evidence', label: 'Technical Evidence Explorer', icon: Database },
          { id: 'policies', label: 'Discovered Policies', icon: FileText },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`pb-3 px-3 flex items-center space-x-2 text-xs sm:text-sm font-semibold border-b-2 transition-colors ${
                isActive
                  ? 'border-brand-500 text-brand-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab 1: Findings & Verdicts */}
      {activeTab === 'verdicts' && (
        <div className="space-y-4">
          {claims.length === 0 ? (
            <div className="glass-panel rounded-xl p-8 text-center text-slate-500">
              No testable claims were extracted for this policy document.
            </div>
          ) : (
            claims.map((claim) => {
              const verdict = verdicts.find((v) => v.claim_id === claim.id);
              const verdictType = verdict?.verdict_type || 'unable_to_verify';

              return (
                <div 
                  key={claim.id}
                  className="glass-panel rounded-2xl p-6 border border-slate-800/80 hover:border-slate-700 transition-all space-y-4"
                >
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-3 border-b border-slate-800/60">
                    <div className="flex items-center space-x-2">
                      {renderCategoryBadge(claim.category)}
                      <span className="text-xs font-mono text-slate-400 capitalize">
                        Testability: {claim.testability.replace(/_/g, ' ')}
                      </span>
                    </div>

                    <div className="flex items-center space-x-3">
                      {verdict && (
                        <div className="text-right">
                          <span className="text-[11px] text-slate-400 mr-2">Confidence:</span>
                          <span className="font-mono text-xs font-bold text-slate-200">
                            {Math.round(verdict.confidence * 100)}%
                          </span>
                        </div>
                      )}
                      {renderVerdictBadge(verdictType)}
                    </div>
                  </div>

                  {/* Claim Quote */}
                  <div className="space-y-1">
                    <p className="text-xs text-slate-400 uppercase font-mono">Stated Policy Commitment</p>
                    <blockquote className="text-sm sm:text-base font-medium text-white italic pl-3 border-l-2 border-brand-500/80">
                      "{claim.claim_text}"
                    </blockquote>
                  </div>

                  {/* Comparison Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                    <div className="bg-slate-950/60 rounded-xl p-3.5 border border-slate-900 space-y-1">
                      <p className="text-xs font-semibold text-slate-400 flex items-center space-x-1.5">
                        <FileText className="w-3.5 h-3.5 text-accent-blue" />
                        <span>Expected Behavior</span>
                      </p>
                      <p className="text-xs text-slate-300 leading-relaxed">
                        {verdict?.expected_behavior || JSON.stringify(claim.expected_behavior)}
                      </p>
                    </div>

                    <div className="bg-slate-950/60 rounded-xl p-3.5 border border-slate-900 space-y-1">
                      <p className="text-xs font-semibold text-slate-400 flex items-center space-x-1.5">
                        <Eye className="w-3.5 h-3.5 text-brand-400" />
                        <span>Observed Web Behavior</span>
                      </p>
                      <p className="text-xs text-slate-300 leading-relaxed">
                        {verdict?.observed_behavior || 'No divergent behavior recorded.'}
                      </p>
                    </div>
                  </div>

                  {/* Analysis Explanation */}
                  {verdict?.explanation && (
                    <div className="bg-slate-900/40 rounded-xl p-4 border border-slate-800/80 text-xs text-slate-300 space-y-1">
                      <div className="flex items-center space-x-1.5 text-brand-400 font-semibold mb-1">
                        <Info className="w-3.5 h-3.5" />
                        <span>Evidence-Backed Explanation</span>
                      </div>
                      <p className="leading-relaxed">{verdict.explanation}</p>
                      {verdict.confidence_reasoning && (
                        <p className="text-[11px] text-slate-500 pt-1">
                          <strong>Confidence Basis:</strong> {verdict.confidence_reasoning}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Tab 2: 3-State Controlled Experiments Matrix */}
      {activeTab === 'matrix' && (
        <div className="glass-panel rounded-2xl p-6 border border-slate-800 space-y-6">
          <div className="space-y-1">
            <h3 className="text-lg font-bold text-white">3-State Experiment Observation Matrix</h3>
            <p className="text-xs text-slate-400">
              Comparison across 3 clean, isolated WebCMD browser instances verifying tracking activity before consent, upon consent acceptance, and upon consent rejection.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-mono">
                  <th className="py-3 px-4">Experiment State</th>
                  <th className="py-3 px-4">Browser Action</th>
                  <th className="py-3 px-4">Total Cookies</th>
                  <th className="py-3 px-4">3rd-Party Trackers</th>
                  <th className="py-3 px-4">Network Requests</th>
                  <th className="py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-200">
                <tr className="hover:bg-slate-900/40">
                  <td className="py-3 px-4 font-semibold text-accent-blue">A. Pre-Consent</td>
                  <td className="py-3 px-4 text-slate-400">Clean page load, zero UI clicks</td>
                  <td className="py-3 px-4 font-mono font-bold">Recorded</td>
                  <td className="py-3 px-4 font-mono text-accent-amber">Audited</td>
                  <td className="py-3 px-4 font-mono">Captured</td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-brand-500/10 text-brand-400 font-semibold border border-brand-500/20">
                      COMPLETED
                    </span>
                  </td>
                </tr>
                <tr className="hover:bg-slate-900/40">
                  <td className="py-3 px-4 font-semibold text-brand-400">B. Accept All</td>
                  <td className="py-3 px-4 text-slate-400">Locate banner, click 'Accept All'</td>
                  <td className="py-3 px-4 font-mono font-bold">Recorded</td>
                  <td className="py-3 px-4 font-mono text-brand-400">Audited</td>
                  <td className="py-3 px-4 font-mono">Captured</td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-brand-500/10 text-brand-400 font-semibold border border-brand-500/20">
                      COMPLETED
                    </span>
                  </td>
                </tr>
                <tr className="hover:bg-slate-900/40">
                  <td className="py-3 px-4 font-semibold text-accent-rose">C. Reject All</td>
                  <td className="py-3 px-4 text-slate-400">Locate banner, click 'Reject All'</td>
                  <td className="py-3 px-4 font-mono font-bold">Recorded</td>
                  <td className="py-3 px-4 font-mono text-accent-rose">Audited</td>
                  <td className="py-3 px-4 font-mono">Captured</td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-brand-500/10 text-brand-400 font-semibold border border-brand-500/20">
                      COMPLETED
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Technical Evidence Explorer */}
      {activeTab === 'evidence' && (
        <div className="glass-panel rounded-2xl p-6 border border-slate-800 space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <h3 className="text-lg font-bold text-white">Technical Evidence Records</h3>
              <p className="text-xs text-slate-400">
                Inspect classified network calls and cookie metadata captured during automated sessions.
              </p>
            </div>

            {/* Filter Buttons */}
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setEvidenceFilter('all')}
                className={`text-xs px-3 py-1.5 rounded-lg border font-semibold ${
                  evidenceFilter === 'all' 
                    ? 'bg-brand-500/10 text-brand-400 border-brand-500/40' 
                    : 'bg-slate-900 text-slate-400 border-slate-800'
                }`}
              >
                All
              </button>
              <button
                onClick={() => setEvidenceFilter('cookies')}
                className={`text-xs px-3 py-1.5 rounded-lg border font-semibold ${
                  evidenceFilter === 'cookies' 
                    ? 'bg-brand-500/10 text-brand-400 border-brand-500/40' 
                    : 'bg-slate-900 text-slate-400 border-slate-800'
                }`}
              >
                Cookies
              </button>
              <button
                onClick={() => setEvidenceFilter('network')}
                className={`text-xs px-3 py-1.5 rounded-lg border font-semibold ${
                  evidenceFilter === 'network' 
                    ? 'bg-brand-500/10 text-brand-400 border-brand-500/40' 
                    : 'bg-slate-900 text-slate-400 border-slate-800'
                }`}
              >
                Network Calls
              </button>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-300">
            <p className="font-semibold text-brand-400 mb-1">Layered Classification Applied:</p>
            <p className="text-slate-400 leading-relaxed">
              Domains classified deterministically against 100+ known ad/analytics provider fingerprints, first-party host matching, and path heuristics before LLM fallback.
            </p>
          </div>
        </div>
      )}

      {/* Tab 4: Discovered Policies */}
      {activeTab === 'policies' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {policies.length === 0 ? (
            <div className="col-span-2 glass-panel rounded-xl p-8 text-center text-slate-500">
              No policy documents found.
            </div>
          ) : (
            policies.map((p) => (
              <div 
                key={p.id}
                className="glass-panel rounded-xl p-5 border border-slate-800 space-y-3 flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="px-2 py-0.5 rounded text-[10px] uppercase font-bold bg-brand-500/10 text-brand-400 border border-brand-500/20">
                      {p.policy_type}
                    </span>
                    <span className="text-[11px] text-slate-500 font-mono">
                      Via {p.discovered_via}
                    </span>
                  </div>
                  <h4 className="font-semibold text-white text-sm truncate">
                    {p.title || 'Policy Document'}
                  </h4>
                  <p className="text-xs text-slate-400 line-clamp-3 leading-relaxed">
                    {p.content_preview || p.content || 'Content extracted.'}
                  </p>
                </div>

                <div className="pt-2 flex items-center justify-between border-t border-slate-800/80">
                  <a
                    href={p.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-accent-blue hover:underline flex items-center space-x-1"
                  >
                    <span>Source Document</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                  <button
                    onClick={() => setSelectedPolicy(p)}
                    className="text-xs px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800"
                  >
                    View Text
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Policy Text Modal */}
      {selectedPolicy && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel rounded-2xl max-w-3xl w-full max-h-[80vh] flex flex-col border border-slate-700 shadow-2xl">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-white text-base">{selectedPolicy.title || 'Policy Text'}</h3>
                <p className="text-xs text-slate-400 truncate">{selectedPolicy.url}</p>
              </div>
              <button
                onClick={() => setSelectedPolicy(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg bg-slate-900 border border-slate-800"
              >
                ✕
              </button>
            </div>
            <div className="p-5 overflow-y-auto font-mono text-xs text-slate-300 leading-relaxed flex-1 whitespace-pre-wrap">
              {selectedPolicy.content || selectedPolicy.content_preview}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
