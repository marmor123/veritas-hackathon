import type { Biomarker } from '../../types';

interface BiomarkerListProps {
  biomarkers: Biomarker[];
  confidence: number;
}

export function BiomarkerList({ biomarkers, confidence }: BiomarkerListProps) {
  return (
    <div className="w-full max-w-xl mx-auto">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
          Extracted Biomarkers
        </h3>
        <span className="text-xs text-slate-500">
          OCR confidence: {(confidence * 100).toFixed(0)}%
        </span>
      </div>
      <div className="grid gap-1.5">
        {biomarkers.map((marker, i) => (
          <div
            key={i}
            className="flex items-center justify-between p-2.5 bg-slate-800/60 border border-slate-700/50 rounded-lg"
          >
            <span className="text-sm text-slate-200 font-medium">{marker.name}</span>
            <div className="flex items-center gap-2">
              <span className="text-sm text-white tabular-nums">
                {marker.value} <span className="text-slate-400 text-xs">{marker.unit}</span>
              </span>
              {marker.ref_low !== null && marker.ref_high !== null && (
                <span className="text-xs text-slate-500">
                  ({marker.ref_low}–{marker.ref_high})
                </span>
              )}
              {marker.flag && marker.flag !== 'normal' && (
                <span
                  className={`text-xs px-2 py-0.5 rounded font-bold ${
                    marker.flag === 'high'
                      ? 'bg-red-900/50 text-red-300'
                      : 'bg-yellow-900/50 text-yellow-300'
                  }`}
                >
                  {marker.flag === 'high' ? '↑' : '↓'}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
