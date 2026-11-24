import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import BusinessForm from '../components/BusinessForm';
import Card from '../components/Card';
import { useBusiness } from '../hooks/useBusiness';
import { createBusiness } from '../services/businessService';
import { getErrorMessage } from '../utils/errors';

export default function CreateBusinessPage() {
  const navigate = useNavigate();
  const { refreshBusinesses } = useBusiness();
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState('');

  const handleSubmit = async (values) => {
    setSubmitting(true);
    setServerError('');
    try {
      const created = await createBusiness(values);
      const id = created?.id || created?._id;
      // Reload memberships from the backend and make the new business active.
      await refreshBusinesses(id);
      navigate(id ? `/businesses/${id}` : '/', { replace: true });
    } catch (err) {
      setServerError(getErrorMessage(err, 'Failed to create business.'));
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Create business</h1>
      <p className="mt-1 text-sm text-slate-500">Add a new business to your account.</p>
      <Card className="mt-6">
        <BusinessForm
          submitLabel="Create business"
          submitting={submitting}
          serverError={serverError}
          onSubmit={handleSubmit}
          onCancel={() => navigate('/')}
        />
      </Card>
    </div>
  );
}
