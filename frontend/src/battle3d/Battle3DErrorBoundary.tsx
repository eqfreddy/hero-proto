import { Component, type ReactNode } from "react";

interface State {
  hasError: boolean;
}

export class Battle3DErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(err: Error) {
    // eslint-disable-next-line no-console
    console.error("[battle-3d] scene crashed, falling back to watermark", err);
  }

  render() {
    if (this.state.hasError) {
      return <div className="battle-watermark">BATTLE</div>;
    }
    return this.props.children;
  }
}
