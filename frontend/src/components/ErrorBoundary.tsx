import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary] Uncaught error:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-stone-50 p-8 text-center">
          <p className="text-lg text-stone-700">Что-то пошло не так. Обновите страницу.</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded border border-stone-900 px-4 py-2 text-stone-900 hover:bg-stone-100"
          >
            Обновить
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
