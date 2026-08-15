/**
 * 仅将已认证用户的工作区拒绝识别为 Agent Run 无权限终态。
 */
export function isAgentRunAccessDenied(error) {
  return Number(error?.response?.status) === 403
}

/**
 * Run 主详情是所有附属数据的授权与状态前提。
 */
export function shouldLoadAgentRunSupplementalData({ runLoaded, accessDenied }) {
  return Boolean(runLoaded) && !accessDenied
}
