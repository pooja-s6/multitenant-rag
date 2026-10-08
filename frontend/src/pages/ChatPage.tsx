import { type FormEvent, useState } from "react";

import { ApiError, askQuestion, type RagAnswer } from "../api/client";

type Turn = {
  question: string;
  answer: RagAnswer;
};

export function ChatPage() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = question.trim();
    if (!text) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const answer = await askQuestion(text);
      setTurns((current) => [...current, { question: text, answer }]);
      setQuestion("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The API did not respond.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto flex min-h-[70vh] max-w-3xl flex-col">
      <h2 className="text-2xl font-semibold">Ask a question</h2>
      <p className="mt-2 text-sm leading-6 text-ink/70">
        Answers include citations, the model that ran, and whether the response came from the cache.
      </p>
      <div className="mt-6 flex-1 space-y-4">
        {turns.length === 0 ? (
          <p className="rounded-lg border border-line bg-card p-5 text-sm text-ink/60">
            Ask about a document you are allowed to read.
          </p>
        ) : null}
        {turns.map((turn) => (
          <article key={turn.answer.request_id} className="rounded-lg border border-line bg-card p-5">
            <p className="text-sm font-medium">{turn.question}</p>
            <p className="mt-3 text-sm leading-6">{turn.answer.answer}</p>
            <p className="mt-3 text-xs text-ink/60">
              {turn.answer.model_used}
              {" · "}
              {turn.answer.cache_hit ? "cache hit" : "cache miss"}
              {" · "}
              {turn.answer.latency} ms
            </p>
            {turn.answer.sources.length > 0 ? (
              <ul className="mt-3 space-y-2">
                {turn.answer.sources.map((source) => (
                  <li key={source.chunk_id} className="rounded-md bg-moss px-3 py-2 text-xs leading-5">
                    <span className="font-medium">{source.filename}</span>
                    {source.page_number ? ` · page ${source.page_number}` : ""}
                    {` · ${source.score.toFixed(2)}`}
                    <span className="mt-1 block text-ink/80">{source.excerpt}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </article>
        ))}
        {error ? <p className="text-sm text-red-800">{error}</p> : null}
      </div>
      <form className="mt-4 flex gap-2" onSubmit={onSubmit}>
        <label className="sr-only" htmlFor="question">
          Question
        </label>
        <input
          id="question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask about your documents"
          className="flex-1 rounded-md border border-line bg-white px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-pine px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {submitting ? "Sending…" : "Send"}
        </button>
      </form>
    </section>
  );
}
