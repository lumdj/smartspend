import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const client = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30s — accounts for Render cold starts
})

// ── Request interceptor ───────────────────────────────────────────────────────
// Attach user_id to every request automatically so components
// don't have to pass it manually every time
client.interceptors.request.use((config) => {
  const userId = localStorage.getItem('smartspend_user_id')
  if (!userId) return config
  
  // Only add user_id as query param if the URL doesn't already contain it as a path segment
  const urlContainsUserId = config.url?.includes(userId)
  if (!urlContainsUserId) {
    config.params = { ...config.params, user_id: config.params?.user_id || userId }
  }
  
  // Remove explicit user_id: undefined params (cleanup)
  if (config.params?.user_id === undefined) {
    delete config.params.user_id
  }
  
  return config
})

// ── Response interceptor ──────────────────────────────────────────────────────
// Normalize errors so components get a consistent error shape
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail ||
      error.message ||
      'Something went wrong'
    return Promise.reject(new Error(message))
  }
)

// ── Profile ───────────────────────────────────────────────────────────────────

export const profileApi = {
  create: (data) => client.post('/profile/', data),
  get: (userId) => client.get(`/profile/${userId}`, { params: { user_id: undefined } }),
  update: (userId, data) => client.patch(`/profile/${userId}`, data),
  exists: (userId) => client.get(`/profile/${userId}/exists`, { params: { user_id: undefined } }),
  setBillingCycle: (userId, day) =>
    client.patch(`/profile/${userId}/billing-cycle`, { billing_cycle_day: day }),
  delete: (userId) => client.delete(`/profile/${userId}`, { params: { user_id: undefined } }),
}

// ── Transactions ──────────────────────────────────────────────────────────────

export const transactionsApi = {
  list: (params) => client.get('/transactions/', { params }),
  get: (id) => client.get(`/transactions/${id}`),
  ingest: (personaKey = 'alex') =>
    client.post('/transactions/ingest', null, { params: { persona_key: personaKey } }),
  setOverride: (merchantName, preferredCategory) =>
    client.post('/transactions/override', { merchant_name: merchantName, preferred_category: preferredCategory }),
  deleteOverride: (merchantName) =>
    client.delete('/transactions/override', { params: { merchant_name: merchantName } }),
}

// ── Insights ──────────────────────────────────────────────────────────────────

export const insightsApi = {
  get: (useAi = true) => client.get(`/insights/${getUserId()}`, { params: { use_ai: useAi, user_id: undefined } }),
}

// ── Reports ───────────────────────────────────────────────────────────────────

export const reportsApi = {
  monthly: (month, useAi = true) =>
    client.get(`/reports/${getUserId()}/monthly`, {
      params: { month, use_ai: useAi, user_id: undefined },
    }),
}

// ── Goals ─────────────────────────────────────────────────────────────────────

export const goalsApi = {
  list: () => client.get('/goals/'),
  create: (data) => client.post('/goals/', data),
  update: (goalId, data) => client.patch(`/goals/${goalId}`, data),
  addProgress: (goalId, data) => client.post(`/goals/${goalId}/progress`, data),
  delete: (goalId) => client.delete(`/goals/${goalId}`),
}

// ── Nudges ────────────────────────────────────────────────────────────────────

export const nudgesApi = {
  list: (unseenOnly = true) =>
    client.get('/nudges/', { params: { unseen_only: unseenOnly } }),
  dismiss: (nudgeId) => client.patch(`/nudges/${nudgeId}/dismiss`),
  feedback: (nudgeId, feedback) =>
    client.patch(`/nudges/${nudgeId}/feedback`, { feedback }),
}

// ── Achievements ──────────────────────────────────────────────────────────────

export const achievementsApi = {
  list: () => client.get('/achievements/'),
}

// ── Demo ──────────────────────────────────────────────────────────────────────

export const demoApi = {
  personas: () => client.get('/demo/personas', { params: { user_id: undefined } }),
  loadPersona: (personaKey) =>
    client.post('/demo/load-persona', {
      persona_key: personaKey,
      user_id: getUserId(),
    }, { params: { user_id: undefined } }),
  reset: (personaKey = 'alex') =>
    client.post(`/demo/reset/${getUserId()}`, null, {
      params: { persona_key: personaKey, user_id: undefined },
    }),
  spikeCategory: (category, multiplier = 2.5) =>
    client.post('/demo/spike-category', null, {
      params: { category, multiplier },
    }),
}

// ── Helpers ───────────────────────────────────────────────────────────────────

export const getUserId = () => localStorage.getItem('smartspend_user_id')

export const setUserId = (id) => localStorage.setItem('smartspend_user_id', id)

export const clearUserId = () => localStorage.removeItem('smartspend_user_id')

export default client
