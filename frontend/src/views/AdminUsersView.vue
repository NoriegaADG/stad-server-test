<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  createUser,
  deactivateUser,
  fetchUsers,
  reactivateUser,
  resetUserPassword,
  type DeactivationReason,
  type ManagedUser,
  type ReactivationReason,
} from '../services/usersApi'

const PAGE_SIZE = 25

const users = ref<ManagedUser[]>([])
const page = ref(1)
const total = ref(0)

const loading = ref(false)
const errorMessage = ref('')

const creating = ref(false)
const createError = ref('')
const createSuccess = ref('')

const newUserName = ref('')
const newUserEmail = ref('')
const newUserRole = ref<'ENGINEER' | 'VIEWER'>('ENGINEER')
const temporaryPassword = ref('')

const resetTarget = ref<ManagedUser | null>(null)
const resetTemporaryPassword = ref('')
const resetConfirmPassword = ref('')
const resetting = ref(false)
const resetError = ref('')
const resetSuccess = ref('')

const deactivateTarget = ref<ManagedUser | null>(null)
const deactivationReason = ref<DeactivationReason>('EMPLOYMENT_ENDED')
const confirmDeactivation = ref(false)
const deactivating = ref(false)
const deactivateError = ref('')
const deactivateSuccess = ref('')

const reactivateTarget = ref<ManagedUser | null>(null)
const reactivationReason = ref<ReactivationReason>('REHIRE')
const reactivationTemporaryPassword = ref('')
const reactivationConfirmPassword = ref('')
const reactivating = ref(false)
const reactivateError = ref('')
const reactivateSuccess = ref('')

async function loadUsers() {
  loading.value = true
  errorMessage.value = ''

  try {
    const response = await fetchUsers(page.value, PAGE_SIZE)

    users.value = response.items
    total.value = response.total
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No fue posible cargar los usuarios'
  } finally {
    loading.value = false
  }
}

async function previousPage() {
  if (page.value <= 1) return

  page.value--
  await loadUsers()
}

async function nextPage() {
  if (page.value * PAGE_SIZE >= total.value) {
    return
  }

  page.value++
  await loadUsers()
}

async function handleCreateUser() {
  if (creating.value) return

  createError.value = ''
  createSuccess.value = ''

  if (temporaryPassword.value.length < 12) {
    createError.value = 'La contraseña temporal debe tener al menos 12 caracteres'
    return
  }

  creating.value = true

  try {
    const created = await createUser({
      email: newUserEmail.value.trim().toLowerCase(),
      full_name: newUserName.value.trim(),
      role: newUserRole.value,
      temporary_password: temporaryPassword.value,
    })

    createSuccess.value = `Usuario ${created.email} registrado correctamente`

    newUserName.value = ''
    newUserEmail.value = ''
    newUserRole.value = 'ENGINEER'
    temporaryPassword.value = ''

    page.value = 1
    await loadUsers()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : 'No fue posible crear el usuario'
  } finally {
    creating.value = false
  }
}

function startReset(user: ManagedUser) {
  if (user.role === 'ADMIN' || !user.is_active) {
    return
  }

  resetTarget.value = user
  resetTemporaryPassword.value = ''
  resetConfirmPassword.value = ''
  resetError.value = ''
  resetSuccess.value = ''
}

function cancelReset() {
  if (resetting.value) return

  resetTarget.value = null
  resetTemporaryPassword.value = ''
  resetConfirmPassword.value = ''
  resetError.value = ''
}

