/** Typed error thrown by the API client */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly body?: unknown

  constructor(status: number, code: string, message: string, body?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.body = body
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isFormData = typeof FormData !== 'undefined' && init.body instanceof FormData
  const headers: Record<string, string> = {
    'X-Requested-With': 'cloudnotes',
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(init.headers as Record<string, string> ?? {}),
  }

  const res = await fetch(path, {
    ...init,
    credentials: 'include',
    headers,
  })

  if (!res.ok) {
    let code = 'unknown_error'
    let message = `HTTP ${res.status}`
    let bodyData: unknown = null
    try {
      bodyData = await res.json()
      const typedBody = bodyData as { error?: { code?: string; message?: string } }
      code = typedBody?.error?.code ?? code
      message = typedBody?.error?.message ?? message
    } catch {}
    throw new ApiError(res.status, code, message, bodyData)
  }

  // Some endpoints return empty body (204 etc.)
  const text = await res.text()
  if (!text) return undefined as T
  return JSON.parse(text) as T
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: 'GET' }),
  post: <T>(path: string, body?: unknown) => {
    const isFormData = typeof FormData !== 'undefined' && body instanceof FormData
    return request<T>(path, {
      method: 'POST',
      body: isFormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
    })
  },
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
