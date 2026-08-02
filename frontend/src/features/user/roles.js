const ROLE_TEXT = {
  admin: '管理员',
  teacher: '教师',
  user: '普通用户',
  guest: '游客'
}

export function getRoleText(role) {
  return ROLE_TEXT[role] || role || '未知'
}
