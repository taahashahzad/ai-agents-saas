export const BUSINESS_TYPES = [
  { value: 'restaurant', label: 'Restaurant' },
  { value: 'clinic', label: 'Clinic' },
  { value: 'school', label: 'School' },
];

export const BUSINESS_TYPE_VALUES = BUSINESS_TYPES.map((t) => t.value);

export function businessTypeLabel(value) {
  const found = BUSINESS_TYPES.find((t) => t.value === String(value || '').toLowerCase());
  return found ? found.label : value || 'Unknown';
}

export function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}
