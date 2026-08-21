import { type Ref, useId, useRef } from "react";

type QuestionInputProps = {
  value: string;
  disabled: boolean;
  submitDisabled?: boolean;
  textareaRef?: Ref<HTMLTextAreaElement>;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
};

export function QuestionInput({
  value,
  disabled,
  submitDisabled = false,
  textareaRef,
  onChange,
  onSubmit,
}: QuestionInputProps) {
  const id = useId();
  const submitLockRef = useRef(false);

  function submitCurrent(raw: string) {
    if (disabled || submitDisabled || submitLockRef.current) {
      return;
    }
    submitLockRef.current = true;
    onSubmit(raw);
    queueMicrotask(() => {
      submitLockRef.current = false;
    });
  }

  return (
    <div className="question-form">
      <label htmlFor={id} className="visually-hidden">
        Research question
      </label>
      <textarea
        id={id}
        ref={textareaRef}
        rows={3}
        value={value}
        disabled={disabled}
        placeholder="Ask about facts, summaries, comparisons, or limitations in your documents"
        aria-busy={disabled}
        autoComplete="off"
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            event.stopPropagation();
            submitCurrent(event.currentTarget.value);
          }
        }}
      />
      <div className="question-row">
        <p className="hint">Enter to submit · Shift+Enter for a newline</p>
        <button
          type="button"
          className="btn btn-primary"
          disabled={disabled || submitDisabled || !value.trim()}
          onClick={() => submitCurrent(value)}
        >
          {disabled ? "Working…" : "Ask question"}
        </button>
      </div>
    </div>
  );
}
