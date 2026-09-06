import { createServer } from 'node:http'
import { readFile, stat } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { createContextLoader, HttpError, validateRequest } from './ai/context.mjs'
import { generate } from './ai/generate.mjs'

const root = fileURLToPath(new URL('../../../', import.meta.url))
const dataRoot = path.join(root, 'code/frontend/public/data')
const distRoot = path.join(root, 'code/frontend/dist')
const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.png': 'image/png' }

async function readBody(req) {
  if (!req.headers['content-type']?.startsWith('application/json')) throw new HttpError(415, 'Use application/json.')
  if (Number(req.headers['content-length']) > 65536) throw new HttpError(413, 'Request too large. Shorten the conversation or context.')
  const chunks = []; let bytes = 0
  for await (const chunk of req) {
    bytes += chunk.length
    if (bytes > 65536) throw new HttpError(413, 'Request too large. Shorten the conversation or context.')
    chunks.push(chunk)
  }
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')) }
  catch { throw new HttpError(400, 'Send valid JSON.') }
}

export function createApp({ apiKey = process.env.GEMINI_API_KEY, model = process.env.GEMINI_MODEL || 'gemini-3.6-flash',
  loadContext = createContextLoader(dataRoot), generateResponse = generate, frontendRoot = distRoot,
  allowedOrigins = (process.env.AI_ALLOWED_ORIGINS || 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173').split(','),
  now = Date.now, maxRequests = 20 } = {}) {
  let active = 0, requests = []
  return createServer(async (req, res) => {
    const send = (status, data) => { if (!res.destroyed) { res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' }); res.end(JSON.stringify(data)) } }
    try {
      const url = new URL(req.url, 'http://localhost')
      if (url.pathname.startsWith('/api/')) {
        const origin = req.headers.origin
        if (origin && origin !== `http://${req.headers.host}` && origin !== `https://${req.headers.host}` && !allowedOrigins.includes(origin)) throw new HttpError(403, 'This origin is not allowed to use the AI service.')
        if (url.pathname === '/api/ai/status' && req.method === 'GET') return send(200, { configured: Boolean(apiKey), model })
        if (!['/api/ai/context', '/api/ai/report', '/api/ai/chat'].includes(url.pathname)) throw new HttpError(404, 'Endpoint not found.')
        if (req.method !== 'POST') throw new HttpError(405, 'Use POST for this endpoint.')
        const body = validateRequest(await readBody(req))
        const mode = url.pathname.split('/').at(-1)
        if (mode === 'chat' && (!body.messages.length || body.messages.at(-1).role !== 'user')) throw new HttpError(400, 'Enter a question about this ship.')
        if (mode !== 'context' && !apiKey) throw new HttpError(503, 'AI is not configured. Add GEMINI_API_KEY to the server environment and restart the backend.')
        requests = requests.filter(time => time > now() - 60000)
        if (requests.length >= maxRequests || active >= 2) throw new HttpError(429, 'Too many AI requests. Wait a moment and try again.')
        requests.push(now()); active++
        const abort = new AbortController()
        const cancel = () => { if (!res.writableEnded) abort.abort() }
        res.on('close', cancel)
        try {
          const context = await loadContext(body)
          if (abort.signal.aborted) return
          const result = mode === 'context' ? context : await generateResponse({ mode, context, messages: body.messages, apiKey, model, signal: abort.signal })
          return send(200, result)
        } finally { active--; res.off('close', cancel) }
      }
      if (!['GET', 'HEAD'].includes(req.method)) throw new HttpError(405, 'Method not allowed.')
      const filename = path.resolve(frontendRoot, '.' + decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname))
      if (!filename.startsWith(path.resolve(frontendRoot) + path.sep)) throw new HttpError(404, 'File not found.')
      let buffer
      try { if (!(await stat(filename)).isFile()) throw new Error(); buffer = await readFile(filename) }
      catch { throw new HttpError(404, 'File not found. Build the frontend or use the Vite development server.') }
      res.writeHead(200, { 'Content-Type': mime[path.extname(filename)] || 'application/octet-stream', 'X-Content-Type-Options': 'nosniff' })
      res.end(req.method === 'HEAD' ? undefined : buffer)
    } catch (error) {
      send(error instanceof HttpError ? error.status : 500, { error: error instanceof HttpError ? error.message : 'The request could not be completed. Please retry.' })
    }
  })
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { process.loadEnvFile(path.join(root, '.env')) } catch (error) { if (error.code !== 'ENOENT') throw error }
  const port = Number(process.env.AI_PORT || 3001)
  createApp().listen(port, '127.0.0.1', () => console.log(`Wake AI portal: http://127.0.0.1:${port} — Gemini ${process.env.GEMINI_API_KEY ? 'configured' : 'needs GEMINI_API_KEY'}`))
}
