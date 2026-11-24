import { useEffect } from 'react';

/**
 * Generic dialog shell: overlay, header with close button, scrollable body, Escape to close.
 * Forms render their own buttons inside `children`.
 * Set `locked` while saving so the dialog cannot be dismissed mid-request.
 */
export default function Modal({
  title,
  description,
  onClose,
  children,
  maxWidth = 'max-w-lg',
  locked = false,
  closeOnBackdrop = true,
}) {
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape' && !locked) onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose, locked]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onMouseDown={(e) => {
        if (closeOnBackdrop && !locked && e.target === e.currentTarget) onClose();
      }}
    >
      <div className={`flex max-h-[90vh] w-full ${maxWidth} flex-col rounded-xl bg-white shadow-xl`}>
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-semibold text-slate-900">{title}</h2>
            {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={locked}
            aria-label="Close"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-40"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-5">{children}</div>
      </div>
    </div>
  );
}
