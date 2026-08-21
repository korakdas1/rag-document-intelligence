import type { AskResponse } from "../api/types";
import { splitCitations } from "../citations";

type AnswerCardProps = {
  response: AskResponse;
  activeCitationId: string | null;
  onCitationClick: (citationId: string) => void;
};

function statusCopy(response: AskResponse): { title: string; body: string; tone: string } {
  switch (response.grounding_status) {
    case "grounded":
      return {
        title: "Grounded",
        body: "Citations were validated against the evidence shown to the model. That does not prove every claim is semantically supported.",
        tone: "ok",
      };
    case "insufficient_evidence":
      return {
        title: "Not enough evidence",
        body: "The indexed documents do not provide enough support to answer this reliably.",
        tone: "insufficient",
      };
    case "unverified":
      return {
        title: "Unverified",
        body: "This answer could not be fully verified against the retrieved sources.",
        tone: "unverified",
      };
    case "invalid_citation":
      return {
        title: "Invalid citations",
        body: "The model cited identifiers that were not in the evidence set. The answer is not treated as grounded.",
        tone: "bad",
      };
    default:
      return {
        title: "Invalid response format",
        body: "The model returned an invalid response format. Retrieved evidence is still available.",
        tone: "bad",
      };
  }
}

export function AnswerCard({ response, activeCitationId, onCitationClick }: AnswerCardProps) {
  const copy = statusCopy(response);
  const segments = splitCitations(response.answer);
  const showAnswer =
    response.grounding_status === "grounded" ||
    response.grounding_status === "unverified" ||
    Boolean(response.answer.trim());

  return (
    <article className={`answer-card tone-${copy.tone}`}>
      <header>
        <span className="status-badge">{copy.title}</span>
        <p className="status-note">{copy.body}</p>
      </header>
      {showAnswer && response.answer.trim() ? (
        <p className="answer-body">
          {segments.map((segment, index) => {
            if (segment.kind === "text") {
              return <span key={index}>{segment.text}</span>;
            }
            const active = activeCitationId === segment.citationId;
            return (
              <button
                key={`${segment.citationId}-${index}`}
                type="button"
                className={active ? "cite-chip active" : "cite-chip"}
                onClick={() => onCitationClick(segment.citationId)}
                aria-pressed={active}
              >
                [{segment.citationId}]
              </button>
            );
          })}
        </p>
      ) : null}
      {response.diagnostics.ambiguous_followup ? (
        <p className="muted">
          This follow-up was ambiguous. Who do you mean? Name the people or topic.
        </p>
      ) : null}
    </article>
  );
}
