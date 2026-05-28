interface DiseaseInputProps {
  value: string;
  onChange: (value: string) => void;
}

const MAX_LENGTH = 500;
const SHOW_COUNT_THRESHOLD = 400;

export function DiseaseInput({ value, onChange }: DiseaseInputProps) {
  const remaining = MAX_LENGTH - value.length;

  return (
    <div>
      <label
        htmlFor="disease-input"
        className="block text-sm font-medium text-slate-300 mb-2"
      >
        Medical Conditions or Diseases
      </label>
      <textarea
        id="disease-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        maxLength={MAX_LENGTH}
        rows={4}
        placeholder="Enter any medical conditions or diseases, separated by commas"
        className="w-full px-3 py-2 text-sm bg-slate-800 border border-slate-700 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y"
      />
      {value.length > SHOW_COUNT_THRESHOLD && (
        <p className="mt-1 text-xs text-slate-400">
          {remaining}/{MAX_LENGTH} characters remaining
        </p>
      )}
    </div>
  );
}
