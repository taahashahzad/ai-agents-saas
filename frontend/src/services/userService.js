import api from '../api';
import { ENDPOINTS } from './endpoints';

/** Create or synchronize the backend profile for the signed-in Firebase user. */
export async function syncUser(payload = {}) {
  const { data } = await api.post(ENDPOINTS.syncUser, payload);
  return data;
}

/** Fetch the backend profile of the signed-in user. */
export async function getCurrentUser() {
  const { data } = await api.get(ENDPOINTS.getUser);
  return data;
}
