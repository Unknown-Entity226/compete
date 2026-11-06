/**
 * Base HTTP client for Compete API with timeout and JSON handling.
 */
const BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

function getErrorMessage(errorBody, status) {
  const detail = errorBody?.detail
  if (typeof errorBody?.message === 'string') return errorBody.message
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || (typeof item === 'string' ? item : ''))
      .filter(Boolean)
      .join('; ')
  }
  return `Request failed with status ${status}`
}

async function request(path, options = {}) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 12000)

  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })
    clearTimeout(timeoutId)

    if (!res.ok) {
      const errorBody = await res.json().catch(() => ({}))
      const error = new Error(getErrorMessage(errorBody, res.status))
      error.status = res.status
      error.data = errorBody
      throw error
    }

    if (res.status === 204) return null
    return await res.json()
  } catch (err) {
    clearTimeout(timeoutId)
    if (err.name === 'AbortError') {
      const timeoutError = new Error('Request timed out. Please check your network or backend.')
      timeoutError.status = 408
      throw timeoutError
    }
    if (err instanceof TypeError) {
      const networkError = new Error('Unable to reach the profile service. Please check your connection and try again.')
      networkError.cause = err
      throw networkError
    }
    throw err
  }
}

export const api = {
  get: (path) => request(path, { method: 'GET' }),
  post: (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) }),
}
