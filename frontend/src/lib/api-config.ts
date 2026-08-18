const defaultApiBaseUrl = ''

export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, '') ?? defaultApiBaseUrl
}

export function apiUrl(path: string, baseUrl = getApiBaseUrl()): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${baseUrl.replace(/\/+$/, '')}${normalizedPath}`
}
