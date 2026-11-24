import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import Input from '../components/Input';
import Button from '../components/Button';
import ErrorAlert from '../components/ErrorAlert';
import {
  validateConfirmPassword,
  validateEmail,
  validateFullName,
  validatePassword,
} from '../utils/validators';
import { getErrorMessage } from '../utils/errors';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [values, setValues] = useState({
    fullName: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setValues((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: '' }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const found = {
      fullName: validateFullName(values.fullName),
      email: validateEmail(values.email),
      password: validatePassword(values.password),
      confirmPassword: validateConfirmPassword(values.password, values.confirmPassword),
    };
    setErrors(found);
    if (Object.values(found).some(Boolean)) return;

    setSubmitting(true);
    setServerError('');
    try {
      await register({
        fullName: values.fullName.trim(),
        email: values.email.trim(),
        password: values.password,
      });
      navigate('/', { replace: true });
    } catch (err) {
      setServerError(getErrorMessage(err, 'Registration failed. Please try again.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <h1 className="text-2xl font-semibold text-slate-900">Create your account</h1>
      <p className="mt-1 text-sm text-slate-500">Start managing your businesses with AI agents.</p>

      <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-5">
        <ErrorAlert message={serverError} />
        <Input
          id="fullName"
          name="fullName"
          label="Full name"
          placeholder="Jane Doe"
          autoComplete="name"
          value={values.fullName}
          onChange={handleChange}
          error={errors.fullName}
          disabled={submitting}
        />
        <Input
          id="email"
          name="email"
          type="email"
          label="Email"
          placeholder="you@company.com"
          autoComplete="email"
          value={values.email}
          onChange={handleChange}
          error={errors.email}
          disabled={submitting}
        />
        <Input
          id="password"
          name="password"
          type="password"
          label="Password"
          placeholder="At least 6 characters"
          autoComplete="new-password"
          value={values.password}
          onChange={handleChange}
          error={errors.password}
          disabled={submitting}
        />
        <Input
          id="confirmPassword"
          name="confirmPassword"
          type="password"
          label="Confirm password"
          placeholder="Repeat your password"
          autoComplete="new-password"
          value={values.confirmPassword}
          onChange={handleChange}
          error={errors.confirmPassword}
          disabled={submitting}
        />
        <Button type="submit" loading={submitting} className="w-full">
          Create account
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-500">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-indigo-600 hover:text-indigo-700">
          Log in
        </Link>
      </p>
    </>
  );
}
