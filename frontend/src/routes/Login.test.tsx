import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Login } from './Login'

const h = vi.hoisted(() => ({ apiFetch: vi.fn() }))
vi.mock('../api/client', () => ({ apiFetch: (...a: unknown[]) => h.apiFetch(...a) }))
vi.mock('../store/ui', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }))

// Set an input's value the way Chrome autofill does: through the native DOM
// setter, WITHOUT dispatching a React change event. This leaves the controlled
// component's state empty while the DOM holds a value — the exact desync that
// made autofilled sign-ins POST empty credentials.
function autofill(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!
  setter.call(input, value)
}

function bodyOf(call: unknown[]): { email: string; password: string } {
  const opts = call[1] as { body: string }
  return JSON.parse(opts.body)
}

describe('Login sign-in', () => {
  beforeEach(() => {
    h.apiFetch.mockReset()
    h.apiFetch.mockResolvedValue({ access_token: 'tok', refresh_token: 'ref' })
  })

  function renderLogin() {
    return render(<MemoryRouter><Login /></MemoryRouter>)
  }

  it('submits autofilled credentials even when React onChange never fired', async () => {
    renderLogin()
    const email = screen.getByLabelText(/email/i) as HTMLInputElement
    const password = screen.getByLabelText(/^password$/i) as HTMLInputElement

    autofill(email, 'saved@user.com')
    autofill(password, 'hunter2pass')

    fireEvent.submit(email.closest('form')!)

    await waitFor(() => expect(h.apiFetch).toHaveBeenCalled())
    const body = bodyOf(h.apiFetch.mock.calls[0])
    expect(body.email).toBe('saved@user.com')
    expect(body.password).toBe('hunter2pass')
  })

  it('still submits normally typed credentials', async () => {
    renderLogin()
    const email = screen.getByLabelText(/email/i) as HTMLInputElement
    const password = screen.getByLabelText(/^password$/i) as HTMLInputElement

    fireEvent.change(email, { target: { value: 'typed@user.com' } })
    fireEvent.change(password, { target: { value: 'typedpass1' } })
    fireEvent.submit(email.closest('form')!)

    await waitFor(() => expect(h.apiFetch).toHaveBeenCalled())
    const body = bodyOf(h.apiFetch.mock.calls[0])
    expect(body.email).toBe('typed@user.com')
    expect(body.password).toBe('typedpass1')
  })
})
