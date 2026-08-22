# -*- coding: utf-8 -*-
"""第二批评测规格 A：网络安全基础 / Web 安全 / 系统安全 / 密码学（样例语料 kb-1~kb-9）。

每条 supported 用例的 must_contain 均为语料中的逐字片段，
由 chunker 在 build 阶段定位真实行号，保证 gold evidence 可溯源、不编造。
"""

RAW_SPECS_BATCH2_A = [
    # ===== 网络安全基础（kb-1） =====
    {
        "case_key": "v2rag-065",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "ARP 欺骗为什么能实现中间人攻击？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-1",
                "must_contain": "ARP协议没有认证机制，攻击者可以发送伪造的ARP响应包，将自己的MAC地址绑定到受害者的IP地址，从而实现中间人攻击。",
            }
        ],
        "tags": ["ARP", "中间人攻击"],
        "rationale": "ARP 无认证机制，可伪造响应实现中间人。",
    },
    {
        "case_key": "v2rag-066",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "DNS 劫持是怎么把用户重定向到恶意站点的？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-1",
                "must_contain": "DNS查询缺乏验证，攻击者可以篡改DNS缓存或拦截DNS请求，将用户重定向到恶意站点。",
            }
        ],
        "tags": ["DNS", "劫持"],
        "rationale": "DNS 查询缺乏验证，可篡改缓存或拦截请求。",
    },
    {
        "case_key": "v2rag-067",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "IP 欺骗一般能用来做什么？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-1",
                "must_contain": "攻击者可以伪造源IP地址，绕过基于IP的访问控制或发起SYN Flood攻击。",
            }
        ],
        "tags": ["IP欺骗", "SYN Flood"],
        "rationale": "伪造源 IP 可绕过访问控制或发起泛洪。",
    },
    # ===== 防火墙（kb-2） =====
    {
        "case_key": "v2rag-068",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "包过滤防火墙工作在哪一层，依据什么过滤？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-2",
                "must_contain": "工作在网络层，根据源/目标IP地址、端口号、协议类型等过滤数据包。",
            }
        ],
        "tags": ["防火墙", "包过滤"],
        "rationale": "包过滤工作在网络层，按地址/端口/协议过滤。",
    },
    {
        "case_key": "v2rag-069",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "状态检测防火墙相比包过滤有什么特点？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-2",
                "must_contain": "跟踪连接状态表，根据连接状态动态调整规则。",
            }
        ],
        "tags": ["防火墙", "状态检测"],
        "rationale": "状态检测基于连接状态表动态调整规则。",
    },
    {
        "case_key": "v2rag-070",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "防火墙部署里的纵深防御指什么？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-2",
                "must_contain": "纵深防御",
            }
        ],
        "tags": ["防火墙", "纵深防御"],
        "rationale": "纵深防御是防火墙部署核心策略之一。",
    },
    # ===== SQL 注入（kb-3） =====
    {
        "case_key": "v2rag-071",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "为什么 ' OR '1'='1' 能让登录绕过？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-3",
                "must_contain": "' OR '1'='1' --",
            }
        ],
        "tags": ["SQL注入", "绕过登录"],
        "rationale": "经典注入 payload 使 WHERE 条件恒真。",
    },
    {
        "case_key": "v2rag-072",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "防御 SQL 注入为什么首选参数化查询？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-3",
                "must_contain": "使用预编译语句",
            }
        ],
        "tags": ["SQL注入", "参数化查询"],
        "rationale": "参数化查询是首选防御手段。",
    },
    {
        "case_key": "v2rag-073",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "联合查询注入通常用于做什么？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-3",
                "must_contain": "联合查询注入",
            }
        ],
        "tags": ["SQL注入", "UNION"],
        "rationale": "UNION 注入用于跨表取数。",
    },
    # ===== XSS（kb-4） =====
    {
        "case_key": "v2rag-074",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "存储型 XSS 的恶意脚本存在哪里？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-4",
                "must_contain": "恶意脚本被永久存储在目标服务器（如数据库）中。",
            }
        ],
        "tags": ["XSS", "存储型"],
        "rationale": "存储型 XSS 脚本被持久化在服务端。",
    },
    {
        "case_key": "v2rag-075",
        "category": "retrieval_supported",
        "difficulty": "hard",
        "query": "DOM 型 XSS 的 payload 在哪执行？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-4",
                "must_contain": "攻击payload在客户端通过JavaScript动态生成，不经过服务器。",
            }
        ],
        "tags": ["XSS", "DOM型"],
        "rationale": "DOM 型在客户端由 JS 动态生成。",
    },
    {
        "case_key": "v2rag-076",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "为什么建议给 Cookie 设置 HttpOnly？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-4",
                "must_contain": "HttpOnly标记Cookie",
            }
        ],
        "tags": ["XSS", "Cookie"],
        "rationale": "HttpOnly 可降低 XSS 窃取 Cookie 风险。",
    },
    # ===== CSRF（kb-5） =====
    {
        "case_key": "v2rag-077",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "CSRF Token 是怎么防御跨站请求的？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-5",
                "must_contain": "在表单中添加随机生成的Token，服务器验证其有效性。",
            }
        ],
        "tags": ["CSRF", "Token"],
        "rationale": "CSRF Token 由服务端校验随机值。",
    },
    {
        "case_key": "v2rag-078",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "SameSite Cookie 如何限制跨站请求？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-5",
                "must_contain": "设置Cookie的SameSite属性，限制跨站请求。",
            }
        ],
        "tags": ["CSRF", "SameSite"],
        "rationale": "SameSite 限制跨站携带 Cookie。",
    },
    {
        "case_key": "v2rag-079",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "双重 Cookie 验证怎么工作？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-5",
                "must_contain": "双重Cookie验证",
            }
        ],
        "tags": ["CSRF", "Cookie"],
        "rationale": "双重 Cookie 比较 Cookie 与参数中的 Token。",
    },
    # ===== Linux 加固（kb-6） =====
    {
        "case_key": "v2rag-080",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "如何在 Linux 上禁用一个系统账户？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-6",
                "must_contain": "usermod -s /sbin/nologin apache",
            }
        ],
        "tags": ["Linux", "账户安全"],
        "rationale": "用 usermod 改 shell 为 nologin 禁用账户。",
    },
    {
        "case_key": "v2rag-081",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "为什么要把 /etc/shadow 权限设为 640？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-6",
                "must_contain": "chmod 640 /etc/shadow",
            }
        ],
        "tags": ["Linux", "文件权限"],
        "rationale": "shadow 文件需严格限制权限。",
    },
    {
        "case_key": "v2rag-082",
        "category": "retrieval_supported",
        "difficulty": "hard",
        "query": "怎样列出系统里具有 SUID/SGID 位的文件？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-6",
                "must_contain": "find / -perm -4000 -o -perm -2000 2>/dev/null",
            }
        ],
        "tags": ["Linux", "SUID"],
        "rationale": "find 按特殊权限位检索。",
    },
]