async function handleResetPassword() {
  const target = resetTarget.value

  if (!target || resetting.value) {
    return
  }

  resetError.value = ''
  resetSuccess.value = ''

  if (resetTemporaryPassword.value.length < 12) {
    resetError.value = 'La contraseña temporal debe tener al menos 12 caracteres'
    return
  }

  if (resetTemporaryPassword.value !== resetConfirmPassword.value) {
    resetError.value = 'Las contraseñas no coinciden'
    return
  }

  resetting.value = true

  try {
    await resetUserPassword(target.id, resetTemporaryPassword.value)

    resetSuccess.value = `Contraseña restablecida correctamente para ${target.email}`
    resetTemporaryPassword.value = ''
    resetConfirmPassword.value = ''
    resetTarget.value = null

    await loadUsers()
  } catch (error) {
    resetError.value =
      error instanceof Error ? error.message : 'No fue posible restablecer la contraseña'
  } finally {
    resetting.value = false
  }
}

function startDeactivation(user: ManagedUser) {
  if (user.role === 'ADMIN' || !user.is_active || deactivating.value) {
    return
  }

  if (resetting.value) return

  resetTarget.value = null
  resetTemporaryPassword.value = ''
  resetConfirmPassword.value = ''
  deactivateTarget.value = user
  deactivationReason.value = 'EMPLOYMENT_ENDED'
  confirmDeactivation.value = false
  deactivateError.value = ''
  deactivateSuccess.value = ''
}

function cancelDeactivation() {
  if (deactivating.value) return

  deactivateTarget.value = null
  deactivationReason.value = 'EMPLOYMENT_ENDED'
  confirmDeactivation.value = false
  deactivateError.value = ''
}

async function handleDeactivateUser() {
  const target = deactivateTarget.value

  if (!target || deactivating.value) return

  deactivateError.value = ''
  deactivateSuccess.value = ''

  if (!confirmDeactivation.value) {
    deactivateError.value = 'Debes confirmar la desactivación'
    return
  }

  deactivating.value = true

  try {
    await deactivateUser(target.id, deactivationReason.value)

    deactivateSuccess.value = `Usuario ${target.email} desactivado correctamente`

    deactivateTarget.value = null
    confirmDeactivation.value = false

    await loadUsers()
  } catch (error) {
    deactivateError.value =
      error instanceof Error ? error.message : 'No fue posible desactivar al usuario'
  } finally {
    deactivating.value = false
  }
}

function startReactivation(user: ManagedUser) {
  if (
    user.role === 'ADMIN' ||
    user.is_active ||
    reactivating.value ||
    deactivating.value ||
    resetting.value
  ) {
    return
  }

  resetTarget.value = null
  resetTemporaryPassword.value = ''
  resetConfirmPassword.value = ''
  deactivateTarget.value = null
  confirmDeactivation.value = false
  reactivateTarget.value = user
  reactivationReason.value = 'REHIRE'
  reactivationTemporaryPassword.value = ''
  reactivationConfirmPassword.value = ''
  reactivateError.value = ''
  reactivateSuccess.value = ''
}

function cancelReactivation() {
  if (reactivating.value) return

  reactivateTarget.value = null
  reactivationReason.value = 'REHIRE'

  reactivationTemporaryPassword.value = ''
  reactivationConfirmPassword.value = ''

  reactivateError.value = ''
}

async function handleReactivateUser() {
  const target = reactivateTarget.value

  if (!target || reactivating.value) return

  reactivateError.value = ''
  reactivateSuccess.value = ''

  if (reactivationTemporaryPassword.value.length < 12) {
    reactivateError.value = 'La contraseña temporal debe tener al menos 12 caracteres'
    return
  }

  if (reactivationTemporaryPassword.value.length > 1024) {
    reactivateError.value = 'La contraseña temporal es demasiado larga'
    return
  }

  if (reactivationTemporaryPassword.value !== reactivationConfirmPassword.value) {
    reactivateError.value = 'Las contraseñas no coinciden'
    return
  }

  reactivating.value = true

  try {
    await reactivateUser(target.id, {
      temporary_password: reactivationTemporaryPassword.value,
      reason: reactivationReason.value,
    })

    reactivateSuccess.value = `Usuario ${target.email} reactivado correctamente`
    reactivationTemporaryPassword.value = ''
    reactivationConfirmPassword.value = ''
    reactivateTarget.value = null

    await loadUsers()
  } catch (error) {
    reactivateError.value =
      error instanceof Error ? error.message : 'No fue posible reactivar al usuario'
  } finally {
    reactivating.value = false
  }
}

