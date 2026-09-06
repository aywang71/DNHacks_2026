// A compact, local reference layer of major commercial ports. Keeping this in
// the client lets the map retain geographic context without a tile service.
export const ports = [
  ['Anchorage', -149.9, 61.22], ['Seattle', -122.33, 47.6], ['Los Angeles', -118.24, 33.74], ['Long Beach', -118.2, 33.75], ['Oakland', -122.28, 37.8],
  ['Vancouver', -123.12, 49.29], ['Balboa', -79.57, 8.95], ['Santos', -46.33, -23.96], ['Rio de Janeiro', -43.17, -22.9], ['Buenos Aires', -58.37, -34.6],
  ['Halifax', -63.58, 44.65], ['New York', -74.04, 40.68], ['Norfolk', -76.3, 36.95], ['Houston', -95.0, 29.73], ['New Orleans', -90.07, 29.95],
  ['Rotterdam', 4.29, 51.89], ['Antwerp', 4.4, 51.23], ['Hamburg', 9.99, 53.54], ['Bremerhaven', 8.58, 53.55], ['Le Havre', 0.11, 49.49],
  ['Felixstowe', 1.35, 51.96], ['Piraeus', 23.64, 37.94], ['Istanbul', 28.97, 40.98], ['Genoa', 8.93, 44.4], ['Algeciras', -5.45, 36.13],
  ['Tangier Med', -5.5, 35.89], ['Alexandria', 29.87, 31.2], ['Durban', 31.04, -29.87], ['Cape Town', 18.44, -33.91], ['Mombasa', 39.67, -4.05],
  ['Djibouti', 43.15, 11.59], ['Jebel Ali', 55.03, 25.01], ['Karachi', 67.0, 24.79], ['Mumbai', 72.84, 18.94], ['Colombo', 79.84, 6.95],
  ['Chittagong', 91.8, 22.3], ['Singapore', 103.85, 1.26], ['Port Klang', 101.36, 3.0], ['Tanjung Pelepas', 103.54, 1.36], ['Jakarta', 106.87, -6.1],
  ['Manila', 120.96, 14.59], ['Ho Chi Minh City', 106.7, 10.77], ['Laem Chabang', 100.88, 13.08], ['Hong Kong', 114.17, 22.29], ['Shenzhen', 114.06, 22.54],
  ['Guangzhou', 113.27, 23.13], ['Xiamen', 118.09, 24.48], ['Shanghai', 121.49, 31.23], ['Ningbo-Zhoushan', 121.55, 29.87], ['Qingdao', 120.31, 36.07],
  ['Tianjin', 117.7, 39.0], ['Dalian', 121.64, 38.92], ['Busan', 129.04, 35.1], ['Tokyo', 139.77, 35.63], ['Yokohama', 139.65, 35.45],
  ['Nagoya', 136.88, 35.08], ['Kobe', 135.19, 34.68], ['Vladivostok', 131.89, 43.12], ['Nakhodka', 132.87, 42.82], ['Petropavlovsk-Kamchatsky', 158.65, 53.02],
  ['Suva', 178.43, -18.14], ['Auckland', 174.77, -36.84], ['Melbourne', 144.93, -37.84], ['Sydney', 151.21, -33.86], ['Perth', 115.86, -31.96]
] as const

export const portFeatures = {
  type: 'FeatureCollection',
  features: ports.map(([name, lon, lat]) => ({
    type: 'Feature',
    properties: { name },
    geometry: { type: 'Point', coordinates: [lon, lat] }
  }))
}
