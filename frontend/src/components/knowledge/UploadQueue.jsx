import { formatFileSize } from '../../utils/knowledge';

const STATUS_TEXT = {
  queued: 'Waiting...',
  uploading: 'Uploading...',
  done: 'Uploaded and processed',
  warning: 'Uploaded, but processing failed',
  error: 'Not uploaded',
};

const BAR_COLOR = {
  queued: 'bg-slate-300',
  uploading: 'bg-indigo-500',
  done: 'bg-emerald-500',
  warning: 'bg-amber-500',
  error: 'bg-red-500',
};

export default function UploadQueue({ uploads, uploading, onClear }) {
  if (uploads.length === 0) return null;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">Uploads</h3>
        {!uploading && (
          <button type="button" onClick={onClear} className="text-xs font-medium text-slate-500 hover:text-slate-700">
            Clear
          </button>
        )}
      </div>
      <ul className="space-y-3">
        {uploads.map((u) => (
          <li key={u.id}>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="min-w-0 truncate font-medium text-slate-800">{u.name}</span>
              <span className="shrink-0 text-xs text-slate-400">{formatFileSize(u.size)}</span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div
                className={`h-full rounded-full transition-all ${BAR_COLOR[u.status]}`}
                style={{ width: `${u.status === 'error' ? 100 : u.progress}%` }}
              />
            </div>
            <p
              className={`mt-1 text-xs ${
                u.status === 'error' ? 'text-red-600' : u.status === 'warning' ? 'text-amber-700' : 'text-slate-500'
              }`}
            >
              {u.status === 'uploading' ? `${STATUS_TEXT.uploading} ${u.progress}%` : STATUS_TEXT[u.status]}
              {u.message ? ` — ${u.message}` : ''}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
