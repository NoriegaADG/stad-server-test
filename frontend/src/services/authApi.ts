
export interface CurrentUser {
  id: number
  email: string
  full_name: string
  role: 'ADMIN' | 'ENGINEER' | 'VIEWER'
  is_active: boolean
  must_change_password: boolean
}

interface LoginResponse {
  message: string
  must_change_password: boolean
}

interface CsrfResponse {
  csrf_token: string
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    credentials: 'same-origin',
    ...options,
  })

  if (!response.ok) {
    const payload: { detail?: unknown } =
      await response.json().catch(() => ({}))

    let message = `Error HTTP ${response.status}`

    if (typeof payload.detail === 'string') {
      message = payload.detail
    } else if (response.status === 401) {
      message = 'Credenciales incorrectas o sesión vencida'
    }

    throw new Error(message)
  }

  return response.json() as Promise<T>
}

export async function getCsrfToken(): Promise<string> {
  const data = await apiRequest<CsrfResponse>(
    '/api/v1/auth/csrf',
    { cache: 'no-store' },
  )

  return data.csrf_token
}

export async function signIn(
  email: string,
  password: string,
): Promise<LoginResponse> {
  const csrfToken = await getCsrfToken()

  return apiRequest<LoginResponse>(
    '/api/v1/auth/login',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken,
      },
      body: JSON.stringify({
        email,
        password,
      }),
    },
  )
}

export function fetchCurrentUser(): Promise<CurrentUser> {
  return apiRequest<CurrentUser>(
    '/api/v1/auth/me',
  )
}

export async function signOut(): Promise<void> {
  const csrfToken = await getCsrfToken()

  await apiRequest<{ message: string }>(
    '/api/v1/auth/logout',
    {
      method: 'POST',
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    },
  )
}

interface ChangePasswordResponse {
  message: string
  login_required: boolean
}

export async function updatePassword(
  currentPassword: string,
  newPassword: string,
): Promise<ChangePasswordResponse> {
  const csrfToken = await getCsrfToken()

  return apiRequest<ChangePasswordResponse>(
    '/api/v1/auth/change-password',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken,
      },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    },
  )
}