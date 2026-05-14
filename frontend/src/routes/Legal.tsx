import { Link } from 'react-router-dom'

const PageWrap = ({ children }: { children: React.ReactNode }) => (
  <div style={{ maxWidth: 720, margin: '0 auto', padding: '6px 10px 24px' }}>
    {children}
    <div style={{ marginTop: 20, fontSize: 12, color: 'var(--muted)', textAlign: 'center' }}>
      Questions? <a href="mailto:privacy@hero-proto.local" style={{ color: 'var(--accent)' }}>privacy@hero-proto.local</a>
      <div style={{ marginTop: 8 }}>
        <Link to="/app/lobby" style={{ color: 'var(--muted)' }}>← Back to game</Link>
      </div>
    </div>
  </div>
)

const H1 = ({ children }: { children: React.ReactNode }) => (
  <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)', marginBottom: 4 }}>{children}</h1>
)
const Lead = ({ children }: { children: React.ReactNode }) => (
  <p style={{ color: 'var(--muted)', fontSize: 12, marginTop: 0, marginBottom: 14 }}>{children}</p>
)
const H2 = ({ children }: { children: React.ReactNode }) => (
  <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', marginTop: 16, marginBottom: 6 }}>{children}</h2>
)
const P = ({ children }: { children: React.ReactNode }) => (
  <p style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--text)', margin: '6px 0' }}>{children}</p>
)
const UL = ({ children }: { children: React.ReactNode }) => (
  <ul style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--text)', paddingLeft: 20, margin: '6px 0' }}>{children}</ul>
)

export function PrivacyRoute() {
  return (
    <PageWrap>
      <H1>Privacy Policy</H1>
      <Lead>Last updated: 2026-04-29</Lead>

      <H2>What we collect</H2>
      <UL>
        <li><strong>Email + password hash</strong> — for login. Bcrypt-hashed, never stored in plaintext.</li>
        <li><strong>Gameplay data</strong> — heroes, gear, currencies, battle history, guild membership, arena results.</li>
        <li><strong>Device push token</strong> (if you opt in to notifications) — to send notifications about events and friend requests.</li>
        <li><strong>Server logs</strong> — request method/path/status/latency. IP stored short-term for rate limiting.</li>
        <li><strong>Payment records</strong> (only if you purchase) — transaction ID, amount, SKU. Card numbers handled by Apple / Google / Stripe — never seen by us.</li>
      </UL>

      <H2>What we don't collect</H2>
      <UL>
        <li>No advertising IDs, no cross-site tracking, no third-party trackers.</li>
        <li>No location beyond IP-derived country.</li>
        <li>No microphone, camera, contacts, or other sensor data.</li>
        <li>We do not sell your data. We do not share it with marketers. We do not use it to train AI models.</li>
      </UL>

      <H2>Children's privacy</H2>
      <P>This game is not directed at children under 13. We do not knowingly collect data from anyone under 13. The age gate on first launch enforces this; if you're under 13 you cannot create an account.</P>

      <H2>Your rights</H2>
      <UL>
        <li><strong>Access:</strong> most of your data is visible in-game on the Me tab. Full export from Account → Export my data.</li>
        <li><strong>Delete:</strong> Account → Delete account permanently. Hard-deleted within 24 hours.</li>
        <li><strong>EU/UK (GDPR), California (CCPA):</strong> additional rights apply. Email <a href="mailto:privacy@hero-proto.local" style={{ color: 'var(--accent)' }}>privacy@hero-proto.local</a>.</li>
      </UL>

      <H2>Retention</H2>
      <UL>
        <li>Active account data: as long as the account exists.</li>
        <li>Deleted accounts: hard-deleted within 24 hours; audit log kept 90 days for fraud prevention.</li>
        <li>Server logs: 30 days.</li>
        <li>Payment records: 7 years (regulatory requirement).</li>
      </UL>

      <H2>Storage</H2>
      <P>localStorage holds your auth token, sound preferences, and age-gate confirmation. Service worker caches static assets for offline use. No tracking cookies.</P>
    </PageWrap>
  )
}

export function TermsRoute() {
  return (
    <PageWrap>
      <H1>Terms of Service</H1>
      <Lead>Last updated: 2026-04-29. By using hero-proto, you agree to these terms.</Lead>

      <H2>Plain English</H2>
      <UL>
        <li>Don't cheat, abuse, or harass other players.</li>
        <li>You own your purchased items; you don't own the game itself.</li>
        <li>Refund window: 14 days for accidental purchases that haven't been consumed.</li>
        <li>If you're under 13, please don't use this game.</li>
        <li>If anything here conflicts with the <Link to="/app/privacy" style={{ color: 'var(--accent)' }}>privacy policy</Link>, the privacy policy wins.</li>
      </UL>

      <H2>Eligibility</H2>
      <P>You must be at least 13 years old to register an account. Some jurisdictions set the minimum higher; you're responsible for knowing your local rules.</P>

      <H2>Your account</H2>
      <P>You're responsible for keeping your password and 2FA codes safe. Don't share your account. We can suspend or terminate accounts that violate these terms.</P>

      <H2>Purchases</H2>
      <P>Purchases are processed by Apple, Google, or Stripe under their respective terms. Virtual currencies and items are non-transferable, have no real-world cash value, and are licensed to you for in-game use only.</P>

      <H2>Acceptable use</H2>
      <UL>
        <li>No exploits, automated clients, or third-party tools that interact with the game on your behalf.</li>
        <li>No harassment, hate speech, or doxing in chat or guild messages.</li>
        <li>No attempts to access another user's account or our infrastructure.</li>
      </UL>

      <H2>Changes</H2>
      <P>We may update these terms. Material changes will be announced in-app at least 14 days before taking effect.</P>

      <H2>Disclaimer</H2>
      <P>The game is provided "as is." We make no warranties about uptime or fitness for a particular purpose. Our liability is limited to the amount you have paid us in the past 12 months.</P>
    </PageWrap>
  )
}
