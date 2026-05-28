import type { Pattern } from '../../types';

interface PatternCardProps {
  pattern: Pattern;
}

const severityConfig = {
  WARNING: {
    bg: 'bg-gradient-to-br from-red-950/70 to-red-900/40',
    border: 'border-red-700/60',
    badge: 'bg-red-600 text-white',
    icon: '🚨',
    accent: 'text-red-400',
    markerBorder: 'border-red-800/50',
    markerBg: 'bg-red-950/40',
  },
  CAUTION: {
    bg: 'bg-gradient-to-br from-amber-950/70 to-amber-900/40',
    border: 'border-amber-700/60',
    badge: 'bg-amber-600 text-white',
    icon: '⚠️',
    accent: 'text-amber-400',
    markerBorder: 'border-amber-800/50',
    markerBg: 'bg-amber-950/40',
  },
  ADVISORY: {
    bg: 'bg-gradient-to-br from-blue-950/70 to-blue-900/40',
    border: 'border-blue-700/60',
    badge: 'bg-blue-600 text-white',
    icon: 'ℹ️',
    accent: 'text-blue-400',
    markerBorder: 'border-blue-800/50',
    markerBg: 'bg-blue-950/40',
  },
};

export function PatternCard({ pattern }: PatternCardProps) {
  const config = severityConfig[pattern.severity];

  return (
    <div className={`${config.bg} border ${config.border} rounded-2xl p-6 shadow-lg`}>
      {/* Header: severity + confidence */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <span className="text-xl">{config.icon}</span>
          <span className={`text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider ${config.badge}`}>
            {pattern.severity}
          </span>
        </div>
        <span className="text-xs text-slate-400 font-medium">
          Confidence: <span className="text-slate-200">{pattern.confidence}</span>
        </span>
      </div>

      {/* Pattern name */}
      <h3 className="text-xl font-bold text-white mb-4">{pattern.name}</h3>

      {/* Divider */}
      <div className="border-t border-slate-700/50 mb-4" />

      {/* Explanation */}
      <p className="text-sm text-slate-300 leading-relaxed mb-4">
        {pattern.explanation}
      </p>

      {/* Symptomatic note (only if present) */}
      {pattern.symptomatic_note && (
        <div className="mb-5 p-3.5 bg-purple-950/40 border border-purple-700/40 rounded-xl">
          <p className="text-sm text-purple-200 flex items-start gap-2.5">
            <span className="text-lg shrink-0">💓</span>
            <span>{pattern.symptomatic_note}</span>
          </p>
        </div>
      )}

      {/* Supporting markers */}
      {pattern.supporting_markers.length > 0 && (
        <div className="mb-5">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
            Supporting Markers
          </h4>
          <div className="flex flex-wrap gap-2">
            {pattern.supporting_markers.map((marker, i) => (
              <MarkerPill key={i} marker={marker} config={config} />
            ))}
          </div>
        </div>
      )}

      {/* Doctor questions */}
      {pattern.doctor_questions.length > 0 && (
        <div className="mb-5">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <span>💬</span> Questions for Your Doctor
          </h4>
          <div className="space-y-2">
            {pattern.doctor_questions.map((q, i) => (
              <div
                key={i}
                className="text-sm text-slate-200 bg-slate-800/60 border border-slate-700/50 rounded-xl px-4 py-3 flex gap-3"
              >
                <span className={`font-bold shrink-0 ${config.accent}`}>{i + 1}.</span>
                <span>{q}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Citations */}
      {pattern.citations.length > 0 && (
        <div>
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
            <span>📖</span> Sources
          </h4>
          <ul className="space-y-1">
            {pattern.citations.map((cite) => (
              <li key={cite.chunk_id} className="text-xs text-slate-400 flex items-start gap-2">
                <span className="text-slate-500 shrink-0">•</span>
                <span>
                  <span className="text-slate-300">{cite.source}</span>
                  {cite.chapter && <span className="text-slate-500"> — {cite.chapter}</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** Renders a single supporting marker as a pill with an arrow indicator */
function MarkerPill({ marker, config }: { marker: string; config: typeof severityConfig.WARNING }) {
  const flag = parseFlag(marker);

  return (
    <span className={`text-xs font-medium px-3 py-1.5 rounded-full border ${config.markerBorder} ${config.markerBg} text-slate-200 flex items-center gap-1.5`}>
      {stripFlag(marker)}
      {flag === 'high' && <span className="text-red-400">↑</span>}
      {flag === 'low' && <span className="text-yellow-400">↓</span>}
      {flag === 'normal' && <span className="text-green-400">✓</span>}
    </span>
  );
}

function parseFlag(marker: string): 'high' | 'low' | 'normal' | null {
  const lower = marker.toLowerCase();
  if (lower.includes('(high)')) return 'high';
  if (lower.includes('(low)')) return 'low';
  if (lower.includes('(normal)')) return 'normal';
  return null;
}

function stripFlag(marker: string): string {
  return marker.replace(/\s*\((High|Low|Normal)\)\s*/i, '').trim();
}
