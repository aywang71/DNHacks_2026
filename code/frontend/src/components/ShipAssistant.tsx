import { useEffect, useId, useRef, useState } from 'react'
import { aiRequest } from '../ai/client'
import type { AiResult, ChatMessage, ShipContext, ShipTarget } from '../ai/types'
import './ShipAssistant.css'

const starterQuestions = ['What do we know about this ship?', 'What does the priority score mean?', 'What should I check next?']
const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'Please try again.'
const answerText = (result: AiResult) => [result.summary, ...result.sections.map(section => `${section.heading}\n${section.text}`)].join('\n\n')

export function ShipAssistant({ target, notes: externalNotes, disabled = false }: { target: ShipTarget; notes?: string; disabled?: boolean }) {
  const [status, setStatus] = useState<{ configured: boolean; model: string } | null>(null)
  const [statusError, setStatusError] = useState('')
  const [retry, setRetry] = useState(0)
  const [localNotes, setLocalNotes] = useState('')
  const notes = externalNotes ?? localNotes
  const [mode, setMode] = useState<'report' | 'chat'>('report')
  const [busy, setBusy] = useState<'report' | 'chat' | 'context' | null>(null)
  const [error, setError] = useState('')
  const [report, setReport] = useState<AiResult | null>(null)
  const [turns, setTurns] = useState<{ question: string; answer: AiResult }[]>([])
  const [question, setQuestion] = useState('')
  const [context, setContext] = useState<ShipContext | null>(null)
  const [showContext, setShowContext] = useState(false)
  const active = useRef<AbortController | null>(null)
  const reportElement = useRef<HTMLElement>(null)
  const answerElement = useRef<HTMLDivElement>(null)
  const prefix = useId()
  useEffect(() => {
    const abort = new AbortController()
    setStatusError('')
    aiRequest<{ configured: boolean; model: string }>('status', undefined, abort.signal).then(value => { if (!abort.signal.aborted) setStatus(value) }).catch(error => { if (!abort.signal.aborted) setStatusError(errorMessage(error)) })
    return () => abort.abort()
  }, [retry])
  useEffect(() => () => active.current?.abort(), [])
  useEffect(() => { if (turns.length) answerElement.current?.focus() }, [turns.length])

  async function run(kind: 'report' | 'chat' | 'context', prompt = question) {
    if (busy || disabled || (kind === 'chat' && !prompt.trim())) return
    const abort = new AbortController(); active.current = abort
    setBusy(kind); setError('')
    const messages: ChatMessage[] = kind === 'chat' ? [...turns.slice(-5).flatMap(turn => [
      { role: 'user' as const, content: turn.question }, { role: 'assistant' as const, content: answerText(turn.answer) },
    ]), { role: 'user', content: prompt.trim() }] : []
    try {
      const body = { ...target, notes, messages }
      if (kind === 'context') {
        const result = await aiRequest<ShipContext>('context', body, abort.signal)
        if (!abort.signal.aborted) { setContext(result); setShowContext(true) }
      } else {
        const result = await aiRequest<AiResult>(kind, body, abort.signal)
        if (abort.signal.aborted) return
        setContext(result.context)
        if (kind === 'report') setReport(result)
        else { setTurns(previous => [...previous, { question: prompt.trim(), answer: result }]); setQuestion('') }
      }
    } catch (error) { if (!abort.signal.aborted) setError(errorMessage(error)) }
    finally { if (!abort.signal.aborted) { setBusy(null); active.current = null } }
  }
  function cancel() { active.current?.abort(); active.current = null; setBusy(null); setError('Request cancelled. You can try again.') }
  function documentHtml() {
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Wake AI vessel evidence brief</title><style>body{font:16px/1.65 system-ui;color:#1c1917;max-width:780px;margin:40px auto;padding:24px}h1{font-size:28px}h2{font-size:19px;margin-top:28px}h3{font-size:16px}p{white-space:pre-wrap;overflow-wrap:anywhere}small{color:#57534e}section{break-inside:avoid}button{display:none}@media print{body{margin:0}}</style></head><body>' + (reportElement.current?.innerHTML ?? '') + '</body></html>'
  }
  function download() {
    if (!report) return
    const url = URL.createObjectURL(new Blob([documentHtml()], { type: 'text/html;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url; link.download = `wake-ai-report-${target.vesselId.replace(/[^a-zA-Z0-9_-]/g, '_')}.html`
    link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  function print() {
    // Print an isolated document so the map, chat, and other reports stay out of the PDF.
    const frame = document.createElement('iframe')
    frame.title = 'Printable AI evidence brief'; frame.className = 'ai-print-frame'
    frame.onload = () => { frame.contentWindow?.focus(); frame.contentWindow?.print() }
    frame.srcdoc = documentHtml(); document.body.appendChild(frame)
    window.setTimeout(() => frame.remove(), 60000)
  }
  const ready = status?.configured && !disabled && !busy
  const lastAnswer = turns.at(-1)?.answer
  return <section className="ship-assistant" aria-label="Ship AI assistant">
    <header className="ai-heading"><div><h3>Ship intelligence</h3><p>Turn the records into a readable brief, or ask a question.</p></div><span className="ai-badge">AI</span></header>
    {statusError ? <p className="ai-notice" role="status">{statusError} <button onClick={() => setRetry(value => value + 1)}>Reconnect AI</button></p>
      : !status ? <p className="ai-meta" role="status">Connecting to AI…</p>
      : !status.configured ? <div className="ai-notice" role="status"><strong>AI setup needed</strong><p>Add GEMINI_API_KEY to the server’s .env file and restart the backend to enable reports and chat.</p><button onClick={() => setRetry(value => value + 1)}>Check connection</button></div>
      : <p className="ai-meta">Uses this ship’s imported records and your context. Responses may contain mistakes; review before sharing.</p>}
    {externalNotes === undefined ? <label className="ai-context-label" htmlFor={`${prefix}-notes`}>Additional context<textarea id={`${prefix}-notes`} rows={3} maxLength={8000} value={localNotes} onChange={event => setLocalNotes(event.target.value)} placeholder="Add observations, background, or what you want to investigate." /><small>{notes.length.toLocaleString()} / 8,000 characters</small></label>
      : <p className="ai-meta">{notes.trim() ? 'Your analyst notes above will be included as unverified context.' : 'Add analyst notes above to give the AI more context.'}</p>}
    <button className="ai-context-button" disabled={Boolean(busy) || disabled} onClick={() => showContext ? setShowContext(false) : void run('context')}>{showContext ? 'Hide source context' : 'Preview source context'}</button>
    {showContext && context && <div className="ai-context-preview"><strong>{context.vessel.name || context.vessel.mmsi || context.vessel.id}</strong><p>{context.window.start.slice(0, 10)} to {context.window.end.slice(0, 10)} UTC (end exclusive)</p><ul><li>{context.presence.observationCount.toLocaleString()} observations; {context.presence.sampleCount} sampled positions sent to AI</li><li>{context.presence.importedHours} imported hours; {context.presence.unimportedHours} hours without imported coverage</li><li>{context.presence.vesselObservedHours} hours with a ship observation; {context.presence.coveredEmptyHours} imported hours with no vessels</li></ul>{context.sources.map(source => <p key={source.id}><strong>{source.label}.</strong> {source.detail}</p>)}</div>}
    <div className="ai-modes" role="group" aria-label="AI task"><button aria-pressed={mode === 'report'} onClick={() => { setMode('report'); setError('') }}>Write a report</button><button aria-pressed={mode === 'chat'} onClick={() => { setMode('chat'); setError('') }}>Ask about this ship</button></div>
    {mode === 'report' ? <div className="ai-report-workspace"><p className="ai-meta">A plain-English assessment with evidence, limitations, and suggested next checks.</p><button className="primary-button" disabled={!ready} onClick={() => void run('report')}>{busy === 'report' ? 'Writing report…' : report ? 'Regenerate AI report' : 'Write AI report'}</button>
      {report && <div className="ai-report-preview"><div className="ai-report-actions"><button onClick={download}>Download report</button><button onClick={print}>Print / Save PDF</button></div>{notes !== report.context.analystNotes && <p className="ai-notice">Context has changed. Regenerate to include your latest notes; this report preserves the earlier context.</p>}
        <article className="ai-paper" ref={reportElement} aria-label="AI evidence brief"><h1>{report.title}</h1><p><strong>{report.context.vessel.name || report.context.vessel.mmsi || report.context.vessel.id}</strong><br />{report.context.window.start.slice(0, 10)} to {report.context.window.end.slice(0, 10)} UTC (end exclusive)</p><p><small>AI draft · {new Date(report.generatedAt).toLocaleString('en-GB', { timeZone: 'UTC' })} UTC · {report.model}</small></p><Answer result={report} headingLevel="h2" /><h2>Source record</h2>{report.context.sources.map(source => <p key={source.id}><strong>{source.label}.</strong> {source.detail}</p>)}{report.context.analystNotes && <><h2>Analyst context used</h2><p>{report.context.analystNotes}</p></>}<p><small>AI-generated draft for analyst review. AIS absence does not establish activity, intent, transfer, or wrongdoing. Data: Global Fishing Watch, CC BY-NC 4.0.</small></p></article>
      </div>}
    </div> : <div className="ai-chat"><div className="ai-chat-heading"><p>Ask follow-up questions in the same conversation.</p>{turns.length > 0 && <button disabled={Boolean(busy)} onClick={() => { setTurns([]); setQuestion(''); setError('') }}>Clear chat</button>}</div>
      <div className="ai-conversation">{turns.map((turn, index) => <div className="ai-turn" key={index}><p className="ai-question"><strong>You</strong>{turn.question}</p><div className="ai-answer" ref={index === turns.length - 1 ? answerElement : undefined} tabIndex={-1}><span className="ai-meta">Wake AI</span><Answer result={turn.answer} headingLevel="h4" /></div></div>)}</div>
      <div className="ai-suggestions" aria-label="Suggested questions">{(lastAnswer?.suggestedQuestions.length ? lastAnswer.suggestedQuestions : starterQuestions.filter(value => target.caseId || !value.includes('priority'))).map(prompt => <button key={prompt} disabled={!ready} onClick={() => { setQuestion(prompt); void run('chat', prompt) }}>{prompt}</button>)}</div>
      <form onSubmit={event => { event.preventDefault(); void run('chat') }}><label htmlFor={`${prefix}-question`}>Your question</label><textarea id={`${prefix}-question`} value={question} maxLength={4000} rows={3} onChange={event => setQuestion(event.target.value)} placeholder="What can these records tell us?" /><div className="ai-send"><small>Uses the latest context and five previous exchanges.</small><button className="primary-button" disabled={!ready || !question.trim()} type="submit">{busy === 'chat' ? 'Thinking…' : 'Ask AI'}</button></div></form>
    </div>}
    {busy && <div className="ai-progress" role="status"><span>{busy === 'context' ? 'Loading this ship’s source records…' : busy === 'report' ? 'Reading the evidence and writing your report…' : 'Reading the evidence and your question…'}</span><button onClick={cancel}>Cancel</button></div>}
    {error && <p className="ai-error" role="alert">{error}</p>}
  </section>
}

function Answer({ result, headingLevel: Heading }: { result: AiResult; headingLevel: 'h2' | 'h4' }) {
  return <><p className="ai-summary">{result.summary}</p>{result.sections.map((section, index) => <section className="ai-response-section" key={index}><Heading>{section.heading}</Heading><p>{section.text}</p>{section.sourceIds.length > 0 && <small className="ai-citations">Sources: {section.sourceIds.map(id => result.context.sources.find(source => source.id === id)?.label ?? id).join('; ')}</small>}</section>)}</>
}
