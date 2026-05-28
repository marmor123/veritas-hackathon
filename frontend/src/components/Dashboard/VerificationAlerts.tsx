interface VerificationAlertsProps {
  alerts: string[];
}

export function VerificationAlerts({ alerts }: VerificationAlertsProps) {
  if (alerts.length === 0) return null;

  return (
    <div className="w-full max-w-xl mx-auto">
      <h3 className="text-sm font-semibold text-amber-400 uppercase tracking-wide mb-3">
        ⚠️ Verification Alerts
      </h3>
      <div className="space-y-2">
        {alerts.map((alert, i) => (
          <div
            key={i}
            className="p-3 bg-amber-900/20 border border-amber-800 rounded-lg text-sm text-amber-200"
          >
            {alert}
          </div>
        ))}
      </div>
    </div>
  );
}
