import { useState } from 'react';
import { SupplementSelector } from './SupplementSelector';
import { DiseaseInput } from './DiseaseInput';

interface HealthFormProps {
  onSubmit: (supplements: string[], diseases: string) => void;
  onSkip: () => void;
}

export function HealthForm({ onSubmit, onSkip }: HealthFormProps) {
  const [selectedSupplements, setSelectedSupplements] = useState<string[]>([]);
  const [diseases, setDiseases] = useState('');

  const handleSubmit = () => {
    onSubmit(selectedSupplements, diseases);
  };

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
      <h2 className="text-xl font-semibold text-slate-100 mb-2">
        Health Context
      </h2>
      <p className="text-sm text-slate-400 mb-6">
        Help us provide better analysis by sharing any supplements you take and medical conditions you have. All fields are optional.
      </p>

      <div className="space-y-6">
        <SupplementSelector
          selected={selectedSupplements}
          onChange={setSelectedSupplements}
        />

        <DiseaseInput
          value={diseases}
          onChange={setDiseases}
        />
      </div>

      <div className="mt-8 flex items-center justify-between">
        <button
          type="button"
          onClick={onSkip}
          className="text-slate-400 hover:text-slate-200 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 focus:ring-offset-slate-900 rounded"
        >
          I don&apos;t want to answer
        </button>

        <button
          type="button"
          onClick={handleSubmit}
          className="bg-blue-600 hover:bg-blue-700 text-white rounded-lg px-6 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 focus:ring-offset-slate-900"
        >
          Submit
        </button>
      </div>
    </div>
  );
}
