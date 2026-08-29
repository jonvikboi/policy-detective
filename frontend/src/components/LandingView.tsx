import React, { useState } from 'react';
import { 
  Search, 
  ShieldCheck, 
  ArrowRight, 
  Layers, 
  Cpu, 
  Lock, 
  FileText, 
  Terminal, 
  CheckCircle2, 
  AlertTriangle,
  Globe
} from 'lucide-react';

interface LandingViewProps {
  onStartScan: (url: string) => void;
  isLoading: boolean;
  error?: string | null;
}

const PRESET_SITES = [
  { name: 'NY Times', url: 'https://www.nytimes.com', desc: 'News & Media' },
  { name: 'TechCrunch', url: 'https://techcrunch.com', desc: 'Tech Publications' },
  { name: 'BBC News', url: 'https://www.bbc.com', desc: 'Broadcaster / UK GDPR' },
  { name: 'Wikipedia', url: 'https://www.wikipedia.org', desc: 'Non-profit / Open Knowledge' },
  { name: 'GitHub', url: 'https://github.com', desc: 'Developer Platform' },
];

export const LandingView: React.FC<LandingViewProps> = ({ onStartScan, isLoading, error }) => {
  const [url, setUrl] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) {
      setValidationError('Please enter a website URL');
      return;
    }

    let targetUrl = url.trim();
    if (!targetUrl.startsWith('http://') && !targetUrl.startsWith('https://')) {
      targetUrl = 'https://' + targetUrl;
    }

    try {
      new URL(targetUrl);
      setValidationError(null);
      onStartScan(targetUrl);
    } catch {
      setValidationError('Please enter a valid URL (e.g., https://example.com)');
    }
  };

  const selectPreset = (presetUrl: string) => {
    setUrl(presetUrl);
    setValidationError(null);
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-16 space-y-16">
      {/* Hero Section */}
      <div className="text-center space-y-6">
        <div className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-slate-900/90 border border-slate-800 text-xs font-medium text-slate-300 shadow-inner">
          <span className="flex h-2 w-2 rounded-full bg-brand-400 animate-ping" />
          <span>WebCMD-Powered Autonomous Policy Auditor</span>
        </div>

        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white max-w-3xl mx-auto leading-tight">
          Verify Stated Privacy Policies Against <span className="gradient-text">Real Web Behavior</span>
        </h1>

        <p className="text-base sm:text-lg text-slate-400 max-w-2xl mx-auto leading-relaxed">
          Policy Detective autonomously locates policy documents, converts disclosures into testable claims, conducts 3-state controlled browser experiments via WebCMD, and generates verifiable, evidence-backed verdicts.
        </p>

        {/* URL Input Form */}
        <div className="max-w-2xl mx-auto pt-4">
          <form onSubmit={handleSubmit} className="relative">
            <div className="glass-panel rounded-2xl p-2 sm:p-2.5 shadow-2xl flex flex-col sm:flex-row items-center space-y-2 sm:space-y-0 sm:space-x-2 border border-slate-700/60 focus-within:border-brand-500/80 transition-all">
              <div className="flex items-center pl-3 w-full sm:w-auto flex-1">
                <Globe className="w-5 h-5 text-slate-400 mr-3 flex-shrink-0" />
                <input
                  type="text"
                  value={url}
                  onChange={(e) => {
                    setUrl(e.target.value);
                    if (validationError) setValidationError(null);
                  }}
                  placeholder="Enter website URL (e.g., https://nytimes.com)"
                  className="w-full bg-transparent text-white placeholder-slate-500 focus:outline-none text-sm sm:text-base"
                  disabled={isLoading}
                />
              </div>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full sm:w-auto px-6 py-3.5 rounded-xl bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-400 hover:to-brand-500 text-slate-950 font-bold text-sm flex items-center justify-center space-x-2 shadow-lg shadow-brand-500/25 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
              >
                {isLoading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin" />
                    <span>Initiating Audit...</span>
                  </>
                ) : (
                  <>
                    <span>Investigate Website</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>

            {(validationError || error) && (
              <p className="mt-2 text-xs text-accent-rose text-left pl-3 flex items-center space-x-1">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>{validationError || error}</span>
              </p>
            )}
          </form>

          {/* Quick Presets */}
          <div className="flex flex-wrap items-center justify-center gap-2 pt-4">
            <span className="text-xs text-slate-400">Quick tests:</span>
            {PRESET_SITES.map((site) => (
              <button
                key={site.url}
                onClick={() => selectPreset(site.url)}
                className="text-xs px-2.5 py-1 rounded-lg bg-slate-900/80 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-white transition-colors"
              >
                {site.name}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 4 Pillars Architecture Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6 pt-4">
        {/* Pillar 1 */}
        <div className="glass-panel rounded-2xl p-6 space-y-3 border border-slate-800/80 hover:border-slate-700 transition-all">
          <div className="w-10 h-10 rounded-xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400">
            <Layers className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-lg text-white">3-State Controlled Experiments</h3>
          <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
            Measures tracking before and after user choices. Deploys fresh isolated WebCMD sessions across <strong>Pre-Consent</strong>, <strong>Accept-All</strong>, and <strong>Reject-All</strong> states.
          </p>
        </div>

        {/* Pillar 2 */}
        <div className="glass-panel rounded-2xl p-6 space-y-3 border border-slate-800/80 hover:border-slate-700 transition-all">
          <div className="w-10 h-10 rounded-xl bg-accent-blue/10 border border-accent-blue/20 flex items-center justify-center text-accent-blue">
            <Terminal className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-lg text-white">WebCMD Browser Infrastructure</h3>
          <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
            Uses stealth CloakBrowser Chromium automation, QuickJS sandboxed scripts, Playwright network interception, and local sitemap navigation memory.
          </p>
        </div>

        {/* Pillar 3 */}
        <div className="glass-panel rounded-2xl p-6 space-y-3 border border-slate-800/80 hover:border-slate-700 transition-all">
          <div className="w-10 h-10 rounded-xl bg-accent-purple/10 border border-accent-purple/20 flex items-center justify-center text-accent-purple">
            <Cpu className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-lg text-white">Layered Tracker Classification</h3>
          <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
            Deterministic domain matching against known analytics/ad databases, first-party vs third-party heuristics, and cookie patterns before LLM escalation.
          </p>
        </div>

        {/* Pillar 4 */}
        <div className="glass-panel rounded-2xl p-6 space-y-3 border border-slate-800/80 hover:border-slate-700 transition-all">
          <div className="w-10 h-10 rounded-xl bg-accent-amber/10 border border-accent-amber/20 flex items-center justify-center text-accent-amber">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-lg text-white">Evidence-Backed Verdicts</h3>
          <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
            Generates calibrated verdicts with confidence scores and non-accusatory legal framing. Every claim links to verifiable network and cookie observations.
          </p>
        </div>
      </div>

      {/* Security & Disclaimer Notice */}
      <div className="glass-panel rounded-xl p-4 border border-slate-800 text-xs text-slate-400 flex items-start space-x-3 bg-slate-950/60">
        <Lock className="w-4 h-4 text-brand-400 mt-0.5 flex-shrink-0" />
        <div className="space-y-1">
          <p className="font-medium text-slate-300">Security & Operational Boundaries</p>
          <p>
            All browser investigations execute in isolated temporary profiles. Webpages are treated as untrusted targets. Action allowlists prevent arbitrary execution, SSRF safeguards block private network traversal, and raw cookie values or credentials are never stored.
          </p>
        </div>
      </div>
    </div>
  );
};
