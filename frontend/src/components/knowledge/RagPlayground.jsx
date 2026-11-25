import { useEffect, useRef, useState } from 'react';
import Button from '../Button';
import Card from '../Card';
import ErrorAlert from '../ErrorAlert';
import { queryKnowledge } from '../../services/knowledgeService';
import { getErrorMessage, isCanceled } from '../../utils/errors';

export default function RagPlayground({ businessId, businessName }) {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const controllerRef = useRef(null);

  useEffect(
    () => () => controllerRef.current?.abort(),
    []
  );

  const submit = async (event) => {
    event.preventDefault();
    const prompt = question.trim();
    if (!prompt || loading) return;
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    setError('');
    setQuestion('');
    try {
      const result = await queryKnowledge(businessId, prompt, { signal: controller.signal });
      setMessages((previous) => [...previous, { question: prompt, ...result }]);
    } catch (err) {
      if (!isCanceled(err)) {
        setQuestion(prompt);
        setError(getErrorMessage(err, 'Could not query the Knowledge Base.'));
      }
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setLoading(false);
      }
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-500">
          Ask questions grounded in {businessName}&apos;s indexed documents and business information.
        </p>
        {messages.length > 0 && (
          <Button
            variant="secondary"
            onClick={() => {
              setMessages([]);
              setError('');
            }}
            disabled={loading}
          >
            Clear conversation
          </Button>
        )}
      </div>

      <ErrorAlert message={error} />

      {messages.length > 0 && (
        <div className="space-y-4" aria-live="polite">
          {messages.map((message, index) => (
            <Card key={`${index}-${message.question}`} className="space-y-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Question</p>
                <p className="mt-1 whitespace-pre-wrap text-sm text-slate-900">{message.question}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Answer</p>
                <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800">{message.answer}</p>
              </div>
              {!message.sufficient_context && (
                <p className="text-xs text-amber-700">The available information may not fully answer this question.</p>
              )}
              {message.sources?.length > 0 && (
                <details className="border-t border-slate-100 pt-3">
                  <summary className="cursor-pointer text-sm font-medium text-indigo-700">
                    Sources ({message.sources.length})
                  </summary>
                  <ul className="mt-3 space-y-3">
                    {message.sources.map((source) => (
                      <li key={source.chunk_id} className="rounded-lg bg-slate-50 p-3">
                        <div className="flex flex-wrap justify-between gap-2 text-xs text-slate-500">
                          <span className="font-medium text-slate-700">
                            {source.document_name || source.title || 'Business knowledge'}
                          </span>
                          <span>Relevance {Number(source.score).toFixed(2)}</span>
                        </div>
                        <p className="mt-2 whitespace-pre-wrap text-sm text-slate-600">{source.excerpt}</p>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </Card>
          ))}
        </div>
      )}

      <Card>
        <form onSubmit={submit} className="space-y-3">
          <label htmlFor="rag-question" className="block text-sm font-medium text-slate-700">
            Ask {businessName}
          </label>
          <textarea
            id="rag-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={3}
            maxLength={4000}
            placeholder="For example: What are the opening hours?"
            className="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
            required
            disabled={loading}
          />
          <div className="flex justify-end">
            <Button type="submit" loading={loading} disabled={!question.trim()}>
              Ask
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
