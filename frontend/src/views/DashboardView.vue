<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import {
  fetchDashboardSummary,
  fetchDashboardNodes,
  fetchDashboardTrends,
  type DashboardSummary,
  type NodeStatistics,
  type DailyTrend,
} from '../services/dashboardApi'

const router = useRouter()
const authStore = useAuthStore()

const summary = ref<DashboardSummary | null>(null)
const loadingSummary = ref(false)
const summaryError = ref('')
const logoutError = ref('')

const formatter = new Intl.NumberFormat('es-MX')

const nodes = ref<NodeStatistics[]>([])

const nodesPage = ref(1)
const nodesPageSize = 10
const totalNodes = ref(0)

const loadingNodes = ref(false)
const nodesError = ref('')

function formatCount(value: number): string {
  return formatter.format(value)
}

function formatDuration(value: number | null): string {
  if (value === null) {
    return 'Sin datos'
  }

  return `${value.toFixed(2)} s`
}

async function loadSummary() {
  if (loadingSummary.value) return

  loadingSummary.value = true
  summaryError.value = ''

  try {
    summary.value = await fetchDashboardSummary()
  } catch (error) {
    summary.value = null
    summaryError.value =
      error instanceof Error ? error.message : 'No fue posible cargar las estadísticas'
  } finally {
    loadingSummary.value = false
  }
}

async function loadNodes(targetPage = nodesPage.value) {
  if (loadingNodes.value) return

  loadingNodes.value = true
  nodesError.value = ''

  try {
    const response = await fetchDashboardNodes(targetPage, nodesPageSize)

    nodes.value = response.items
    nodesPage.value = response.page
    totalNodes.value = response.total_nodes
  } catch (error) {
    nodesError.value =
      error instanceof Error ? error.message : 'No fue posible cargar los servidores'
  } finally {
    loadingNodes.value = false
  }
}

async function previousNodesPage() {
  if (nodesPage.value <= 1) return

  await loadNodes(nodesPage.value - 1)
}

async function nextNodesPage() {
  if (nodesPage.value * nodesPageSize >= totalNodes.value) {
    return
  }

  await loadNodes(nodesPage.value + 1)
}

async function handleLogout() {
  logoutError.value = ''

  try {
    await authStore.logout()
    await router.replace('/login')
  } catch (error) {
    logoutError.value = error instanceof Error ? error.message : 'No fue posible cerrar sesión'
  }
}

const trends = ref<DailyTrend[]>([])
const loadingTrends = ref(false)
const trendsError = ref('')
const showIncomplete = ref(false)

type TrendKey = 'pass_count' | 'fail_count' | 'error_count' | 'incomplete_count'

const trendSeries: {
  key: TrendKey
  label: string
  color: string
}[] = [
  { key: 'pass_count', label: 'PASS', color: '#15803d' },
  { key: 'fail_count', label: 'FAIL', color: '#dc2626' },
  { key: 'error_count', label: 'ERROR', color: '#ea580c' },
  {
    key: 'incomplete_count',
    label: 'INCOMPLETE',
    color: '#7c3aed',
  },
]

async function loadTrends() {
  if (loadingTrends.value) return

  loadingTrends.value = true
  trendsError.value = ''

  try {
    const response = await fetchDashboardTrends()
    trends.value = response.items
  } catch (error) {
    trendsError.value =
      error instanceof Error ? error.message : 'No fue posible cargar las tendencias'
  } finally {
    loadingTrends.value = false
  }
}

const hasTrendData = computed(() => trends.value.some((day) => day.total_executions > 0))

