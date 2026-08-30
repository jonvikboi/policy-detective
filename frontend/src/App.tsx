import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { LandingView } from './components/LandingView';
import { InvestigationView } from './components/InvestigationView';
import { ReportView } from './components/ReportView';
import { Footer } from './components/Footer';
import { 
  checkBackendHealth, 
  createScan, 
  getScanReport, 
  subscribeToScanEvents 
} from './api/client';
import { Scan, ScanEvent, ScanReport } from './types';

export function App() {
  const [activeView, setActiveView] = useState<'landing' | 'investigation' | 'report'>('landing');
  const [currentScan, setCurrentScan] = useState<Scan | null>(null);
  const [scanEvents, setScanEvents] = useState<ScanEvent[]>([]);
  const [report, setReport] = useState<ScanReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendHealthy, setBackendHealthy] = useState(false);

  // Check health on mount and periodically
  useEffect(() => {
    const check = async () => {
      try {
        await checkBackendHealth();
        setBackendHealthy(true);
      } catch (err) {
        setBackendHealthy(false);
      }
    };
    check();
    const interval = setInterval(check, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleStartScan = async (url: string) => {
    setIsLoading(true);
    setError(null);
    setScanEvents([]);
    setReport(null);

    try {
      const newScan = await createScan(url);
      setCurrentScan(newScan);
      setActiveView('investigation');

      // Subscribe to real-time events
      const cleanup = subscribeToScanEvents(
        newScan.id,
        async (eventType, data) => {
          if (eventType === 'progress') {
            setCurrentScan((prev) => prev ? {
              ...prev,
              progress: data.progress,
              current_stage: data.stage,
              stage_details: data.stage_details || prev.stage_details,
              status: data.status,
            } : null);
          } else if (eventType === 'done' || (eventType === 'stage_change' && (data.stage === 'completed' || data.message?.includes('complete')))) {
            try {
              const fullReport = await getScanReport(newScan.id);
              setReport(fullReport);
              setCurrentScan(fullReport.scan);
              // Smoothly transition to the full report view
              setTimeout(() => {
                setActiveView('report');
              }, 1200);
            } catch (err) {
              console.error('Failed to load final report:', err);
            }
          } else {
            setScanEvents((prev) => [
              ...prev,
              {
                type: eventType,
                data: data,
                timestamp: data.timestamp || new Date().toISOString(),
              },
            ]);
          }
        },
        (err) => {
          console.warn('Scan stream warning:', err);
        }
      );

      // Store cleanup if needed
    } catch (err: any) {
      setError(err.message || 'Failed to initialize investigation');
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewScan = () => {
    setActiveView('landing');
    setCurrentScan(null);
    setScanEvents([]);
    setReport(null);
    setError(null);
  };

  const handleViewReport = async () => {
    if (report) {
      setActiveView('report');
    } else if (currentScan) {
      setIsLoading(true);
      try {
        const fullReport = await getScanReport(currentScan.id);
        setReport(fullReport);
        setActiveView('report');
      } catch (err: any) {
        setError('Report is still compiling or unavailable');
      } finally {
        setIsLoading(false);
      }
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 selection:bg-brand-500/30 selection:text-brand-300">
      <Navbar
        onNewScan={handleNewScan}
        activeView={activeView}
        backendHealthy={backendHealthy}
      />

      <main className="flex-1">
        {activeView === 'landing' && (
          <LandingView
            onStartScan={handleStartScan}
            isLoading={isLoading}
            error={error}
          />
        )}

        {activeView === 'investigation' && currentScan && (
          <InvestigationView
            scan={currentScan}
            events={scanEvents}
            onViewReport={handleViewReport}
            onCancelScan={handleNewScan}
          />
        )}

        {activeView === 'report' && report && (
          <ReportView
            report={report}
            onNewScan={handleNewScan}
          />
        )}
      </main>

      <Footer />
    </div>
  );
}

export default App;
