const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateEmail(email) {
  if (!email.trim()) return 'Email is required.';
  if (!EMAIL_REGEX.test(email.trim())) return 'Enter a valid email address.';
  return '';
}

export function validatePassword(password) {
  if (!password) return 'Password is required.';
  if (password.length < 6) return 'Password must be at least 6 characters.';
  return '';
}

export function validateFullName(name) {
  if (!name.trim()) return 'Full name is required.';
  if (name.trim().length < 2) return 'Full name must be at least 2 characters.';
  return '';
}

export function validateConfirmPassword(password, confirm) {
  if (!confirm) return 'Please confirm your password.';
  if (password !== confirm) return 'Passwords do not match.';
  return '';
}

export function validateBusiness({ name, type, description }, allowedTypes) {
  const errors = {};
  if (!name.trim()) errors.name = 'Business name is required.';
  else if (name.trim().length < 2) errors.name = 'Business name must be at least 2 characters.';
  else if (name.trim().length > 100) errors.name = 'Business name must be 100 characters or fewer.';

  if (!type) errors.type = 'Select a business type.';
  else if (!allowedTypes.includes(type)) errors.type = 'Invalid business type.';

  if (description && description.length > 1000) {
    errors.description = 'Description must be 1000 characters or fewer.';
  }
  return errors;
}
