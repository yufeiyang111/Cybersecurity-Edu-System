// T11 Agent SSE 单一 Parser（纯函数，无依赖，Node 可直接测试）。
//
// 解析 id/event/data 帧、正式 heartbeat、多行 data、尾帧与错误帧；
// 不维护第二份解析逻辑（api/index.js 的流循环只调用本模块）。

export function parseSseFrame(raw) {
  if (!raw || typeof raw !== 'string') return null
  const lines = raw.split('\n')
  let id = null
  let event = null
  const dataLines = []
  let isComment = true

  for (const line of lines) {
    if (!line.trim()) {
      continue
    }
    if (line.startsWith(':')) {
      continue
    }
    isComment = false
    if (line.startsWith('id:')) {
      id = line.slice(3).trim()
    } else if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).replace(/^ /, ''))
    }
  }

  // 只有纯注释行才是 ping；空行/无内容直接忽略
  if (isComment) {
    return { event: 'ping', id: null, data: null }
  }
  if (!dataLines.length && event == null && id == null) {
    return null
  }

  const data = dataLines.join('\n')
  let parsed = null
  if (data) {
    try {
      parsed = JSON.parse(data)
    } catch (e) {
      parsed = { __raw: data }
    }
  }
  return {
    id: id != null ? Number(id) : null,
    event: event || 'message',
    data: parsed
  }
}

// 增量解析：接收 buffer 字符串，返回 { frames, rest }
export function parseSseChunk(buffer) {
  const frames = []
  let rest = buffer
  let separator
  while ((separator = rest.indexOf('\n\n')) !== -1) {
    const raw = rest.slice(0, separator)
    rest = rest.slice(separator + 2)
    const frame = parseSseFrame(raw)
    if (frame) frames.push(frame)
  }
  return { frames, rest }
}
