declare module 'world-atlas/land-50m.json' {
  const topology: any
  export default topology
}

declare module 'topojson-client' {
  export function feature(topology: any, object: any): any
}
