const STYLES = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  warning: 'border-amber-200 bg-amber-50 text-amber-800',
  info: 'border-indigo-200 bg-indigo-50 text-indigo-700',
};

export default function Notice({ type = 'success', children, onDismiss, className = '' }) {
  if (!children) return null;
  return (
    <div
      role="status"
      className={`flex items-start justify-between gap-3 rounded-lg border px-4 py-3 text-sm ${STYLES[type]} ${className}`}
    >
      <span>{children}</span>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="shrink-0 text-lg leading-none opacity-60 hover:opacity-100"
        >
          &times;
        </button>
      )}
    </div>
  );
}
