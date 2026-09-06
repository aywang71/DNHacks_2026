import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { existsSync } from 'node:fs'

const localPython = fileURLToPath(new URL('../../../.venv-model/bin/python', import.meta.url))
const python = process.env.MODEL_PYTHON || (existsSync(localPython) ? localPython : 'python3')
const result = spawnSync(python, [fileURLToPath(new URL('./export-investigations.py', import.meta.url)), ...process.argv.slice(2)], { stdio: 'inherit' })
if (result.error) console.error(result.error.message)
process.exit(result.status ?? 1)
