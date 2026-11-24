import axios from 'axios';
import { signOut } from 'firebase/auth';
import { auth } from './firebase';

/**
 * Centralized Axios instance.
 * - Base URL comes from VITE_API_BASE_URL.
 * - Every request gets a fresh Firebase ID token as `Authorization: Bearer {token}`.
 * - On a 401 the request is retried once with a force-refreshed token;
 *   if it still fails the user is signed out.
 */
// NOTE: no default Content-Type header on purpose. Axios sets application/json
// by itself for plain-object bodies, and for FormData uploads the browser must
// generate `multipart/form-data; boundary=...`. A forced JSON default would
// make axios serialize the FormData as JSON and break document uploads.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 20000,
});

api.interceptors.request.use(async (config) => {
  const user = auth.currentUser;
  if (user) {
    const token = await user.getIdToken();
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && original && !original._retried && auth.currentUser) {
      original._retried = true;
      try {
        const token = await auth.currentUser.getIdToken(true);
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      } catch {
        await signOut(auth);
      }
    }
    return Promise.reject(error);
  }
);

export default api;
