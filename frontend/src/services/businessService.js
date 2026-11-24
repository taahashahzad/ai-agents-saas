import api from '../api';
import { ENDPOINTS } from './endpoints';

/**
 * Backends commonly return either a bare array or { items: [...] } / { businesses: [...] }.
 * Normalize so the UI doesn't care.
 */
function toList(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.businesses)) return data.businesses;
  if (Array.isArray(data?.data)) return data.data;
  return [];
}

function unwrap(data) {
  return data?.business || data?.data || data;
}

export async function listBusinesses() {
  const { data } = await api.get(ENDPOINTS.businesses);
  return toList(data);
}

export async function getBusiness(id) {
  const { data } = await api.get(ENDPOINTS.business(id));
  return unwrap(data);
}

export async function createBusiness(payload) {
  const { data } = await api.post(ENDPOINTS.businesses, payload);
  return unwrap(data);
}

export async function updateBusiness(id, payload) {
  const { data } = await api.patch(ENDPOINTS.business(id), payload);
  return unwrap(data);
}

export async function archiveBusiness(id) {
  const { data } = await api.delete(ENDPOINTS.business(id));
  return unwrap(data);
}
