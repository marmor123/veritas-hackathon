import { useState } from 'react';
import type { Pattern } from '../../types';

interface PatternCardProps {
  pattern: Pattern;
}

const severityConfig = {
  WARNING: { bg: 'bg-red-900/30', border: 'border-red-700', badge: 'bg-red-600 text-white', label: 'WARNING' },
  CAUTION: { bg: 'bg-amber-900/30', border: 'border-amber-700', badge: 'bg-amber-600 text-white', label: 'CAUTION' },
  ADVISORY: { bg: 'bg-blue-900/30', border: 'border-blue-700', badge: 'bg-blue-600 text-white', label: 'ADVISORY' },
};

export function PatternCard({ pattern }: PatternCardProps) {
  const [expanded, setExpanded] = useState(false);
  const config = severityConfig[pattern.severity];

  return (
    <div className={`${config.bg} border ${config.border} rounded-xl p-5 transition-all duration-200`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <span className={`text-xs font-bold px-2 py-1 rounded ${config.badge}`}>
              {config.label}
            </span>
            <span className="text-xs text-slate-400">
              {(pattern.confidence * 100).toFixed(0)}% confidence
            </span>
          </div>
          <h3 className="text-lg font-semibold text-white">{pattern.name}</h3>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-slate-400 hover:text-white transition-colors p-1"
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          <svg
            className={`w-5 h-5 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {/* Biomarker tags */}
      <div className="flex flex-wrap gap-2 mt-3">
        {pattern.biomarkers.map((name) => (
          <span key={name} className="text-xs bg-slate-700/60 text-slate-300 px-2 py-1 rounded">
            {name}
          </span>
        ))}
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="mt-4 space-y-4">
          {/* Explanation */}
          <p className="text-sm text-slate-300 leading-relaxed">{pattern.explanation}</p>

          {/* Citations */}
          {pattern.citations.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Sources</h4>
              <ul className="space-y-1">
                {pattern.citations.map((cite) => (
                  <li key={cite.chunk_id} className="text-xs text-slate-500">
                    📖 {cite.source} — {cite.chapter}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Doctor Questions */}
          {pattern.doctor_questions.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
                Questions for your doctor
              </h4>
              <ul className="space-y-2">
                {pattern.doctor_questions.map((q, i) => (
                  <li key={i} className="text-sm text-slate-300 flex gap-2">
                    <span className="text-blue-400 shrink-0">→</span>
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
