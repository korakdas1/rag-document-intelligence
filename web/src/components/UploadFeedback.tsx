export type UploadFailure = Readonly<{
  filename: string;
  reason: string;
  retryFile?: File;
}>;

export type UploadFeedbackState =
  | Readonly<{ kind: "progress"; current: number; total: number }>
  | Readonly<{ kind: "result"; added: number; failures: readonly UploadFailure[] }>;

type UploadFeedbackProps = {
  feedback: UploadFeedbackState | null;
  onRetry: (files: File[]) => void;
  onDismiss: () => void;
};

function retryableUploadFiles(feedback: UploadFeedbackState | null): File[] {
  if (feedback?.kind !== "result") return [];
  return feedback.failures.flatMap((failure) => failure.retryFile ? [failure.retryFile] : []);
}

function successSummary(added: number): string {
  return `${added} document${added === 1 ? "" : "s"} added.`;
}

function failureSummary(added: number, failed: number): string {
  if (added > 0) return `${added} added · ${failed} not added`;
  return `${failed} file${failed === 1 ? "" : "s"} not added`;
}

export function UploadFeedback({ feedback, onRetry, onDismiss }: UploadFeedbackProps) {
  if (!feedback) return null;

  if (feedback.kind === "progress") {
    return (
      <div className="upload-feedback" role="status" aria-live="polite" data-testid="upload-status">
        <strong>Uploading files</strong>
        <span>Uploading {feedback.current} of {feedback.total}…</span>
      </div>
    );
  }

  if (feedback.failures.length === 0) {
    return (
      <div className="upload-feedback" role="status" aria-live="polite" data-testid="upload-status">
        <strong>Upload complete</strong>
        <span>{successSummary(feedback.added)}</span>
      </div>
    );
  }

  const retryFiles = retryableUploadFiles(feedback);
  return (
    <section className="upload-feedback is-error" role="alert" data-testid="upload-error">
      <strong>{feedback.added > 0 ? "Upload incomplete" : "Files not added"}</strong>
      <span>{failureSummary(feedback.added, feedback.failures.length)}</span>
      <ul className="upload-failures">
        {feedback.failures.map((failure, index) => (
          <li key={`${failure.filename}-${index}`}>
            <strong title={failure.filename}>{failure.filename}</strong>
            <span>{failure.reason}</span>
          </li>
        ))}
      </ul>
      <div className="upload-feedback-actions">
        {retryFiles.length > 0 ? (
          <button type="button" className="btn btn-quiet" onClick={() => onRetry(retryFiles)}>
            Retry failed files
          </button>
        ) : null}
        <button type="button" className="btn btn-quiet" onClick={onDismiss}>
          Dismiss
        </button>
      </div>
    </section>
  );
}
