import { useState } from 'react';
import { MAX_UPLOAD_MB, SUPPORTED_LABEL } from '../../utils/knowledge';

/**
 * Drag-and-drop target. File selection itself (the hidden <input>) is owned by
 * DocumentsTab so the header "Upload document" button and this area share it.
 */
export default function UploadDropzone({ onFiles, onBrowse, disabled = false, busy = false }) {
  const [dragging, setDragging] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    if (e.dataTransfer?.files?.length) onFiles(e.dataTransfer.files);
  };

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label="Upload documents: drag files here or press Enter to browse"
      onClick={() => !disabled && onBrowse()}
      onKeyDown={(e) => {
        if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onBrowse();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition focus:outline-none focus:ring-2 focus:ring-indigo-200 ${
        disabled
          ? 'cursor-not-allowed border-slate-200 bg-slate-50 opacity-70'
          : dragging
            ? 'cursor-copy border-indigo-500 bg-indigo-50'
            : 'cursor-pointer border-slate-300 bg-white hover:border-indigo-400 hover:bg-indigo-50/40'
      }`}
    >
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-indigo-50 text-indigo-600">
        {busy ? (
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />
        ) : (
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
            />
          </svg>
        )}
      </div>
      <p className="text-sm font-medium text-slate-900">
        {busy ? 'Upload in progress...' : dragging ? 'Drop to upload' : 'Drag and drop files here, or click to browse'}
      </p>
      <p className="mt-1 text-xs text-slate-500">
        {SUPPORTED_LABEL} &middot; up to {MAX_UPLOAD_MB} MB each
      </p>
    </div>
  );
}