// Completar con ceros los días sin ejecuciones.
// Todos los días se interpretan en UTC.
const trendDays = computed(() => {
  const byDate = new Map(trends.value.map((item) => [item.day, item]))

  const start = new Date()
  start.setUTCHours(0, 0, 0, 0)
  start.setUTCDate(start.getUTCDate() - 29)

  return Array.from({ length: 30 }, (_, index) => {
    const date = new Date(start)
    date.setUTCDate(start.getUTCDate() + index)

    const key = date.toISOString().slice(0, 10)

    return {
      day: key,
      pass_count: byDate.get(key)?.pass_count ?? 0,
      fail_count: byDate.get(key)?.fail_count ?? 0,
      error_count: byDate.get(key)?.error_count ?? 0,
      incomplete_count: byDate.get(key)?.incomplete_count ?? 0,
    }
  })
})

const trendChart = computed(() => {
  const width = 960
  const height = 320

  const left = 55
  const right = 20
  const top = 20
  const bottom = 55

  const plotWidth = width - left - right
  const plotHeight = height - top - bottom

  const visibleSeries = trendSeries.filter(
    (series) => series.key !== 'incomplete_count' || showIncomplete.value,
  )

  const maximum = Math.max(
    1,
    ...trendDays.value.flatMap((day) => visibleSeries.map((series) => day[series.key])),
  )

  const maxY = Math.max(4, Math.ceil(maximum / 4) * 4)

  const x = (index: number) => left + (index / 29) * plotWidth

  const y = (value: number) => top + plotHeight * (1 - value / maxY)

  const lines = visibleSeries.map((series) => ({
    ...series,
    points: trendDays.value
      .map((day, index) => `${x(index).toFixed(1)},${y(day[series.key]).toFixed(1)}`)
      .join(' '),
  }))

  const yTicks = Array.from({ length: 5 }, (_, index) => {
    const value = (maxY / 4) * index

    return {
      value,
      y: y(value),
    }
  })

  const xTicks = [0, 7, 14, 21, 29].map((index) => {
    const day = trendDays.value[index]!

    return {
      x: x(index),
      label: new Intl.DateTimeFormat('es-MX', {
        day: '2-digit',
        month: 'short',
        timeZone: 'UTC',
      }).format(new Date(`${day.day}T00:00:00Z`)),
    }
  })

  return {
    lines,
    yTicks,
    xTicks,
    left,
    right,
    top,
    bottom,
    width,
    height,
  }
})

onMounted(() => {
  void loadSummary()
  void loadNodes()
  void loadTrends()
})
</script>

