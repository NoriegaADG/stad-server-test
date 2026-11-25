
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const { loading } = storeToRefs(authStore)

const email = ref('')
const password = ref('')
const errorMessage = ref('')

async function handleLogin() {
  errorMessage.value = ''

  try {
    await authStore.login(
      email.value.trim(),
      password.value,
    )

    password.value = ''

    if (authStore.mustChangePassword) {
      await router.replace('/change-password')
    } else {
      await router.replace('/dashboard')
    }
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : 'No fue posible iniciar sesión'
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
          <small>Server Test Automation Dashboard</small>
        </div>
      </div>

      <h1>Iniciar sesión</h1>

      <p class="subtitle">
        Ingresa tus credenciales para acceder a STAD.
      </p>

      <form @submit.prevent="handleLogin">
        <label for="email">Correo electrónico</label>

        <input
          id="email"
          v-model="email"
          type="email"
          autocomplete="username"
          placeholder="usuario@empresa.com"
          required
        />

        <label for="password">Contraseña</label>

        <input
          id="password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
        />

        <p
          v-if="errorMessage"
          class="error"
          role="alert"
        >
          {{ errorMessage }}
        </p>

        <button type="submit" :disabled="loading">
          {{ loading ? 'Ingresando...' : 'Ingresar' }}
        </button>
      </form>

      <footer>STAD · Acceso seguro</footer>
    </section>
  </main>
</template>