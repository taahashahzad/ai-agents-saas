import { useState } from 'react';
import Input from './Input';
import Select from './Select';
import Textarea from './Textarea';
import Button from './Button';
import ErrorAlert from './ErrorAlert';
import { BUSINESS_TYPES, BUSINESS_TYPE_VALUES } from '../utils/constants';
import { validateBusiness } from '../utils/validators';

/**
 * Shared by Create Business and the Edit mode of Business Details.
 * `onSubmit` receives { name, business_type, description } and may throw/reject;
 * the parent passes a string via `serverError` to show backend errors.
 */
export default function BusinessForm({
  initialValues = { name: '', type: '', description: '' },
  submitLabel = 'Save',
  submitting = false,
  serverError = '',
  onSubmit,
  onCancel,
}) {
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});

  const handleChange = (e) => {
    const { name, value } = e.target;
    setValues((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: '' }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const found = validateBusiness(values, BUSINESS_TYPE_VALUES);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    onSubmit({
      name: values.name.trim(),
      business_type: values.type,
      description: values.description.trim(),
    });
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <ErrorAlert message={serverError} />
      <Input
        id="name"
        name="name"
        label="Business name"
        placeholder="e.g. Sunrise Bistro"
        value={values.name}
        onChange={handleChange}
        error={errors.name}
        disabled={submitting}
      />
      <Select
        id="type"
        name="type"
        label="Business type"
        placeholder="Select a type"
        options={BUSINESS_TYPES}
        value={values.type}
        onChange={handleChange}
        error={errors.type}
        disabled={submitting}
      />
      <Textarea
        id="description"
        name="description"
        label="Description"
        placeholder="What does this business do?"
        value={values.description}
        onChange={handleChange}
        error={errors.description}
        disabled={submitting}
      />
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        {onCancel && (
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
        )}
        <Button type="submit" loading={submitting}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