onMounted(loadUsers)
</script>

<template>
  <main class="admin-page">
    <div class="admin-panel">
      <header class="header">
        <div>
          <h1>Administración de usuarios</h1>
          <p>Consulta las cuentas registradas en STAD.</p>
        </div>

        <RouterLink to="/dashboard"> Volver al dashboard </RouterLink>
      </header>

      <section class="create-card">
        <h2>Registrar usuario</h2>

        <p>
          Crea una cuenta con contraseña temporal. El usuario deberá cambiarla al iniciar sesión.
        </p>

        <form class="create-form" @submit.prevent="handleCreateUser">
          <div class="field">
            <label for="new-name">Nombre completo</label>

            <input id="new-name" v-model="newUserName" type="text" maxlength="150" required />
          </div>

          <div class="field">
            <label for="new-email">Correo electrónico</label>

            <input
              id="new-email"
              v-model="newUserEmail"
              type="email"
              maxlength="255"
              autocomplete="off"
              required
            />
          </div>

          <div class="field">
            <label for="new-role">Rol</label>

            <select id="new-role" v-model="newUserRole">
              <option value="ENGINEER">ENGINEER</option>
              <option value="VIEWER">VIEWER</option>
            </select>
          </div>

          <div class="field">
            <label for="new-temp-password"> Contraseña temporal </label>

            <input
              id="new-temp-password"
              v-model="temporaryPassword"
              type="password"
              autocomplete="new-password"
              minlength="12"
              maxlength="1024"
              required
            />
          </div>

          <div class="form-actions">
            <p v-if="createError" class="error" role="alert">
              {{ createError }}
            </p>

            <p v-if="createSuccess" class="success" role="status">
              {{ createSuccess }}
            </p>

            <button type="submit" :disabled="creating">
              {{ creating ? 'Registrando...' : 'Registrar usuario' }}
            </button>
          </div>
        </form>
      </section>

      <section class="content">
        <div class="toolbar">
          <h2>Usuarios registrados</h2>

          <button type="button" :disabled="loading" @click="loadUsers">Actualizar</button>
        </div>

        <p v-if="errorMessage" class="error">
          {{ errorMessage }}
        </p>

        <p v-if="loading">Cargando usuarios...</p>

        <div v-else class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Nombre</th>
                <th>Correo</th>
                <th>Rol</th>
                <th>Estado</th>
                <th>Contraseña</th>
                <th>Acciones</th>
              </tr>
            </thead>

            <tbody>
              <tr v-for="user in users" :key="user.id">
                <td>{{ user.id }}</td>
                <td>{{ user.full_name }}</td>
                <td>{{ user.email }}</td>
                <td>{{ user.role }}</td>

                <td>
                  <span :class="['status', user.is_active ? 'active' : 'inactive']">
                    {{ user.is_active ? 'Activo' : 'Inactivo' }}
                  </span>
                </td>

                <td>
                  {{ user.must_change_password ? 'Cambio pendiente' : 'Actualizada' }}
                </td>

                <td>
                  <span v-if="user.role === 'ADMIN'"> Protegido </span>

                  <div v-else-if="user.is_active" class="user-actions">
                    <button
                      type="button"
                      class="reset-trigger"
                      :disabled="resetting || deactivating || reactivating"
                      @click="startReset(user)"
                    >
                      Restablecer
                    </button>

                    <button
                      type="button"
                      class="deactivate-trigger"
                      :disabled="resetting || deactivating || reactivating"
                      @click="startDeactivation(user)"
                    >
                      Desactivar
                    </button>
                  </div>

                  <button
                    v-else
                    type="button"
                    class="reactivate-trigger"
                    :disabled="resetting || deactivating || reactivating"
                    @click="startReactivation(user)"
                  >
                    Reactivar
                  </button>
                </td>
              </tr>

              <tr v-if="users.length === 0">
                <td colspan="7">No hay usuarios registrados.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <footer class="pagination">
          <span> Total: {{ total }} usuarios </span>

          <div class="page-controls">
            <button type="button" :disabled="loading || page === 1" @click="previousPage">
              Anterior
            </button>

            <span>Página {{ page }}</span>

            <button
              type="button"
              :disabled="loading || page * PAGE_SIZE >= total"
              @click="nextPage"
            >
              Siguiente
            </button>
          </div>
        </footer>
      </section>

      <section v-if="resetTarget" class="reset-card">
        <h2>Restablecer contraseña</h2>

        <p>
          Usuario:
          <strong>{{ resetTarget.full_name }}</strong>
        </p>

        <p>Correo: {{ resetTarget.email }}</p>

        <p class="reset-warning">
          Al restablecer la contraseña se invalidarán las sesiones anteriores del usuario. Deberá
          cambiar su contraseña temporal cuando vuelva a iniciar sesión.
        </p>

        <form class="reset-form" @submit.prevent="handleResetPassword">
          <label for="reset-password"> Nueva contraseña temporal </label>

          <input
            id="reset-password"
            v-model="resetTemporaryPassword"
            type="password"
            autocomplete="new-password"
            minlength="12"
            maxlength="1024"
            required
          />

          <label for="reset-confirm"> Confirmar contraseña temporal </label>

          <input
            id="reset-confirm"
            v-model="resetConfirmPassword"
            type="password"
            autocomplete="new-password"
            minlength="12"
            maxlength="1024"
            required
          />

          <p v-if="resetError" class="error" role="alert">
            {{ resetError }}
          </p>

          <div class="reset-actions">
            <button type="submit" :disabled="resetting">
              {{ resetting ? 'Restableciendo...' : 'Confirmar restablecimiento' }}
            </button>

            <button type="button" class="cancel-button" :disabled="resetting" @click="cancelReset">
              Cancelar
            </button>
          </div>
        </form>
      </section>

      <p v-if="resetSuccess" class="reset-success" role="status">
        {{ resetSuccess }}
      </p>

      <section v-if="deactivateTarget" class="deactivate-card">
        <h2>Desactivar usuario</h2>

        <p>
          Usuario:
          <strong>{{ deactivateTarget.full_name }}</strong>
        </p>

        <p>Correo: {{ deactivateTarget.email }}</p>

        <p class="deactivate-warning">
          Esta acción impedirá que el usuario vuelva a iniciar sesión e invalidará sus sesiones
          actuales. Su historial permanecerá guardado.
        </p>

        <form class="deactivate-form" @submit.prevent="handleDeactivateUser">
          <label for="deactivation-reason"> Motivo de desactivación </label>

          <select id="deactivation-reason" v-model="deactivationReason" required>
            <option value="EMPLOYMENT_ENDED">Ya no trabaja en la empresa</option>

            <option value="ACCESS_NO_LONGER_REQUIRED">Ya no necesita acceso</option>

            <option value="SECURITY">Motivos de seguridad</option>

            <option value="OTHER">Otro motivo</option>
          </select>

          <label class="confirmation">
            <input v-model="confirmDeactivation" type="checkbox" />

            <span> Confirmo que deseo desactivar esta cuenta de usuario. </span>
          </label>

          <p v-if="deactivateError" class="error" role="alert">
            {{ deactivateError }}
          </p>

          <div class="deactivate-actions">
            <button
              type="submit"
              class="confirm-deactivation"
              :disabled="deactivating || !confirmDeactivation"
            >
              {{ deactivating ? 'Desactivando...' : 'Confirmar desactivación' }}
            </button>

            <button
              type="button"
              class="cancel-button"
              :disabled="deactivating"
              @click="cancelDeactivation"
            >
              Cancelar
            </button>
          </div>
        </form>
      </section>

      <p v-if="deactivateSuccess" class="deactivate-success" role="status">
        {{ deactivateSuccess }}
      </p>

      <section v-if="reactivateTarget" class="reactivate-card">
        <h2>Reactivar usuario</h2>

        <p>
          Usuario:
          <strong>
            {{ reactivateTarget.full_name }}
          </strong>
        </p>

        <p>Correo: {{ reactivateTarget.email }}</p>

        <p class="reactivate-information">
          Se restaurará el acceso a esta cuenta. El usuario deberá iniciar sesión con una nueva
          contraseña temporal y cambiarla antes de acceder al dashboard.
        </p>

        <form class="reactivate-form" @submit.prevent="handleReactivateUser">
          <label for="reactivation-reason"> Motivo de reactivación </label>

          <select id="reactivation-reason" v-model="reactivationReason" required>
            <option value="REHIRE">El empleado regresó a la empresa</option>

            <option value="ACCESS_RESTORED">Acceso autorizado nuevamente</option>

            <option value="OTHER">Otro motivo</option>
          </select>

          <label for="reactivation-password"> Nueva contraseña temporal </label>

          <input
            id="reactivation-password"
            v-model="reactivationTemporaryPassword"
            type="password"
            autocomplete="new-password"
            minlength="12"
            maxlength="1024"
            required
          />

          <label for="reactivation-confirm"> Confirmar contraseña temporal </label>

          <input
            id="reactivation-confirm"
            v-model="reactivationConfirmPassword"
            type="password"
            autocomplete="new-password"
            minlength="12"
            maxlength="1024"
            required
          />

          <p v-if="reactivateError" class="error" role="alert">
            {{ reactivateError }}
          </p>

          <div class="reactivate-actions">
            <button type="submit" class="confirm-reactivation" :disabled="reactivating">
              {{ reactivating ? 'Reactivando...' : 'Confirmar reactivación' }}
            </button>

            <button
              type="button"
              class="cancel-button"
              :disabled="reactivating"
              @click="cancelReactivation"
            >
              Cancelar
            </button>
          </div>
        </form>
      </section>

      <p v-if="reactivateSuccess" class="reactivate-success" role="status">
        {{ reactivateSuccess }}
      </p>
    </div>
  </main>
