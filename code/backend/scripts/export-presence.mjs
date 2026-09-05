import path from 'node:path'
import { exportPresence } from '../src/presence/export.mjs'

const args = process.argv.slice(2), options = {}
for (let i = 0; i < args.length; i += 2) {
  if (!['--input', '--output'].includes(args[i]) || !args[i + 1]) throw new Error('Usage: npm run import:presence -- [--input directory] [--output directory]')
  options[args[i].slice(2)] = path.resolve(args[i + 1])
}
try { const result = await exportPresence(options); console.log(`Exported ${result.observationCount.toLocaleString('en-US')} observations across ${result.coveredHourCount} covered hours (${result.days.length} UTC days).`) }
catch (error) { console.error(error.message); process.exitCode = 1 }
