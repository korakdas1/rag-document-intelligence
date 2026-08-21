import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { failed: boolean };

export class ConversationErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("conversation_render_failed", error, info.componentStack);
  }

  render() {
    if (this.state.failed) {
      return (
        <p className="error" role="alert">
          The conversation could not be displayed. Refresh to restore saved turns.
        </p>
      );
    }
    return this.props.children;
  }
}
