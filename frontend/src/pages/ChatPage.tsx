export function ChatPage() {
  return (
    <section className="mx-auto flex min-h-[70vh] max-w-3xl flex-col">
      <h2 className="text-2xl font-semibold">Ask a question</h2>
      <p className="mt-2 text-sm leading-6 text-ink/70">
        Answers will include citations, the model that ran, and whether the response came from
        the semantic cache. Retrieval stays inside your tenant and your document permissions.
      </p>
      <div className="mt-6 flex-1 rounded-lg border border-line bg-card p-5 text-sm text-ink/60">
        The conversation view is wired in with the RAG endpoint.
      </div>
      <form className="mt-4 flex gap-2" onSubmit={(event) => event.preventDefault()}>
        <label className="sr-only" htmlFor="question">
          Question
        </label>
        <input
          id="question"
          disabled
          placeholder="Questions open when the RAG endpoint is available"
          className="flex-1 rounded-md border border-line bg-white px-3 py-2 text-sm disabled:bg-paper"
        />
        <button
          type="submit"
          disabled
          className="rounded-md bg-pine px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </section>
  );
}
