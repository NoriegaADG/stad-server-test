
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')

const errorMessage = ref('')

async function handleSubmit() {
  errorMessage.value = ''

  if (newPassword.value.length < 12) {
    errorMessage.value =
      'La nueva contraseña debe tener al menos 12 caracteres'
    return
  }

  if (newPassword.value !== confirmPassword.value) {
    errorMessage.value =
      'Las contraseñas nuevas no coinciden'
    return
  }

  if (newPassword.value === currentPassword.value) {
    errorMessage.value =
      'La nueva contraseña debe ser diferente de la actual'
    return
  }

  try {
    await authStore.changePassword(
      currentPassword.value,
      newPassword.value,
    )

    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''

    // El backend invalida la sesión.
    await router.replace('/login')
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : 'No fue posible cambiar la contraseña'
  }
}

async function handleLogout() {
  errorMessage.value = ''

  try {
    await authStore.logout()
    await router.replace('/login')
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : 'No fue posible cerrar sesión'
  }
}
</script>

<template>
  <main class="page">
    <section class="login-card">
      <div class="brand">
        <div class="brand-icon">S</div>

        <div>
          <strong>STAD</strong>
          <small>Seguridad de la cuenta</small>
        </div>
      </div>

      <h1>Cambiar contraseña</h1>

      <p class="subtitle">
        Por seguridad, debes cambiar tu contraseña
        temporal antes de utilizar STAD.
      </p>

      <form @submit.prevent="handleSubmit">
        <label for="current-password">
          Contraseña actual
        </label>

        <input
          id="current-password"
          v-model="currentPassword"
          type="password"
          autocomplete="current-password"
          required
        />

        <label for="new-password">
          Nueva contraseña
        </label>

        <input
          id="new-password"
          v-model="newPassword"
          type="password"
          autocomplete="new-password"
          minlength="12"
          maxlength="1024"
          required
        />

        <label for="confirm-password">
          Confirmar nueva contraseña
        </label>

        <input
          id="confirm-password"
          v-model="confirmPassword"
          type="password"
          autocomplete="new-password"
          minlength="12"
          maxlength="1024"
          required
        />

        <p
          v-if="errorMessage"
          class="error"
          role="alert"
        >
          {{ errorMessage }}
        </p>

        <button
          type="submit"
          :disabled="authStore.loading"
        >
          {{
            authStore.loading
              ? 'Actualizando...'
              : 'Actualizar contraseña'
          }}
        </button>

        <button
          type="button"
          class="logout-button"
          :disabled="authStore.loading"
          @click="handleLogout"
        >
          Cerrar sesión
        </button>
      </form>

      <footer>
        Después del cambio deberás iniciar sesión nuevamente.
      </footer>
    </section>
  </main>
</template>

<style scoped>
.logout-button {
  margin-top: 12px;
  background: #e2e8f0;
  color: #334155;
}

.logout-button:hover:not(:disabled) {
  background: #cbd5e1;
}
</style>