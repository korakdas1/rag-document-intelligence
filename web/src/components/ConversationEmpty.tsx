type ConversationEmptyProps = {
  hasDocuments: boolean;
};

export function ConversationEmpty({ hasDocuments }: ConversationEmptyProps) {
  if (!hasDocuments) {
    return (
      <div className="empty-state">
        <h3>Add a document to begin</h3>
        <p>Upload a PDF, Markdown, or text file in the library, then ask a question.</p>
      </div>
    );
  }
  return (
    <div className="empty-state">
      <h3>Ask a question about your documents.</h3>
      <p>
        Follow-up conversation can clarify the question. Indexed documents remain the only
        evidence.
      </p>
    </div>
  );
}
