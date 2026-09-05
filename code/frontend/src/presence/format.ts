export const formatTime = (timestamp: number | string) => new Date(timestamp).toLocaleString('en-GB', {
  timeZone: 'UTC', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
}) + ' UTC'
