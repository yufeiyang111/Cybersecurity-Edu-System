export const DEFAULT_PARAMS = {
  repulsion: 6000,
  springK: 0.025,
  springLength: 220,
  gravity: 0.02,
  velocityDecay: 0.5,
  alphaDecay: 0.02,
  alphaMin: 0.012,
  maxVelocity: 40,
  maxTicks: 400
}

const randomJitter = (size) => (Math.random() - 0.5) * size

const clamp = (value, min, max) => Math.min(Math.max(value, min), max)

export function createSimNodes(nodes, prevNodes = []) {
  const prevById = new Map(prevNodes.map(n => [n.id, n]))
  const simNodes = []
  for (let i = 0; i < nodes.length; i++) {
    const raw = nodes[i]
    const prev = prevById.get(raw.id)
    simNodes.push({
      id: raw.id,
      label: raw.label || raw.name || String(raw.id),
      raw,
      x: prev ? prev.x : randomJitter(300),
      y: prev ? prev.y : randomJitter(300),
      vx: 0,
      vy: 0,
      fixed: false,
      degree: raw.degree || raw.value || 1
    })
  }
  return simNodes
}

export function createSimEdges(edges, simNodes) {
  const indexById = new Map(simNodes.map((n, i) => [n.id, i]))
  const count = Math.max(1, simNodes.length)
  const restBase = DEFAULT_PARAMS.springLength * Math.sqrt(count / 40)
  const simEdges = []
  for (const edge of edges) {
    const sourceIdx = indexById.get(edge.source)
    const targetIdx = indexById.get(edge.target)
    if (sourceIdx === undefined || targetIdx === undefined) continue
    simEdges.push({
      sourceIdx,
      targetIdx,
      raw: edge,
      restLength: restBase * (0.85 + Math.random() * 0.3)
    })
  }
  return simEdges
}

export function stepSim(simNodes, simEdges, params = DEFAULT_PARAMS, alpha = 1) {
  const count = Math.max(1, simNodes.length)
  const { springK, gravity, velocityDecay, maxVelocity } = params
  const repulsion = params.repulsion * Math.max(1, count / 40)
  let maxMove = 0

  for (let i = 0; i < count; i++) {
    const a = simNodes[i]
    for (let j = i + 1; j < count; j++) {
      const b = simNodes[j]
      let dx = a.x - b.x
      let dy = a.y - b.y
      let d2 = dx * dx + dy * dy
      if (d2 < 1) {
        dx = randomJitter(0.4)
        dy = randomJitter(0.4)
        d2 = dx * dx + dy * dy
      }
      const d = Math.sqrt(d2)
      const force = (repulsion / d2) * alpha
      const fx = (dx / d) * force
      const fy = (dy / d) * force
      a.vx += fx
      a.vy += fy
      b.vx -= fx
      b.vy -= fy
    }
  }

  for (const edge of simEdges) {
    const a = simNodes[edge.sourceIdx]
    const b = simNodes[edge.targetIdx]
    const dx = a.x - b.x
    const dy = a.y - b.y
    const d = Math.sqrt(dx * dx + dy * dy) || 1
    const force = springK * (d - edge.restLength) * alpha
    const fx = (dx / d) * force
    const fy = (dy / d) * force
    a.vx -= fx
    a.vy -= fy
    b.vx += fx
    b.vy += fy
  }

  for (const node of simNodes) {
    node.vx += -node.x * gravity * alpha
    node.vy += -node.y * gravity * alpha
    node.vx *= velocityDecay
    node.vy *= velocityDecay
    node.vx = clamp(node.vx, -maxVelocity, maxVelocity)
    node.vy = clamp(node.vy, -maxVelocity, maxVelocity)
    if (node.fixed) continue
    node.x += node.vx
    node.y += node.vy
    const move = Math.abs(node.vx) + Math.abs(node.vy)
    if (move > maxMove) maxMove = move
  }

  return maxMove
}

export function computeBBox(simNodes) {
  if (!simNodes.length) return { minX: 0, minY: 0, maxX: 0, maxY: 0, w: 1, h: 1 }
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const node of simNodes) {
    if (node.x < minX) minX = node.x
    if (node.x > maxX) maxX = node.x
    if (node.y < minY) minY = node.y
    if (node.y > maxY) maxY = node.y
  }
  return {
    minX,
    minY,
    maxX,
    maxY,
    w: Math.max(maxX - minX, 1),
    h: Math.max(maxY - minY, 1)
  }
}
