export async function aiRequest<T>(endpoint: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${import.meta.env.BASE_URL}api/ai/${endpoint}`, {
      method: body === undefined ? 'GET' : 'POST', headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(75000)]) : AbortSignal.timeout(75000),
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new Error('The AI service could not be reached. Check the connection and try again.')
  }
  let data
  try { data = await response.json() }
  catch { throw new Error('The AI service is unavailable. Start the portal backend and try again.') }
  if (!response.ok) throw new Error(data.error || 'The AI request failed. Please retry.')
  return data as T
}
