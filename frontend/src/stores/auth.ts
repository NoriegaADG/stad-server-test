import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  fetchCurrentUser,
  signIn,
  signOut,
  updatePassword,
  type CurrentUser,
} from '../services/authApi'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(null)
  const loading = ref(false)
  const checkingSession = ref(true)

  const isAuthenticated = computed(() => user.value !== null)

  const userRole = computed(() => user.value?.role ?? null)

  const mustChangePassword = computed(() => user.value?.must_change_password ?? false)

  async function restoreSession(): Promise<void> {
    checkingSession.value = true

    try {
      user.value = await fetchCurrentUser()
    } catch {
      user.value = null
    } finally {
      checkingSession.value = false
    }
  }

  async function login(email: string, password: string): Promise<void> {
    loading.value = true

    try {
      await signIn(email, password)

      user.value = await fetchCurrentUser()
    } finally {
      loading.value = false
    }
  }

  async function logout(): Promise<void> {
    loading.value = true

    try {
      await signOut()

      user.value = null
    } finally {
      loading.value = false
    }
  }

  async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
    loading.value = true

    try {
      await updatePassword(currentPassword, newPassword)

      user.value = null
    } finally {
      loading.value = false
    }
  }

  return {
    user,
    loading,
    checkingSession,
    isAuthenticated,
    userRole,
    mustChangePassword,
    restoreSession,
    login,
    logout,
    changePassword,
  }
})
