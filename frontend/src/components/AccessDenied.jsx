import { Link } from 'react-router-dom';
import Card from './Card';

export default function AccessDenied({
  title = 'Access restricted',
  message = "Your role in this business doesn't include access to this page.",
}) {
  return (
    <Card className="mx-auto max-w-lg text-center">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-50 text-amber-600">
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
          />
        </svg>
      </div>
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      <p className="mt-1 text-sm text-slate-500">{message}</p>
      <Link
        to="/"
        className="mt-5 inline-block text-sm font-medium text-indigo-600 hover:text-indigo-700"
      >
        &larr; Back to dashboard
      </Link>
    </Card>
  );
}
