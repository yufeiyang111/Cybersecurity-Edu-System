export function createRoutePrefetcher(routeLoaders) {
  const completed = new Set()
  const pending = new Map()

  return (routeName) => {
    if (completed.has(routeName)) {
      return Promise.resolve()
    }

    const currentRequest = pending.get(routeName)
    if (currentRequest) {
      return currentRequest
    }

    const loader = routeLoaders?.[routeName]
    if (typeof loader !== 'function') {
      return Promise.resolve()
    }

    const request = Promise.resolve()
      .then(() => loader())
      .then(() => {
        completed.add(routeName)
      })
      .catch(() => undefined)
      .finally(() => {
        pending.delete(routeName)
      })

    pending.set(routeName, request)
    return request
  }
}