import { forwardRef } from "react";
import type { AskResponse } from "../api/types";
import { AnswerCard } from "./AnswerCard";

type ConversationTurnProps = {
  question: string;
  response: AskResponse | null;
  error: string | null;
  pending: boolean;
  retryable?: boolean;
  retryDisabled?: boolean;
  turnId: string;
  activeCitationId: string | null;
  onCitationClick: (citationId: string) => void;
  onRetry: () => void;
};

export const ConversationTurn = forwardRef<HTMLLIElement, ConversationTurnProps>(
  function ConversationTurn(
    {
      question,
      response,
      error,
      pending,
      retryable = true,
      retryDisabled = false,
      turnId,
      activeCitationId,
      onCitationClick,
      onRetry,
    },
    ref,
  ) {
    return (
      <li className="turn" ref={ref} data-turn-id={turnId}>
        <p className="turn-q">
          <span className="who">You</span>
          <span className="ask">{question}</span>
        </p>
        {error ? (
          <div className="turn-error" role="alert">
            <p>{error}</p>
            {retryable ? (
              <button
                type="button"
                className="btn btn-quiet"
                onClick={onRetry}
                disabled={pending || retryDisabled}
              >
                Retry
              </button>
            ) : null}
          </div>
        ) : null}
        {pending && !error && !response ? (
          <p className="loading" role="status">
            Working…
          </p>
        ) : null}
        {response ? (
          <AnswerCard
            response={response}
            activeCitationId={activeCitationId}
            onCitationClick={onCitationClick}
          />
        ) : null}
      </li>
    );
  },
);
