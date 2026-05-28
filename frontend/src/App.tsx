import { useState } from 'react';
import { FileUpload } from './components/Upload/FileUpload';
import { PatternCard } from './components/Dashboard/PatternCard';
import { BiomarkerList } from './components/Dashboard/BiomarkerList';
import { VerificationAlerts } from './components/Dashboard/VerificationAlerts';
import { HealthForm } from './components/HealthForm/HealthForm';
import { uploadForOcr } from './api/ocr';
import { analyzeResults } from './api/analyze';
import { demoScenarios } from './api/mock-data';
import type { DemoScenario } from './api/mock-data';
import type { OcrResponse, AnalysisResponse, VerificationResponse, PipelineStage } from './types';

function App() {
  const [stage, setStage] = useState<PipelineStage>('idle');
  const [ocrResult, setOcrResult] = useState<OcrResponse | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(null);
  const [verificationResult, setVerificationResult] = useState<VerificationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [useMock, setUseMock] = useState(true); // Toggle for demo mode
  const [demoScenario, setDemoScenario] = useState<DemoScenario | null>(null); // Track which demo was selected

  const handleFileSelected = async (file: File) => {
    setStage('uploading');
    setError(null);
    setOcrResult(null);
    setAnalysisResult(null);

    if (useMock) {
      // Simulate progressive pipeline with demo data
      await simulateDelay(800);
      setStage('ocr');
      const demo = demoScenarios.iron_deficiency;
      await simulateDelay(1200);
      setOcrResult(demo.ocr);
      setStage('health_form');
    } else {
      // Real API call
      try {
        setStage('ocr');
        const ocr = await uploadForOcr(file);
        setOcrResult(ocr);
        setStage('health_form');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to process file');
        setStage('error');
      }
    }
  };

  const handleDemoScenario = async (scenario: DemoScenario) => {
    const demo = demoScenarios[scenario];
    setError(null);
    setOcrResult(null);
    setAnalysisResult(null);
    setDemoScenario(scenario);

    setStage('ocr');
    await simulateDelay(1000);
    setOcrResult(demo.ocr);
    setStage('health_form');
  };

  const handleHealthFormSubmit = async (supplements: string[], diseases: string) => {
    if (!ocrResult) return;

    setStage('verification');
    setError(null);

    if (useMock) {
      // In demo mode, simulate verification and then show analysis
      await simulateDelay(1500);
      // Use the actual demo scenario that was selected (not hardcoded)
      const scenarioKey = demoScenario ?? 'iron_deficiency';
      setAnalysisResult(demoScenarios[scenarioKey].analysis);
      setStage('complete');
    } else {
      try {
        const result = await analyzeResults(ocrResult.biomarkers, {
          supplements: supplements.length > 0 ? supplements : undefined,
          medications: diseases ? [diseases] : undefined,
        });
        setAnalysisResult(result);
        setStage('complete');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Analysis failed');
        setStage('error');
      }
    }
  };

  const handleHealthFormSkip = () => {
    handleHealthFormSubmit([], '');
  };

  // verificationResult is stored for potential future use (e.g., rendering verification-specific data)
  void verificationResult;

  const handleClearAll = () => {
    setStage('idle');
    setOcrResult(null);
    setAnalysisResult(null);
    setVerificationResult(null);
    setDemoScenario(null);
    setError(null);
  };

  const showUpload = stage === 'idle' || stage === 'error';

  return (
    <div className="min-h-screen bg-slate-900 py-10 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white tracking-tight">VERITAS</h1>
          <p className="mt-2 text-slate-400">
            Verified blood test analysis with clinical pattern recognition
          </p>
        </div>

        {/* Mode toggle + Demo buttons */}
        <div className="flex items-center justify-center gap-4 mb-6">
          <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
            <input
              type="checkbox"
              checked={useMock}
              onChange={(e) => setUseMock(e.target.checked)}
              className="rounded"
            />
            Demo mode (mock data)
          </label>
          {stage !== 'idle' && (
            <button
              onClick={handleClearAll}
              className="text-sm text-red-400 hover:text-red-300 transition-colors"
            >
              Clear All Data
            </button>
          )}
        </div>

        {/* Demo scenario buttons */}
        {showUpload && (
          <div className="flex flex-wrap justify-center gap-2 mb-6">
            {(Object.entries(demoScenarios) as [DemoScenario, typeof demoScenarios[DemoScenario]][]).map(
              ([key, { label }]) => (
                <button
                  key={key}
                  onClick={() => handleDemoScenario(key)}
                  className="text-xs px-3 py-1.5 bg-slate-800 border border-slate-700 text-slate-300 rounded-lg hover:bg-slate-700 hover:text-white transition-colors"
                >
                  Demo: {label}
                </button>
              )
            )}
          </div>
        )}

        {/* Upload area */}
        {showUpload && <FileUpload onFileSelected={handleFileSelected} />}

        {/* Loading states */}
        {(stage === 'uploading' || stage === 'ocr' || stage === 'analysis' || stage === 'verification') && (
          <div className="flex items-center justify-center gap-3 my-8">
            <div className="w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
            <span className="text-slate-300">
              {stage === 'uploading' && 'Uploading file...'}
              {stage === 'ocr' && 'Extracting biomarkers (OCR)...'}
              {stage === 'analysis' && 'Analyzing patterns...'}
              {stage === 'verification' && 'Verifying results...'}
            </span>
          </div>
        )}

        {/* Health Form (show when stage is health_form) */}
        {stage === 'health_form' && (
          <div className="mt-6">
            <HealthForm onSubmit={handleHealthFormSubmit} onSkip={handleHealthFormSkip} />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mt-6 p-4 bg-red-900/30 border border-red-700 rounded-lg">
            <p className="text-red-300 text-sm">{error}</p>
          </div>
        )}

        {/* Results - progressive rendering */}
        <div className="mt-6 space-y-6">
          {/* Biomarkers (show as soon as OCR completes) */}
          {ocrResult && (
            <BiomarkerList biomarkers={ocrResult.biomarkers} confidence={ocrResult.parse_confidence} />
          )}

          {/* Verification alerts */}
          {analysisResult && (
            <VerificationAlerts alerts={analysisResult.verification_alerts} />
          )}

          {/* Pattern cards */}
          {analysisResult && analysisResult.patterns.length > 0 && (
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
                Clinical Patterns Detected
              </h3>
              {analysisResult.patterns.map((pattern, i) => (
                <PatternCard key={i} pattern={pattern} />
              ))}
            </div>
          )}

          {/* Summary */}
          {analysisResult && (
            <div className="p-4 bg-slate-800/50 border border-slate-700 rounded-lg">
              <p className="text-sm text-slate-300">{analysisResult.summary}</p>
            </div>
          )}

          {/* Disclaimer */}
          {analysisResult && (
            <p className="text-xs text-slate-500 text-center italic">
              {analysisResult.disclaimer}
            </p>
          )}
        </div>

        {/* Footer */}
        <p className="mt-10 text-xs text-slate-600 text-center">
          All processing happens on-device. Your data never leaves your computer.
        </p>
      </div>
    </div>
  );
}

function simulateDelay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default App;
