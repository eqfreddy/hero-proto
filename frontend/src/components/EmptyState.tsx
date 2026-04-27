interface Props { icon?: string; message: string; hint?: string }
export function EmptyState({ icon = '📭', message, hint }: Props) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">{icon}</div>
      <div className="empty-state-msg">{message}</div>
      {hint && <div className="empty-state-hint">{hint}</div>}
    </div>
  )
}
