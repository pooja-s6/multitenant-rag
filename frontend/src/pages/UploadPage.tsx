export function UploadPage() {
  return (
    <section className="mx-auto max-w-3xl">
      <h2 className="text-2xl font-semibold">Documents</h2>
      <p className="mt-2 text-sm leading-6 text-ink/70">
        Uploads will accept PDF, plain text, and Markdown. The ingestion pipeline extracts text,
        cleans it, splits it into chunks, embeds those chunks, and stores the document with
        tenant and permission metadata.
      </p>
      <div className="mt-6 rounded-lg border border-dashed border-line bg-card p-8 text-sm text-ink/70">
        File upload opens when document ingestion is available. Managers and admins will be able
        to set department, access level, and allowed roles on each document.
      </div>
    </section>
  );
}
