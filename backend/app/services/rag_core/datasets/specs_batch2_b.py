# -*- coding: utf-8 -*-
"""第二批评测规格 B：Windows / 密码学 / 渗透 / 应急 / 数据 / 移动安全（样例语料 kb-7~kb-17）。

每条 supported 用例的 must_contain 均为语料中的逐字片段，由 chunker 定位真实行号。
"""

RAW_SPECS_BATCH2_B = [
    # ===== Windows 策略（kb-7） =====
    {
        "case_key": "v2rag-083",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "Windows 账户锁定策略一般怎么设？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-7",
                "must_contain": "账户锁定阈值：5次无效登录",
            }
        ],
        "tags": ["Windows", "账户策略"],
        "rationale": "锁定阈值限制无效登录次数。",
    },
    {
        "case_key": "v2rag-084",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "为什么建议启用 UAC？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-7",
                "must_contain": "启用UAC（用户账户控制）",
            }
        ],
        "tags": ["Windows", "UAC"],
        "rationale": "UAC 降低特权滥用风险。",
    },
    {
        "case_key": "v2rag-085",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "Windows 密码最长使用期建议多久？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-7",
                "must_contain": "密码最长使用期：90天",
            }
        ],
        "tags": ["Windows", "密码策略"],
        "rationale": "密码最长使用期建议 90 天。",
    },
    # ===== 对称/非对称加密（kb-8） =====
    {
        "case_key": "v2rag-086",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "AES 支持的密钥长度有哪些？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-8",
                "must_contain": "高级加密标准，密钥长度128/192/256位",
            }
        ],
        "tags": ["AES", "对称加密"],
        "rationale": "AES 密钥长度 128/192/256。",
    },
    {
        "case_key": "v2rag-087",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "RSA 为什么要用 2048 位以上？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-8",
                "must_contain": "基于大数分解难题，2048位以上安全",
            }
        ],
        "tags": ["RSA", "非对称加密"],
        "rationale": "RSA 基于大数分解，需 2048 位以上。",
    },
    {
        "case_key": "v2rag-088",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "混合加密里对称和非对称分别干什么？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-8",
                "must_contain": "用非对称加密传递对称密钥",
            }
        ],
        "tags": ["混合加密", "密钥交换"],
        "rationale": "混合加密用非对称传递对称密钥。",
    },
    # ===== 数字签名/证书（kb-9） =====
    {
        "case_key": "v2rag-089",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "数字签名为什么能确认发送者不可抵赖？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-9",
                "must_contain": "确认发送者身份（不可抵赖）",
            }
        ],
        "tags": ["数字签名", "不可抵赖"],
        "rationale": "数字签名提供发送者身份与不可抵赖。",
    },
    {
        "case_key": "v2rag-090",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "PKI 里的 CA 是什么？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-9",
                "must_contain": "证书颁发机构",
            }
        ],
        "tags": ["PKI", "CA"],
        "rationale": "CA 是证书颁发机构。",
    },
    {
        "case_key": "v2rag-091",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "OCSP 的作用是什么？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-9",
                "must_contain": "在线证书状态协议",
            }
        ],
        "tags": ["PKI", "OCSP"],
        "rationale": "OCSP 用于在线查询证书状态。",
    },
    # ===== 信息收集（kb-10） =====
    {
        "case_key": "v2rag-092",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "被动信息收集里 whois 能拿到什么？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-10",
                "must_contain": "whois example.com",
            }
        ],
        "tags": ["信息收集", "whois"],
        "rationale": "whois 获取域名注册信息。",
    },
    {
        "case_key": "v2rag-093",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "SYN 扫描用 nmap 怎么写？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-10",
                "must_contain": "nmap -sS -p- 192.168.1.1",
            }
        ],
        "tags": ["nmap", "端口扫描"],
        "rationale": "nmap -sS 为 SYN 扫描。",
    },
    {
        "case_key": "v2rag-094",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "Google Hacking 怎么搜某个站的 PDF？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-10",
                "must_contain": "site:example.com filetype:pdf",
            }
        ],
        "tags": ["Google Hacking", "搜索引擎"],
        "rationale": "site+filetype 限定搜索。",
    },
    # ===== Metasploit（kb-11） =====
    {
        "case_key": "v2rag-095",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "怎么启动 Metasploit 控制台？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-11",
                "must_contain": "msfconsole",
            }
        ],
        "tags": ["Metasploit", "msfconsole"],
        "rationale": "msfconsole 启动控制台。",
    },
    {
        "case_key": "v2rag-096",
        "category": "retrieval_supported",
        "difficulty": "hard",
        "query": "永恒之蓝在 Metasploit 里对应哪个模块？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-11",
                "must_contain": "use exploit/windows/smb/ms17_010_eternalblue",
            }
        ],
        "tags": ["Metasploit", "MS17-010"],
        "rationale": "ms17_010_eternalblue 对应永恒之蓝。",
    },
    {
        "case_key": "v2rag-097",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "MS17-010 的中文名是什么？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-11",
                "must_contain": "MS17-010（永恒之蓝）",
            }
        ],
        "tags": ["Metasploit", "漏洞"],
        "rationale": "MS17-010 即永恒之蓝。",
    },
    # ===== 事件分级（kb-12） =====
    {
        "case_key": "v2rag-098",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "勒索软件属于哪类安全事件？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-12",
                "must_contain": "勒索软件",
            }
        ],
        "tags": ["事件分类", "恶意代码"],
        "rationale": "勒索软件属恶意代码事件。",
    },
    {
        "case_key": "v2rag-099",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "APT 攻击属于哪类事件？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-12",
                "must_contain": "APT攻击",
            }
        ],
        "tags": ["事件分类", "APT"],
        "rationale": "APT 属网络攻击事件。",
    },
    {
        "case_key": "v2rag-100",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "特别重大安全事件（I级）指什么？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-12",
                "must_contain": "特别重大事件（I级）",
            }
        ],
        "tags": ["事件分级", "I级"],
        "rationale": "I 级为特别重大事件。",
    },
    # ===== 取证（kb-13） =====
    {
        "case_key": "v2rag-101",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "数字取证为什么要用哈希保证完整性？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-13",
                "must_contain": "使用哈希校验",
            }
        ],
        "tags": ["数字取证", "哈希"],
        "rationale": "哈希保证证据不被篡改。",
    },
    {
        "case_key": "v2rag-102",
        "category": "retrieval_supported",
        "difficulty": "hard",
        "query": "内存镜像用 Volatility 怎么列进程？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-13",
                "must_contain": "volatility -f memory.img pslist",
            }
        ],
        "tags": ["数字取证", "Volatility"],
        "rationale": "volatility pslist 列进程。",
    },
    {
        "case_key": "v2rag-103",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "网络取证里怎么抓包？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-13",
                "must_contain": "tcpdump -i eth0 -w capture.pcap",
            }
        ],
        "tags": ["网络取证", "tcpdump"],
        "rationale": "tcpdump 抓包存 pcap。",
    },
    # ===== 数据加密（kb-14） =====
    {
        "case_key": "v2rag-104",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "透明数据加密 TDE 是哪一层的加密？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-14",
                "must_contain": "透明数据加密（TDE）",
            }
        ],
        "tags": ["数据加密", "TDE"],
        "rationale": "TDE 为数据库级加密。",
    },
    {
        "case_key": "v2rag-105",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "列级加密通常加密哪些字段？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-14",
                "must_contain": "对敏感列（如身份证号、银行卡号）单独加密。",
            }
        ],
        "tags": ["数据加密", "列级加密"],
        "rationale": "列级加密针对敏感字段。",
    },
    {
        "case_key": "v2rag-106",
        "category": "retrieval_supported",
        "difficulty": "hard",
        "query": "密钥分层里 DEK 做什么？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-14",
                "must_contain": "数据密钥（DEK）：加密实际数据",
            }
        ],
        "tags": ["密钥管理", "DEK"],
        "rationale": "DEK 加密实际数据。",
    },
    # ===== GDPR（kb-15） =====
    {
        "case_key": "v2rag-107",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "GDPR 的数据最小化原则是什么？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-15",
                "must_contain": "只收集必要的数据。",
            }
        ],
        "tags": ["GDPR", "数据最小化"],
        "rationale": "数据最小化只收集必要数据。",
    },
    {
        "case_key": "v2rag-108",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "GDPR 里被遗忘权对应什么权利？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-15",
                "must_contain": "要求删除数据（被遗忘权）",
            }
        ],
        "tags": ["GDPR", "删除权"],
        "rationale": "删除权即被遗忘权。",
    },
    {
        "case_key": "v2rag-109",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "GDPR 的数据可携权指什么？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-15",
                "must_contain": "获取结构化格式的数据",
            }
        ],
        "tags": ["GDPR", "数据可携权"],
        "rationale": "数据可携权获取结构化数据。",
    },
    # ===== Android（kb-16） =====
    {
        "case_key": "v2rag-110",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "Android 静态分析常用 Jadx 做什么？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-16",
                "must_contain": "Jadx（反编译）",
            }
        ],
        "tags": ["Android", "Jadx"],
        "rationale": "Jadx 用于反编译。",
    },
    {
        "case_key": "v2rag-111",
        "category": "retrieval_supported",
        "difficulty": "hard",
        "query": "怎么用 apktool 反编译 APK？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-16",
                "must_contain": "apktool d app.apk -o output",
            }
        ],
        "tags": ["Android", "apktool"],
        "rationale": "apktool d 反编译 APK。",
    },
    {
        "case_key": "v2rag-112",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "Android 静态检查要查哪些硬编码风险？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-16",
                "must_contain": "硬编码密钥/密码",
            }
        ],
        "tags": ["Android", "硬编码"],
        "rationale": "检查硬编码密钥/密码。",
    },
    # ===== iOS（kb-17） =====
    {
        "case_key": "v2rag-113",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "iOS 的 Sandbox 沙盒限制什么？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-17",
                "must_contain": "每个应用运行在独立沙盒中，无法访问其他应用数据。",
            }
        ],
        "tags": ["iOS", "沙盒"],
        "rationale": "沙盒隔离各应用数据。",
    },
    {
        "case_key": "v2rag-114",
        "category": "retrieval_supported",
        "difficulty": "easy",
        "query": "为什么 iOS 推荐 SSL Pinning？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-17",
                "must_contain": "SSL Pinning",
            }
        ],
        "tags": ["iOS", "SSL Pinning"],
        "rationale": "SSL Pinning 防中间人。",
    },
    {
        "case_key": "v2rag-115",
        "category": "retrieval_supported",
        "difficulty": "medium",
        "query": "ATS 应用传输安全强制什么？",
        "expected_status": "supported",
        "evidence": [
            {
                "document_id": "kb-17",
                "must_contain": "强制HTTPS连接，拒绝不安全的HTTP。",
            }
        ],
        "tags": ["iOS", "ATS"],
        "rationale": "ATS 强制 HTTPS。",
    },
]
