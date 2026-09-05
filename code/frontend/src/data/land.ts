import { feature } from 'topojson-client'
import landTopology from 'world-atlas/land-50m.json'

// Natural Earth land geometry, packaged locally by world-atlas. The 50 m
// dataset keeps coastlines recognizable after a few zoom steps while staying
// compact enough to render locally without a tile service.
export const land = feature(landTopology, landTopology.objects.land)
