export function circularBounds(points) {
  if (!points.length) return null
  const lons = [...new Set(points.map(p => ((p.lon % 360) + 360) % 360))].sort((a, b) => a - b)
  let gap = -1, after = 0
  for (let i = 0; i < lons.length; i++) {
    const distance = (i + 1 < lons.length ? lons[i + 1] : lons[0] + 360) - lons[i]
    if (distance > gap) { gap = distance; after = (i + 1) % lons.length }
  }
  let west = lons[after], east = west + 360 - gap
  if (west > 180) { west -= 360; east -= 360 }
  let south = 90, north = -90
  for (const point of points) { south = Math.min(south, point.lat); north = Math.max(north, point.lat) }
  return [west, south, east, north]
}

