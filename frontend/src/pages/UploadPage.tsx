import { type FormEvent, useEffect, useState } from "react";

import {
  ApiError,
  deleteDocument,
  listDocuments,
  uploadDocument,
  type DocumentSummary,
} from "../api/client";

export function UploadPage() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [accessLevel, setAccessLevel] = useState("internal");
  const [department, setDepartment] = useState("");
  const [allowedRoles, setAllowedRoles] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formKey, setFormKey] = useState(0);

  async function refresh() {
    const rows = await listDocuments();
    setDocuments(rows);
  }

  useEffect(() => {
    let cancelled = false;
    listDocuments()
      .then((rows) => {
        if (!cancelled) {
          setDocuments(rows);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Could not list documents.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Choose a PDF, text, or Markdown file.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await uploadDocument(file, {
        access_level: accessLevel,
        department,
        allowed_roles: allowedRoles,
      });
      setFile(null);
      setFormKey((value) => value + 1);
      await refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Upload failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function onDelete(documentId: string) {
    setError(null);
    try {
      await deleteDocument(documentId);
      await refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Delete failed.");
    }
  }

  return (
    <section className="mx-auto max-w-3xl">
      <h2 className="text-2xl font-semibold">Documents</h2>
      <p className="mt-2 text-sm leading-6 text-ink/70">
        PDF, plain text, and Markdown are extracted, chunked, and embedded for your tenant.
      </p>
      <form onSubmit={onSubmit} className="mt-6 space-y-4 rounded-lg border border-line bg-card p-5">
        <label className="block text-sm">
          File
          <input
            key={formKey}
            type="file"
            accept=".pdf,.txt,.md,text/plain,text/markdown,application/pdf"
            required
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="mt-1 block w-full text-sm"
          />
        </label>
        <label className="block text-sm">
          Access level
          <select
            value={accessLevel}
            onChange={(event) => setAccessLevel(event.target.value)}
            className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2"
          >
            <option value="public">public</option>
            <option value="internal">internal</option>
            <option value="private">private</option>
          </select>
        </label>
        <label className="block text-sm">
          Department
          <input
            value={department}
            onChange={(event) => setDepartment(event.target.value)}
            className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2"
          />
        </label>
        <label className="block text-sm">
          Allowed roles
          <input
            value={allowedRoles}
            onChange={(event) => setAllowedRoles(event.target.value)}
            placeholder="ADMIN,MANAGER"
            className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2"
          />
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-pine px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {submitting ? "Uploading…" : "Upload"}
        </button>
        {error ? <p className="text-sm text-red-800">{error}</p> : null}
      </form>
      <ul className="mt-6 divide-y divide-line rounded-lg border border-line bg-card">
        {documents.length === 0 ? (
          <li className="px-4 py-3 text-sm text-ink/60">No documents yet.</li>
        ) : null}
        {documents.map((document) => (
          <li key={document.id} className="flex items-center justify-between gap-3 px-4 py-3">
            <div>
              <p className="text-sm font-medium">{document.filename}</p>
              <p className="text-xs text-ink/60">{document.chunk_count} chunks</p>
            </div>
            <button
              type="button"
              onClick={() => onDelete(document.id)}
              className="text-sm text-red-800"
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
