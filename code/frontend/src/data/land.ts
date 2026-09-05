import { feature } from 'topojson-client'
import landTopology from 'world-atlas/land-110m.json'

// Natural Earth land geometry, packaged locally by world-atlas. Using this
// rather than hand-drawn polygons preserves real coastlines while keeping the
// map usable without a tile service.
export const land = feature(landTopology, landTopology.objects.land)
