import { ElMessage as RawMessage, ElMessageBox } from 'element-plus'

const DEFAULT_DURATION = 3000

function withGrouping(options) {
  if (typeof options === 'string') {
    return { message: options, grouping: true, duration: DEFAULT_DURATION }
  }
  return { ...options, grouping: true, duration: options.duration ?? DEFAULT_DURATION }
}

export const ElMessage = {
  success(options) {
    return RawMessage.success(withGrouping(options))
  },
  error(options) {
    return RawMessage.error(withGrouping(options))
  },
  warning(options) {
    return RawMessage.warning(withGrouping(options))
  },
  info(options) {
    return RawMessage.info(withGrouping(options))
  }
}

export { ElMessageBox }
