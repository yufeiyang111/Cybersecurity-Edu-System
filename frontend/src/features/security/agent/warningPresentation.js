const WARNING_PRESENTATIONS = {
  AGENT_REPEATED_TOOL_CALL: {
    title: '已拦截重复工具调用',
    detail: '系统识别到相同工具调用会重复执行，已停止重复请求并保留现有证据。'
  },
  AGENT_MODEL_ERRORS_EXCEEDED: {
    title: '模型调用连续失败',
    detail: '模型调用连续失败已达到保护阈值，系统已停止继续重试并保留可用结果。'
  },
  AGENT_ITERATION_LIMIT_REACHED: {
    title: '达到迭代上限',
    detail: '本轮已达到允许的迭代次数，系统已结束继续扩展以控制执行范围。'
  },
  AGENT_BUDGET_EXHAUSTED: {
    title: '预算已用尽',
    detail: '本轮调用预算已达到上限，系统已停止继续扩展，以避免无意义循环。'
  },
  AGENT_BASELINE_MODEL_SUMMARY_FALLBACK: {
    title: '已使用确定性摘要',
    detail: '模型未生成可用摘要，系统已使用确定性扫描摘要作为受控降级结果。'
  },
  AGENT_TOOL_INPUT_INVALID: {
    title: '工具输入未通过校验',
    detail: '系统已拒绝不符合工具契约的输入，未执行对应操作。'
  },
  AGENT_TOOL_FAILED: {
    title: '工具执行失败',
    detail: '单个工具执行未成功，系统会基于其余可用证据继续或安全结束。'
  },
  AGENT_LOOP_ITERATION_FAILED: {
    title: '单轮审计未完成',
    detail: '当前审计轮发生异常，系统已记录状态并按保护策略处理后续步骤。'
  },
  AGENT_MODEL_ACTION_INVALID: {
    title: '模型动作未通过校验',
    detail: '模型建议的动作不符合授权工具契约，系统已拒绝执行该动作。'
  }
}

const DEFAULT_WARNING = {
  title: '运行提示',
  detail: '系统已按保护策略进行受控降级，并保留当前可用的审计结果。'
}

export function presentAgentWarnings(codes) {
  if (!Array.isArray(codes)) {
    return []
  }

  const seen = new Set()
  const warnings = []

  for (const value of codes) {
    if (typeof value !== 'string') {
      continue
    }
    const code = value.trim()
    if (!code || seen.has(code)) {
      continue
    }
    seen.add(code)
    warnings.push(WARNING_PRESENTATIONS[code] || DEFAULT_WARNING)
  }

  return warnings
}
