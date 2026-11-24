export default function ErrorAlert({ message, onRetry, className = '' }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className={`flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 ${className}`}
    >
      <span>{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 font-medium text-red-700 underline hover:text-red-800"
        >
          Retry
        </button>
      )}
    </div>
  );
}
