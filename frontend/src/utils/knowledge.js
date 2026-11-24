/**
 * Constants and helpers for the Knowledge Base (Phase 3).
 * Everything here mirrors the backend contract; the server stays the source of truth.
 */

// The backend's size limit (MAX_UPLOAD_MB, default 10) is not exposed by any
// endpoint, so the client limit comes from an env var that must match it.
const configured = Number(import.meta.env?.VITE_MAX_UPLOAD_MB);
export const MAX_UPLOAD_MB = Number.isFinite(configured) && configured > 0 ? configured : 10;
export const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;

export const ALLOWED_EXTENSIONS = ['pdf', 'docx', 'txt', 'csv'];
export const ACCEPT_ATTR = ALLOWED_EXTENSIONS.map((e) => `.${e}`).join(',');
export const SUPPORTED_LABEL = 'PDF, DOCX, TXT or CSV';

// Structured-entry field limits from the contract.
export const ENTRY_LIMITS = { title: 200, category: 60, content: 20000 };

export function getExtension(filename) {
  const name = String(filename || '');
  const i = name.lastIndexOf('.');
  return i < 0 ? '' : name.slice(i + 1).toLowerCase();
}

export function formatFileSize(bytes) {
  const n = Number(bytes);
  if (!Number.isFinite(n) || n < 0) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10 * 1024 ? 1 : 0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/** Client-side check (extension + size). Returns an error message, or '' if OK. */
export function validateFile(file) {
  if (!ALLOWED_EXTENSIONS.includes(getExtension(file.name))) {
    return `"${file.name}" is not a supported file type. Upload a ${SUPPORTED_LABEL} file.`;
  }
  if (file.size === 0) return `"${file.name}" is empty.`;
  if (file.size > MAX_UPLOAD_BYTES) {
    return `"${file.name}" is ${formatFileSize(file.size)}, which exceeds the ${MAX_UPLOAD_MB} MB limit.`;
  }
  return '';
}

// Statuses are exactly those defined by the contract: uploaded | processing | processed | failed.
export const DOCUMENT_STATUS = {
  uploaded: { label: 'Uploaded', badge: 'bg-slate-100 text-slate-600 ring-slate-200', dot: 'bg-slate-400' },
  processing: { label: 'Processing', badge: 'bg-blue-50 text-blue-700 ring-blue-200', dot: 'bg-blue-500 animate-pulse' },
  processed: { label: 'Processed', badge: 'bg-emerald-50 text-emerald-700 ring-emerald-200', dot: 'bg-emerald-500' },
  failed: { label: 'Failed', badge: 'bg-red-50 text-red-700 ring-red-200', dot: 'bg-red-500' },
};

export function documentName(doc) {
  return doc?.original_filename || doc?.filename || 'Untitled document';
}

export function isArchived(business) {
  return Boolean(business && (business.archived === true || business.status === 'archived'));
}

export function formatDateTime(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

/**
 * Category is free text (the backend stores it lowercase). These are only
 * quick-pick SUGGESTIONS to help people get started; nothing is required or
 * hardcoded per business type.
 */
const GENERIC_SUGGESTIONS = ['hours', 'services', 'policies', 'faq', 'contact', 'pricing'];
const TYPE_SUGGESTIONS = {
  restaurant: ['hours', 'menu', 'delivery', 'payments', 'faq'],
  clinic: ['hours', 'services', 'doctors', 'appointments', 'faq'],
  school: ['hours', 'admissions', 'fees', 'attendance', 'faq'],
};

export function categorySuggestions(businessType) {
  return TYPE_SUGGESTIONS[String(businessType || '').toLowerCase()] || GENERIC_SUGGESTIONS;
}

/** Validate a structured entry. `partial` skips untouched empty fields is NOT allowed: none may be empty. */
export function validateEntry({ title, category, content }) {
  const errors = {};
  const t = String(title || '').trim();
  const c = String(category || '').trim();
  const b = String(content || '').trim();

  if (!t) errors.title = 'Title is required.';
  else if (t.length > ENTRY_LIMITS.title) errors.title = `Title must be ${ENTRY_LIMITS.title} characters or fewer.`;

  if (!c) errors.category = 'Category is required.';
  else if (c.length > ENTRY_LIMITS.category) errors.category = `Category must be ${ENTRY_LIMITS.category} characters or fewer.`;

  if (!b) errors.content = 'Content is required.';
  else if (b.length > ENTRY_LIMITS.content) errors.content = `Content must be ${ENTRY_LIMITS.content.toLocaleString()} characters or fewer.`;

  return errors;
}
