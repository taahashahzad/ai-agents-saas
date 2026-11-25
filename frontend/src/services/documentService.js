import api from '../api';
import { ENDPOINTS } from './endpoints';
import { documentName } from '../utils/knowledge';

// Uploads/downloads of up to the size limit can exceed the 20 s default of the shared client.
const TRANSFER_TIMEOUT_MS = 120000;

/**
 * Every call goes through the shared Axios instance (src/api.js), so the
 * Firebase ID token is attached by the existing interceptor. The business is
 * identified ONLY by the id in the URL. `signal` lets callers cancel requests
 * that belong to a business the user has switched away from.
 */

export async function listDocuments(businessId, { limit = 25, cursor, signal } = {}) {
  const params = { limit };
  if (cursor) params.cursor = cursor;
  const { data } = await api.get(ENDPOINTS.documents(businessId), { params, signal });
  return {
    items: Array.isArray(data?.items) ? data.items : [],
    nextCursor: data?.next_cursor || null,
  };
}

export async function getDocument(businessId, documentId, { signal } = {}) {
  const { data } = await api.get(ENDPOINTS.document(businessId, documentId), { signal });
  return data;
}

/**
 * Upload one file as multipart/form-data with a single field named `file`.
 * No Content-Type header is set here (or by default in api.js): the browser must
 * generate it, because it contains the multipart boundary.
 */
export async function uploadDocument(businessId, file, { onProgress, signal } = {}) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post(ENDPOINTS.documents(businessId), form, {
    signal,
    timeout: TRANSFER_TIMEOUT_MS,
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    },
  });
  return data;
}

/** When a blob request fails, the JSON error body arrives as a Blob. Parse it so error messages work. */
async function withParsedBlobError(error) {
  const body = error?.response?.data;
  if (body instanceof Blob) {
    try {
      error.response.data = JSON.parse(await body.text());
    } catch {
      error.response.data = null;
    }
  }
  return error;
}

/**
 * The bucket is private and the file is streamed through the API, so a plain
 * <a href> would not carry the Authorization header. Fetch it as a blob via the
 * authenticated client, then trigger a browser download.
 */
export async function downloadDocument(businessId, doc) {
  let response;
  try {
    response = await api.get(ENDPOINTS.downloadDocument(businessId, doc.document_id), {
      responseType: 'blob',
      timeout: TRANSFER_TIMEOUT_MS,
    });
  } catch (error) {
    throw await withParsedBlobError(error);
  }
  const url = URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = url;
  link.download = documentName(doc);
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function deleteDocument(businessId, documentId) {
  await api.delete(ENDPOINTS.document(businessId, documentId)); // 204 No Content
}

export async function retryDocument(businessId, documentId) {
  const { data } = await api.post(ENDPOINTS.retryDocument(businessId, documentId));
  return data;
}

export async function indexDocument(businessId, documentId) {
  const { data } = await api.post(ENDPOINTS.indexDocument(businessId, documentId));
  return data;
}
