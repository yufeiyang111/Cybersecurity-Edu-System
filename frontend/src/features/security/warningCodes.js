/**
 * RAG 治理警告 code / 注入 flag 的中文说明映射。
 * 未知 code 原样回退，保证前端对新 code 不破版。
 */

const INJECTION_FLAG_LABELS = {
  ignore_instructions: '尝试诱导忽略指令',
  system_override: '尝试覆盖系统角色',
  new_instructions: '试图植入新指令',
  reveal_prompt: '尝试套取提示词',
  delimiter_escape: '尝试逃逸内容定界'
}

const WARNING_CODE_LABELS = {
  CITATION_INJECTION_FILTERED: '已剔除疑似注入的知识引用',
  LLM_DISABLED: 'LLM 生成未启用，已回退规则建议',
  LLM_PROVIDER_FAILED: 'LLM 生成失败，已回退规则建议',
  LLM_PROVIDER_UNAVAILABLE: 'LLM 服务暂不可用',
  LLM_PROVIDER_REQUEST_FAILED: 'LLM 请求失败',
  LLM_PROVIDER_RESPONSE_INVALID: 'LLM 响应格式无效',
  LLM_OUTPUT_INVALID: 'LLM 输出无法解析',
  REMEDIATION_LLM_ENABLED: '已启用 LLM 修复建议',
  SECRET_PATCH_WITHHELD: '补丁含敏感内容，已隐藏',
  PATCH_SENSITIVE_CONTENT: '补丁含敏感内容，已隐藏',
  PATCH_CONTEXT_SENSITIVE: '补丁上下文含敏感内容',
  PATCH_CONTEXT_UNAVAILABLE: '补丁上下文不可用',
  PATCH_FORMAT_INVALID: '补丁格式无效，未生成补丁',
  PATCH_TARGET_PATTERN_NOT_FOUND: '未找到补丁目标位置',
  RULE_BASED_NO_PATCH: '规则模式未生成补丁',
  CONTEXT_PATH_INVALID: '上下文路径无效',
  CONTEXT_TRUNCATED: '上下文超长已截断',
  CONTEXT_UNAVAILABLE: '上下文不可用',
  SECRET_CONTEXT_WITHHELD: '上下文含敏感内容，已隐藏',
  REMEDIATION_MAX_CONTEXT_CHARS: '上下文超过字符上限'
}

export function injectionFlagLabel(flag) {
  return INJECTION_FLAG_LABELS[flag] || flag
}

export function warningCodeLabel(code) {
  return WARNING_CODE_LABELS[code] || code
}

/**
 * 解析服务端 rag_warnings 条目："docId:flag1,flag2" → { id, flags, flagsText }
 */
export function parseRagWarning(raw) {
  if (typeof raw !== 'string') {
    return { id: String(raw ?? ''), flags: [], flagsText: '' }
  }
  const separator = raw.indexOf(':')
  const id = separator === -1 ? raw : raw.slice(0, separator)
  const flags = separator === -1 ? [] : raw.slice(separator + 1).split(',').filter(Boolean)
  return { id, flags, flagsText: flags.map(injectionFlagLabel).join('；') }
}
