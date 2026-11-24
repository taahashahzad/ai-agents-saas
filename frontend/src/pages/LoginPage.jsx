import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import Input from '../components/Input';
import Button from '../components/Button';
import ErrorAlert from '../components/ErrorAlert';
import { validateEmail, validatePassword } from '../utils/validators';
import { getErrorMessage } from '../utils/errors';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = location.state?.from?.pathname || '/';

  const [values, setValues] = useState({ email: '', password: '' });
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
      email: validateEmail(values.email),
      password: validatePassword(values.password),
    };
    setErrors(found);
    if (found.email || found.password) return;

    setSubmitting(true);
    setServerError('');
    try {
      await login({ email: values.email.trim(), password: values.password });
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setServerError(getErrorMessage(err, 'Login failed. Please try again.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <h1 className="text-2xl font-semibold text-slate-900">Welcome back</h1>
      <p className="mt-1 text-sm text-slate-500">Sign in to your account to continue.</p>

      <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-5">
        <ErrorAlert message={serverError} />
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
          placeholder="••••••••"
          autoComplete="current-password"
          value={values.password}
          onChange={handleChange}
          error={errors.password}
          disabled={submitting}
        />
        <Button type="submit" loading={submitting} className="w-full">
          Log in
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-500">
        Don&apos;t have an account?{' '}
        <Link to="/register" className="font-medium text-indigo-600 hover:text-indigo-700">
          Sign up
        </Link>
      </p>
    </>
  );
}
