import { useState } from 'react';
import Button from './Button';
import ErrorAlert from './ErrorAlert';
import Input from './Input';
import Select from './Select';
import { inviteMember } from '../services/memberService';
import { ROLE_LABELS } from '../utils/permissions';
import { validateEmail } from '../utils/validators';
import { getErrorMessage } from '../utils/errors';

/**
 * Render conditionally (`{open && <InviteModal .../>}`) so its state resets each time.
 * `allowedRoles` comes from the permission helper (owner: admin/member, admin: member).
 * The backend still enforces who may invite which role.
 */
export default function InviteModal({ businessId, businessName, allowedRoles, onClose, onInvited }) {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState(allowedRoles.includes('member') ? 'member' : allowedRoles[0] || '');
  const [emailError, setEmailError] = useState('');
  const [serverError, setServerError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const err = validateEmail(email);
    setEmailError(err);
    if (err) return;
    if (!allowedRoles.includes(role)) {
      setServerError('You are not allowed to invite this role.');
      return;
    }

    setSubmitting(true);
    setServerError('');
    try {
      await inviteMember(businessId, { email: email.trim(), role });
      await onInvited(email.trim());
    } catch (error) {
      setServerError(getErrorMessage(error, 'Failed to send invitation.'));
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="invite-title"
    >
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <h2 id="invite-title" className="text-lg font-semibold text-slate-900">
          Invite a member
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Invite someone to <span className="font-medium text-slate-700">{businessName}</span>.
        </p>

        <form onSubmit={handleSubmit} noValidate className="mt-5 space-y-5">
          <ErrorAlert message={serverError} />
          <Input
            id="invite-email"
            type="email"
            label="Email address"
            placeholder="teammate@company.com"
            autoFocus
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (emailError) setEmailError('');
            }}
            error={emailError}
            disabled={submitting}
          />
          <Select
            id="invite-role"
            label="Role"
            options={allowedRoles.map((r) => ({ value: r, label: ROLE_LABELS[r] }))}
            value={role}
            onChange={(e) => setRole(e.target.value)}
            disabled={submitting}
          />
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button variant="secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" loading={submitting}>
              Send invitation
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
