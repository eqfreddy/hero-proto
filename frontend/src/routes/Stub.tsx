interface Props { name: string }
export function Stub({ name }: Props) {
  return (
    <div style={{ padding: 32, textAlign: 'center', color: 'var(--muted)' }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>🚧</div>
      <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)' }}>{name}</div>
      <div style={{ fontSize: 12, marginTop: 6 }}>Coming in the next plan phase.</div>
    </div>
  )
}
