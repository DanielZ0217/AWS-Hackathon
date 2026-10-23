import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { buttonSecondary } from "./buttonStyles";

interface Props {
  children: ReactNode;
}

interface State {
  failed: boolean;
}

// Keeps one broken panel from blanking the whole page.
export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("A panel failed to render", error, info.componentStack);
  }

  render(): ReactNode {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="border border-line bg-surface p-4">
        <p className="font-bold">Something on this screen failed to load.</p>
        <p className="mt-1 text-ink-soft">The rest of the page still works.</p>
        <button type="button" className={`${buttonSecondary} mt-3`} onClick={() => this.setState({ failed: false })}>
          Try again
        </button>
      </div>
    );
  }
}