<template>
  <main class="dashboard-page">
    <div class="dashboard-container">
      <header class="dashboard-header">
        <div>
          <div class="brand">
            <div class="brand-icon">S</div>

            <div>
              <strong>STAD</strong>
              <small>Server Test Automation Dashboard</small>
            </div>
          </div>

          <h1>Dashboard principal</h1>

          <p class="subtitle">Estadísticas y monitoreo de pruebas de servidores.</p>
        </div>

        <div class="header-actions">
          <RouterLink v-if="authStore.userRole === 'ADMIN'" to="/admin/users" class="admin-link">
            Administrar usuarios
          </RouterLink>

          <button
            type="button"
            class="logout-button"
            :disabled="authStore.loading"
            @click="handleLogout"
          >
            {{ authStore.loading ? 'Cerrando sesión...' : 'Cerrar sesión' }}
          </button>
        </div>
      </header>

      <p v-if="logoutError" class="error-message" role="alert">
        {{ logoutError }}
      </p>

      <section class="welcome-panel">
        <div>
          <h2>
            Bienvenido,
            {{ authStore.user?.full_name ?? 'Usuario' }}
          </h2>

          <p>
            {{ authStore.user?.email }}
          </p>
        </div>

        <span class="role-badge">
          {{ authStore.userRole }}
        </span>
      </section>

      <section class="statistics-section">
        <div class="section-heading">
          <div>
            <h2>Resumen de ejecuciones</h2>
            <p>Información obtenida desde FastAPI.</p>
          </div>

          <button
            type="button"
            class="refresh-button"
            :disabled="loadingSummary"
            @click="loadSummary"
          >
            {{ loadingSummary ? 'Actualizando...' : 'Actualizar estadísticas' }}
          </button>
        </div>

        <p v-if="summaryError" class="error-message" role="alert">
          {{ summaryError }}
        </p>

        <p v-if="loadingSummary && !summary" class="loading-message" role="status">
          Cargando estadísticas...
        </p>

        <div v-if="summary" class="statistics-grid">
          <article class="stat-card">
            <p>Ejecuciones totales</p>
            <strong>
              {{ formatCount(summary.total_executions) }}
            </strong>
            <span>Pruebas registradas</span>
          </article>

          <article class="stat-card">
            <p>Exitosas (PASS)</p>
            <strong class="success-value">
              {{ formatCount(summary.pass_count) }}
            </strong>
            <span>Pruebas aprobadas</span>
          </article>

          <article class="stat-card">
            <p>Fallidas (FAIL)</p>
            <strong class="failure-value">
              {{ formatCount(summary.fail_count) }}
            </strong>
            <span>Pruebas fallidas</span>
          </article>

          <article class="stat-card">
            <p>Tasa de éxito</p>
            <strong class="rate-value"> {{ summary.success_rate_percent.toFixed(2) }}% </strong>
            <span>Porcentaje de pruebas exitosas</span>
          </article>

          <article class="stat-card">
            <p>Errores (ERROR)</p>
            <strong>
              {{ formatCount(summary.error_count) }}
            </strong>
            <span>Pruebas con errores</span>
          </article>

          <article class="stat-card">
            <p>Incompletas (INCOMPLETE)</p>
            <strong>
              {{ formatCount(summary.incomplete_count) }}
            </strong>
            <span>Pruebas sin completar</span>
          </article>

          <article class="stat-card">
            <p>Duración promedio</p>
            <strong>
              {{ formatDuration(summary.average_duration_seconds) }}
            </strong>
            <span>Tiempo promedio por ejecución</span>
          </article>
        </div>

        <p v-if="summary && summary.total_executions === 0" class="empty-message">
          Todavía no hay ejecuciones registradas. Las estadísticas se actualizarán cuando se
          incorporen resultados de pruebas.
        </p>
      </section>

      <section class="nodes-section">
        <div class="section-heading">
          <div>
            <h2>Estadísticas por servidor</h2>
            <p>Resultados agrupados por nodo de pruebas.</p>
          </div>

          <button
            type="button"
            class="refresh-button"
            :disabled="loadingNodes"
            @click="loadNodes()"
          >
            {{ loadingNodes ? 'Actualizando...' : 'Actualizar nodos' }}
          </button>
        </div>

        <p v-if="nodesError" class="error-message" role="alert">
          {{ nodesError }}
        </p>

        <p v-if="loadingNodes" role="status">Cargando estadísticas de servidores...</p>

        <div class="nodes-table-wrapper">
          <table class="nodes-table">
            <thead>
              <tr>
                <th>Servidor / Nodo</th>
                <th>Total</th>
                <th>PASS</th>
                <th>FAIL</th>
                <th>ERROR</th>
                <th>INCOMPLETE</th>
                <th>Tasa de éxito</th>
                <th>Duración promedio</th>
              </tr>
            </thead>

            <tbody>
              <tr v-for="node in nodes" :key="node.node_name">
                <td>
                  <strong>{{ node.node_name }}</strong>
                </td>

                <td>
                  {{ formatCount(node.total_executions) }}
                </td>

                <td class="success-value">
                  {{ formatCount(node.pass_count) }}
                </td>

                <td class="failure-value">
                  {{ formatCount(node.fail_count) }}
                </td>

                <td>
                  {{ formatCount(node.error_count) }}
                </td>

                <td>
                  {{ formatCount(node.incomplete_count) }}
                </td>

                <td>{{ node.success_rate_percent.toFixed(2) }}%</td>

                <td>
                  {{ formatDuration(node.average_duration_seconds) }}
                </td>
              </tr>

              <tr v-if="nodes.length === 0 && !loadingNodes">
                <td colspan="8" class="empty-nodes">
                  No hay ejecuciones registradas por servidor.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <footer class="nodes-pagination">
          <span> Total de nodos: {{ totalNodes }} </span>

          <div class="nodes-page-actions">
            <button
              type="button"
              :disabled="loadingNodes || nodesPage <= 1"
              @click="previousNodesPage"
            >
              Anterior
            </button>

            <span>Página {{ nodesPage }}</span>

            <button
              type="button"
              :disabled="loadingNodes || nodesPage * nodesPageSize >= totalNodes"
              @click="nextNodesPage"
            >
              Siguiente
            </button>
          </div>
        </footer>
      </section>

      <section class="trends-section">
        <div class="section-heading">
          <div>
            <h2>Tendencias de ejecuciones</h2>
            <p>Resultados diarios de los últimos 30 días UTC.</p>
          </div>

          <button
            type="button"
            class="refresh-button"
            :disabled="loadingTrends"
            @click="loadTrends"
          >
            {{ loadingTrends ? 'Actualizando...' : 'Actualizar tendencias' }}
          </button>
        </div>

        <p v-if="trendsError" class="error-message" role="alert">
          {{ trendsError }}
        </p>

        <p v-if="loadingTrends" role="status">Cargando tendencias...</p>

        <template v-if="hasTrendData">
          <div class="trends-controls">
            <label class="trend-checkbox">
              <input v-model="showIncomplete" type="checkbox" />
              Mostrar INCOMPLETE
            </label>
          </div>

          <div class="trends-chart-wrapper">
            <svg
              class="trends-chart"
              viewBox="0 0 960 320"
              role="img"
              aria-label="Gráfica de resultados diarios de pruebas de servidores durante los últimos 30 días"
            >
              <g v-for="tick in trendChart.yTicks" :key="tick.value">
                <line
                  :x1="trendChart.left"
                  :y1="tick.y"
                  :x2="trendChart.width - trendChart.right"
                  :y2="tick.y"
                  stroke="#e2e8f0"
                  stroke-width="1"
                />

                <text
                  :x="trendChart.left - 12"
                  :y="tick.y + 4"
                  text-anchor="end"
                  fill="#64748b"
                  font-size="12"
                >
                  {{ tick.value }}
                </text>
              </g>

              <g v-for="tick in trendChart.xTicks" :key="tick.x">
                <text
                  :x="tick.x"
                  :y="trendChart.height - 20"
                  text-anchor="middle"
                  fill="#64748b"
                  font-size="12"
                >
                  {{ tick.label }}
                </text>
              </g>

              <polyline
                v-for="line in trendChart.lines"
                :key="line.key"
                :points="line.points"
                :stroke="line.color"
                fill="none"
                stroke-width="3"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </div>

          <div class="trends-legend">
            <div v-for="line in trendChart.lines" :key="line.key" class="legend-item">
              <span class="legend-color" :style="{ backgroundColor: line.color }"></span>

              {{ line.label }}
            </div>
          </div>
        </template>

        <p v-else-if="!loadingTrends && !trendsError" class="empty-message">
          No existen ejecuciones registradas durante los últimos 30 días.
        </p>
      </section>
    </div>
  </main>