</template>

<style scoped>
.admin-page {
  min-height: 100vh;
  padding: 36px 24px;
  background: #f1f5f9;
  color: #1e293b;
}

.admin-panel {
  max-width: 1150px;
  margin: 0 auto;
}

.header,
.toolbar,
.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.header {
  margin-bottom: 28px;
}

.header h1 {
  margin: 0 0 8px;
}

.header p {
  color: #64748b;
}

.header a {
  color: #116c88;
  font-weight: 600;
}

.content {
  background: white;
  border-radius: 14px;
  padding: 24px;
  box-shadow: 0 4px 20px #0000000d;
}

.toolbar {
  margin-bottom: 22px;
}

.toolbar h2 {
  margin: 0;
  font-size: 20px;
}

button {
  width: auto;
  padding: 10px 16px;
}

.table-wrapper {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

th,
td {
  padding: 14px 12px;
  border-bottom: 1px solid #e2e8f0;
  font-size: 14px;
}

th {
  background: #f8fafc;
  font-weight: 700;
}

.status {
  display: inline-block;
  padding: 5px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.active {
  color: #166534;
  background: #dcfce7;
}

.inactive {
  color: #991b1b;
  background: #fee2e2;
}

.pagination {
  margin-top: 24px;
}

.page-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.error {
  color: #b91c1c;
}

@media (max-width: 700px) {
  .header,
  .pagination {
    align-items: flex-start;
    flex-direction: column;
  }
}

.create-card {
  margin-bottom: 24px;
  padding: 24px;
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 4px 20px #0000000d;
}

.create-card h2 {
  margin: 0 0 8px;
  font-size: 20px;
}

.create-card > p {
  margin-bottom: 24px;
  color: #64748b;
}

.create-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.field label {
  font-size: 14px;
  font-weight: 600;
}

.field input,
.field select {
  width: 100%;
  min-height: 44px;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: white;
  color: #1e293b;
  font-size: 14px;
}

.form-actions {
  display: flex;
  grid-column: 1 / -1;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}

.form-actions button {
  width: auto;
  min-width: 180px;
}

.success {
  color: #166534;
  font-size: 14px;
}

@media (max-width: 700px) {
  .create-form {
    grid-template-columns: 1fr;
  }
}

.reset-trigger {
  width: auto;
  padding: 8px 12px;
  background: #475569;
  color: white;
  font-size: 12px;
  white-space: nowrap;
}

.reset-card {
  margin-top: 24px;
  padding: 24px;
  background: white;
  border-radius: 14px;
  box-shadow: 0 4px 20px #0000000d;
}

.reset-card h2 {
  margin: 0 0 16px;
  font-size: 20px;
}

.reset-card p {
  line-height: 1.5;
}

.reset-warning {
  padding: 12px;
  border-radius: 8px;
  background: #fff7ed;
  color: #9a3412;
}

.reset-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 440px;
  margin-top: 20px;
}

.reset-form input {
  width: 100%;
  padding: 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: white;
  color: #1e293b;
}

.reset-actions {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

.reset-actions button {
  width: auto;
}

.cancel-button {
  background: #e2e8f0;
  color: #334155;
}

.reset-success {
  margin-top: 16px;
  color: #166534;
  font-weight: 600;
}

@media (max-width: 500px) {
  .reset-actions {
    flex-direction: column;
  }
}

.user-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.deactivate-trigger {
  width: auto;
  padding: 8px 12px;
  background: #b91c1c;
  color: white;
  font-size: 12px;
  white-space: nowrap;
}

.deactivate-card {
  margin-top: 24px;
  padding: 24px;
  border-radius: 14px;
  background: white;
  box-shadow: 0 4px 20px #0000000d;
}

.deactivate-card h2 {
  margin: 0 0 16px;
  font-size: 20px;
}

.deactivate-warning {
  padding: 12px;
  border-radius: 8px;
  color: #991b1b;
  background: #fef2f2;
  line-height: 1.6;
}

.deactivate-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 480px;
  margin-top: 20px;
}

.deactivate-form select {
  padding: 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: white;
  color: #1e293b;
}

.confirmation {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.confirmation input {
  width: 18px;
  height: 18px;
  margin: 0;
  flex-shrink: 0;
}

.deactivate-actions {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

.deactivate-actions button {
  width: auto;
}

.confirm-deactivation {
  background: #b91c1c;
}

.deactivate-success {
  margin-top: 16px;
  color: #166534;
  font-weight: 600;
}

@media (max-width: 500px) {
  .deactivate-actions {
    flex-direction: column;
  }
}

.reactivate-trigger {
  width: auto;
  padding: 8px 12px;
  background: #047857;
  color: white;
  font-size: 12px;
  white-space: nowrap;
}

.reactivate-card {
  margin-top: 24px;
  padding: 24px;
  border-radius: 14px;
  background: white;
  box-shadow: 0 4px 20px #0000000d;
}

.reactivate-card h2 {
  margin: 0 0 16px;
  font-size: 20px;
}

.reactivate-information {
  padding: 12px;
  border-radius: 8px;
  background: #ecfdf5;
  color: #065f46;
  line-height: 1.6;
}

.reactivate-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 480px;
  margin-top: 20px;
}

.reactivate-form input,
.reactivate-form select {
  width: 100%;
  padding: 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: white;
  color: #1e293b;
}

.reactivate-actions {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

.reactivate-actions button {
  width: auto;
}

.confirm-reactivation {
  background: #047857;
}

.reactivate-success {
  margin-top: 16px;
  color: #166534;
  font-weight: 600;
}

@media (max-width: 500px) {
  .reactivate-actions {
    flex-direction: column;
  }
}
</style>
