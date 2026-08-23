/**
 * 系统功能特性开关与熔断配置
 */

/**
 * 检查安全工作台是否开启
 * 可通过前端环境变量 VITE_SECURITY_WORKBENCH_ENABLED 控制（默认 true）
 * 部署上线或需要临时下线安全工作台时，在环境变量中配置 VITE_SECURITY_WORKBENCH_ENABLED=false 即可直接全局熔断
 * @returns {boolean}
 */
export const isSecurityWorkbenchEnabled = () => {
  const raw = import.meta.env?.VITE_SECURITY_WORKBENCH_ENABLED
  if (raw === undefined || raw === null || raw === '') {
    return true
  }
  const normalized = String(raw).trim().toLowerCase()
  return normalized !== 'false' && normalized !== '0' && normalized !== 'off' && normalized !== 'no'
}
