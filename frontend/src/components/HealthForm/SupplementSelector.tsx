import { useState } from 'react';
import { PREDEFINED_SUPPLEMENTS } from './supplements';

interface SupplementSelectorProps {
  selected: string[];
  onChange: (selected: string[]) => void;
}

export function SupplementSelector({ selected, onChange }: SupplementSelectorProps) {
  const [otherText, setOtherText] = useState('');
  const isOtherSelected = selected.some(
    (s) => !PREDEFINED_SUPPLEMENTS.includes(s as typeof PREDEFINED_SUPPLEMENTS[number])
  ) || otherText.length > 0;

  const [showOtherInput, setShowOtherInput] = useState(isOtherSelected);

  const handleToggle = (supplement: string) => {
    if (selected.includes(supplement)) {
      onChange(selected.filter((s) => s !== supplement));
    } else {
      onChange([...selected, supplement]);
    }
  };

  const handleOtherToggle = () => {
    if (showOtherInput) {
      // Deselecting "Other": remove custom supplement and hide input
      const withoutCustom = selected.filter((s) =>
        PREDEFINED_SUPPLEMENTS.includes(s as typeof PREDEFINED_SUPPLEMENTS[number])
      );
      setOtherText('');
      setShowOtherInput(false);
      onChange(withoutCustom);
    } else {
      setShowOtherInput(true);
    }
  };

  const handleOtherTextChange = (value: string) => {
    const previousCustom = otherText.trim();
    setOtherText(value);

    const withoutPreviousCustom = selected.filter(
      (s) =>
        PREDEFINED_SUPPLEMENTS.includes(s as typeof PREDEFINED_SUPPLEMENTS[number]) ||
        s !== previousCustom
    );

    const newCustom = value.trim();
    if (newCustom) {
      // Remove old custom value and add new one
      const base = withoutPreviousCustom.filter((s) => s !== previousCustom);
      onChange([...base, newCustom]);
    } else {
      onChange(withoutPreviousCustom.filter((s) => s !== previousCustom));
    }
  };

  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-3">
        Nutritional Supplements
      </label>
      <div
        role="group"
        aria-label="Select supplements"
        className="flex flex-wrap gap-2"
      >
        {PREDEFINED_SUPPLEMENTS.map((supplement) => {
          const isSelected = selected.includes(supplement);
          return (
            <button
              key={supplement}
              type="button"
              aria-pressed={isSelected}
              onClick={() => handleToggle(supplement)}
              className={`px-3 py-1.5 text-sm rounded-lg border transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 focus:ring-offset-slate-900 ${
                isSelected
                  ? 'bg-blue-600/20 border-blue-500 text-blue-300'
                  : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white'
              }`}
            >
              {supplement}
            </button>
          );
        })}
        <button
          type="button"
          aria-pressed={showOtherInput}
          onClick={handleOtherToggle}
          className={`px-3 py-1.5 text-sm rounded-lg border transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 focus:ring-offset-slate-900 ${
            showOtherInput
              ? 'bg-blue-600/20 border-blue-500 text-blue-300'
              : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white'
          }`}
        >
          Other
        </button>
      </div>

      {showOtherInput && (
        <div className="mt-3">
          <label htmlFor="other-supplement" className="sr-only">
            Enter custom supplement
          </label>
          <input
            id="other-supplement"
            type="text"
            value={otherText}
            onChange={(e) => handleOtherTextChange(e.target.value)}
            placeholder="Enter supplement name"
            className="w-full max-w-xs px-3 py-2 text-sm bg-slate-800 border border-slate-700 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
      )}
    </div>
  );
}
