
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const errorMessage = ref('')

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
          <small>Dashboard</small>
        </div>
      </div>

      <h1>Bienvenido a STAD</h1>

      <p class="subtitle">
        Has iniciado sesión correctamente.
      </p>

      <div v-if="authStore.user" class="profile">
        <p>
          <strong>Nombre:</strong>
          {{ authStore.user.full_name }}
        </p>

        <p>
          <strong>Correo:</strong>
          {{ authStore.user.email }}
        </p>

        <p>
          <strong>Rol:</strong>
          {{ authStore.user.role }}
        </p>
      </div>

      <RouterLink
        v-if="authStore.userRole === 'ADMIN'"
        to="/admin/users"
        class="admin-link"
      >
        Administrar usuarios
      </RouterLink>

      <p v-if="errorMessage" class="error" role="alert">
        {{ errorMessage }}
      </p>

      <button
        type="button"
        :disabled="authStore.loading"
        @click="handleLogout"
      >
        {{ authStore.loading ? 'Cerrando sesión...' : 'Cerrar sesión' }}
      </button>
    </section>
  </main>
</template>

<style scoped>
.admin-link {
  display: block;
  margin-bottom: 20px;
  text-align: center;
  font-weight: 600;
  color: #116c88;
}
</style>