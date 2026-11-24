import { useCallback, useEffect, useState } from 'react';
import { listBusinesses } from '../services/businessService';
import { getErrorMessage } from '../utils/errors';

export function useBusinesses() {
  const [businesses, setBusinesses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refetch = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const items = await listBusinesses();
      setBusinesses(items);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load businesses.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { businesses, loading, error, refetch };
}
