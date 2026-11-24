const FIREBASE_MESSAGES = {
  'auth/email-already-in-use': 'An account with this email already exists.',
  'auth/invalid-email': 'Please enter a valid email address.',
  'auth/weak-password': 'Password is too weak. Use at least 6 characters.',
  'auth/user-not-found': 'Invalid email or password.',
  'auth/wrong-password': 'Invalid email or password.',
  'auth/invalid-credential': 'Invalid email or password.',
  'auth/too-many-requests': 'Too many attempts. Please try again later.',
  'auth/network-request-failed': 'Network error. Check your connection and try again.',
  'auth/user-disabled': 'This account has been disabled.',
};

// Used only when the backend gives no readable message of its own.
const STATUS_MESSAGES = {
  400: 'The request was invalid.',
  401: 'Your session has expired. Please sign in again.',
  403: "You don't have permission to perform this action.",
  404: 'The requested item was not found.',
  409: 'This conflicts with existing data (for example, the user may already be a member or invited).',
  410: 'This invitation has expired or is no longer valid.',
  413: 'The file is too large.',
  415: 'This file type is not supported.',
  422: 'Some of the submitted information is invalid.',
  500: 'An unexpected server error occurred. Please try again.',
  502: 'Storage is temporarily unavailable. Please try again.',
  503: 'The service is temporarily unavailable. Please try again later.',
};

export function getStatus(error) {
  return error?.response?.status || null;
}

/**
 * Backend error body shape (Phase 3 contract):
 *   { "error": { "code": "file_too_large", "message": "...", "details": [...] } }
 * Returns the machine-readable `code`, or null.
 */
export function getErrorCode(error) {
  const data = error?.response?.data;
  const err = data && typeof data === 'object' ? data.error : null;
  return err && typeof err === 'object' && typeof err.code === 'string' ? err.code : null;
}

/** True when a request was cancelled with AbortController (not a real failure). */
export function isCanceled(error) {
  return error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError' || error?.name === 'AbortError';
}

function describeDetail(first) {
  if (!first?.msg) return '';
  const loc = Array.isArray(first.loc)
    ? first.loc.filter((p) => p !== 'body' && p !== 'query').join('.')
    : '';
  return loc ? `${loc}: ${first.msg}` : first.msg;
}

/**
 * Convert any thrown error (Firebase, Axios, or plain) into a user-facing string.
 * Never returns raw HTML or stack traces.
 */
export function getErrorMessage(error, fallback = 'Something went wrong. Please try again.') {
  if (!error) return fallback;

  if (error.code && FIREBASE_MESSAGES[error.code]) {
    return FIREBASE_MESSAGES[error.code];
  }

  const data = error.response?.data;
  if (data && typeof data === 'object') {
    // Phase 3 shape: { error: { code, message, details } }
    if (data.error && typeof data.error === 'object') {
      const { message, details } = data.error;
      if (typeof message === 'string' && message) {
        const extra = Array.isArray(details) ? describeDetail(details[0]) : '';
        return extra && !message.includes(extra) ? `${message} (${extra})` : message;
      }
    }
    // Earlier shapes (FastAPI default etc.)
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) {
      const msg = describeDetail(data.detail[0]);
      if (msg) return msg;
    }
    if (typeof data.message === 'string') return data.message;
    if (typeof data.error === 'string') return data.error;
  } else if (typeof data === 'string' && data.length < 300 && !data.trim().startsWith('<')) {
    return data;
  }

  const status = getStatus(error);
  if (status && STATUS_MESSAGES[status]) return STATUS_MESSAGES[status];

  if (error.code === 'ERR_NETWORK') {
    return 'Cannot reach the server. Check your connection or try again later.';
  }
  if (error.code === 'ECONNABORTED') {
    return 'The request timed out. Please try again.';
  }

  if (error.message) return error.message;
  return fallback;
}
