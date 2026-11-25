import { apiRequest, getCsrfToken } from './authApi'

export interface ManagedUser {
  id: number
  email: string
  full_name: string
  role: 'ADMIN' | 'ENGINEER' | 'VIEWER'
  is_active: boolean
  must_change_password: boolean
}

export interface UserPage {
  items: ManagedUser[]
  total: number
  page: number
  page_size: number
}

export async function fetchUsers(page = 1, pageSize = 25): Promise<UserPage> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })

  return apiRequest<UserPage>(`/api/v1/users?${params.toString()}`, {
    cache: 'no-store',
  })
}

export interface CreateUserRequest {
  email: string
  full_name: string
  role: 'ENGINEER' | 'VIEWER'
  temporary_password: string
}

export async function createUser(payload: CreateUserRequest): Promise<ManagedUser> {
  const csrfToken = await getCsrfToken()

  return apiRequest<ManagedUser>('/api/v1/users', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    body: JSON.stringify(payload),
  })
}

export interface ResetPasswordRequest {
  temporary_password: string
}

export async function resetUserPassword(
  userId: number,
  temporaryPassword: string,
): Promise<ManagedUser> {
  const csrfToken = await getCsrfToken()

  const payload: ResetPasswordRequest = {
    temporary_password: temporaryPassword,
  }

  return apiRequest<ManagedUser>(`/api/v1/users/${userId}/reset-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    body: JSON.stringify(payload),
  })
}

export type DeactivationReason =
  'EMPLOYMENT_ENDED' | 'ACCESS_NO_LONGER_REQUIRED' | 'SECURITY' | 'OTHER'

export async function deactivateUser(
  userId: number,
  reason: DeactivationReason,
): Promise<ManagedUser> {
  const csrfToken = await getCsrfToken()

  return apiRequest<ManagedUser>(`/api/v1/users/${userId}/deactivate`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    body: JSON.stringify({ reason }),
  })
}

export type ReactivationReason = 'REHIRE' | 'ACCESS_RESTORED' | 'OTHER'

export interface ReactivateUserRequest {
  temporary_password: string
  reason: ReactivationReason
}

export async function reactivateUser(
  userId: number,
  payload: ReactivateUserRequest,
): Promise<ManagedUser> {
  const csrfToken = await getCsrfToken()

  return apiRequest<ManagedUser>(`/api/v1/users/${userId}/reactivate`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    body: JSON.stringify(payload),
  })
}