</template>

<style scoped>
.dashboard-page {
  min-height: 100vh;
  padding: 32px 24px;
  background: #f1f5f9;
  color: #1e293b;
}

.dashboard-container {
  max-width: 1250px;
  margin: 0 auto;
}

.dashboard-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 28px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 24px;
}

.brand-icon {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: #116c88;
  color: white;
  font-size: 25px;
  font-weight: 800;
}

.brand strong,
.brand small {
  display: block;
}

.brand strong {
  font-size: 21px;
}

.brand small {
  color: #64748b;
  font-size: 12px;
}

.dashboard-header h1 {
  margin: 0 0 8px;
}

.subtitle {
  margin: 0;
  color: #64748b;
}

.header-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.admin-link {
  padding: 12px 16px;
  border: 1px solid #116c88;
  border-radius: 8px;
  color: #116c88;
  text-decoration: none;
  font-weight: 600;
}

.logout-button,
.refresh-button {
  width: auto;
  padding: 12px 18px;
}

.logout-button {
  background: #334155;
}

.welcome-panel,
.statistics-section {
  padding: 24px;
  border-radius: 14px;
  background: white;
  box-shadow: 0 4px 20px #0000000a;
}

.welcome-panel {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 24px;
}

.welcome-panel h2 {
  margin: 0 0 8px;
  font-size: 20px;
}

