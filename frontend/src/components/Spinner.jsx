export default function Spinner({ fullScreen = false, label = '', size = 'md' }) {
  const sizes = { sm: 'h-4 w-4 border-2', md: 'h-8 w-8 border-[3px]', lg: 'h-12 w-12 border-4' };
  const spinner = (
    <div className="flex flex-col items-center justify-center gap-3" role="status">
      <div
        className={`${sizes[size]} animate-spin rounded-full border-slate-200 border-t-indigo-600`}
      />
      {label && <p className="text-sm text-slate-500">{label}</p>}
    </div>
  );

  if (fullScreen) {
    return <div className="flex min-h-screen items-center justify-center">{spinner}</div>;
  }
  return <div className="flex items-center justify-center py-12">{spinner}</div>;
}
