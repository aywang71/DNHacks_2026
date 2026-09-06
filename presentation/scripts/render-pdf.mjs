import { copyFile, mkdir, rm, stat } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const slidev = resolve(root, 'node_modules', '@slidev', 'cli', 'bin', 'slidev.mjs')
const temporaryPdf = resolve(root, 'slides-export.pdf')
const renderedPdf = resolve(root, 'rendered', 'wake-ai-pitch-deck.pdf')

function run(command, args) {
  return new Promise((resolveRun, rejectRun) => {
    const child = spawn(command, args, { cwd: root, stdio: 'inherit' })
    child.once('error', rejectRun)
    child.once('exit', (code) => {
      if (code === 0) resolveRun()
      else rejectRun(new Error(`Slide export failed with exit code ${code}.`))
    })
  })
}

await rm(temporaryPdf, { force: true })
await run(process.execPath, [slidev, 'export', 'slides.md'])
await mkdir(dirname(renderedPdf), { recursive: true })
await copyFile(temporaryPdf, renderedPdf)
await rm(temporaryPdf, { force: true })

const { size } = await stat(renderedPdf)
console.log(`Rendered PDF: ${renderedPdf} (${size.toLocaleString()} bytes)`)
