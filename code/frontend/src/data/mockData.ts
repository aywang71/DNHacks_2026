import type { Vessel } from '../types'

export const vessels: Vessel[] = [
  {
    id: 'ocean-star', name: 'Ocean Star', imo: 'IMO 9412387', flag: 'Panama', vesselType: 'Crude oil tanker', riskScore: 82, riskLevel: 'high', eventKind: 'dark-period', eventLabel: 'AIS dark period', location: 'Eastern Mediterranean', lastSeen: '31h ago', coordinates: [25.18, 34.51],
    evidence: [
      { id: 'gap', claim: 'AIS unavailable for 31 hours and 18 minutes', source: 'AIS replay', observedAt: '03 Sep 2026, 02:14 UTC', confidence: 'high' },
      { id: 'aoi', claim: 'Signal gap began 11 nm from a monitored transfer zone', source: 'Spatial rule', observedAt: '03 Sep 2026, 02:14 UTC', confidence: 'medium' },
      { id: 'encounter', claim: 'Ocean Pearl remained within 0.4 nm before signal loss', source: 'AIS replay', observedAt: '03 Sep 2026, 01:44–02:12 UTC', confidence: 'medium' }
    ],
    timeline: [
      { time: '03 Sep · 01:44', title: 'Close proximity observed', detail: 'Ocean Pearl entered a 0.4 nm radius.' },
      { time: '03 Sep · 02:14', title: 'Last observed transmission', detail: 'Position and course received from AIS.' },
      { time: '03 Sep · 02:15', title: 'AIS gap begins', detail: 'No position was received for 31h 18m.', emphasis: true },
      { time: '04 Sep · 09:32', title: 'Vessel reappears', detail: 'First observed signal after the gap.' }
    ]
  },
  {
    id: 'mare-azur', name: 'Mare Azur', imo: 'IMO 9317024', flag: 'Liberia', vesselType: 'Product tanker', riskScore: 74, riskLevel: 'review', eventKind: 'encounter', eventLabel: 'Vessel encounter', location: 'Gulf of Guinea', lastSeen: '4h ago', coordinates: [3.38, 4.05],
    evidence: [{ id: 'proximity', claim: 'Sustained close-proximity encounter detected', source: 'AIS replay', observedAt: '05 Sep 2026, 04:20 UTC', confidence: 'medium' }],
    timeline: [{ time: '05 Sep · 04:20', title: 'Close approach', detail: 'Another vessel was detected nearby.', emphasis: true }]
  },
  {
    id: 'northwind', name: 'Northwind', imo: 'IMO 9581340', flag: 'Malta', vesselType: 'Bulk carrier', riskScore: 66, riskLevel: 'watch', eventKind: 'loitering', eventLabel: 'Unusual loitering', location: 'South Atlantic', lastSeen: '7h ago', coordinates: [-21.47, -18.37],
    evidence: [{ id: 'speed', claim: 'Low-speed movement outside port limits', source: 'Movement rule', observedAt: '05 Sep 2026, 01:10 UTC', confidence: 'medium' }],
    timeline: [{ time: '05 Sep · 01:10', title: 'Low-speed pattern detected', detail: 'Movement remained below 1 knot.', emphasis: true }]
  }
]