.welcome-panel p {
  margin: 0;
  color: #64748b;
  overflow-wrap: anywhere;
}

.role-badge {
  padding: 8px 12px;
  border-radius: 20px;
  background: #e0f2fe;
  color: #075985;
  font-size: 12px;
  font-weight: 700;
}

.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.section-heading h2 {
  margin: 0 0 6px;
}

.section-heading p {
  margin: 0;
  color: #64748b;
}

.statistics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card {
  min-width: 0;
  padding: 20px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;
}

.stat-card p {
  margin: 0 0 14px;
  color: #64748b;
  font-size: 14px;
  font-weight: 600;
}

.stat-card strong {
  display: block;
  margin-bottom: 10px;
  font-size: 28px;
  overflow-wrap: anywhere;
}

.stat-card span {
  color: #64748b;
  font-size: 12px;
}

.success-value {
  color: #047857;
}

.failure-value {
  color: #b91c1c;
}

.rate-value {
  color: #116c88;
}

.error-message {
  padding: 12px;
  border-radius: 8px;
  background: #fef2f2;
  color: #b91c1c;
  margin-bottom: 20px;
}

.loading-message,
.empty-message {
  padding: 20px;
  color: #64748b;
  text-align: center;
}

@media (max-width: 1000px) {
  .statistics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 650px) {
  .dashboard-page {
    padding: 18px 12px;
  }

  .dashboard-header,
  .section-heading,
  .welcome-panel {
    flex-direction: column;
    align-items: stretch;
  }

  .statistics-grid {
    grid-template-columns: 1fr;
  }

  .header-actions {
    align-items: stretch;
  }
}

.nodes-section {
  margin-top: 24px;
  padding: 24px;
  border-radius: 14px;
  background: white;
  box-shadow: 0 4px 20px #0000000a;
}

.nodes-table-wrapper {
  width: 100%;
  overflow-x: auto;
}

.nodes-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.nodes-table th,
.nodes-table td {
  padding: 14px 12px;
  text-align: left;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}

.nodes-table th {
  background: #f8fafc;
  color: #475569;
  font-weight: 700;
}

.nodes-table tbody tr:hover {
  background: #f8fafc;
}

.empty-nodes {
  padding: 30px !important;
  text-align: center !important;
  color: #64748b;
}

.nodes-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 20px;
  color: #475569;
}

.nodes-page-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nodes-page-actions button {
  width: auto;
  padding: 9px 14px;
}

@media (max-width: 650px) {
  .nodes-section {
    padding: 16px;
  }

  .nodes-page-actions {
    flex-wrap: wrap;
  }
}

.trends-section {
  margin-top: 24px;
  padding: 24px;
  border-radius: 14px;
  background: white;
  box-shadow: 0 4px 20px #0000000a;
}

.trends-controls {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.trend-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  color: #475569;
  cursor: pointer;
}

.trend-checkbox input {
  width: 16px;
  height: 16px;
  margin: 0;
}

.trends-chart-wrapper {
  width: 100%;
  overflow-x: auto;
}

.trends-chart {
  display: block;
  width: 100%;
  min-width: 600px;
  height: auto;
}

.trends-legend {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 20px;
  margin-top: 18px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}

.legend-color {
  width: 20px;
  height: 4px;
  border-radius: 4px;
}

@media (max-width: 650px) {
  .trends-section {
    padding: 16px;
  }

  .trends-controls {
    justify-content: flex-start;
  }
}
</style>
