# SQL注入防护指南

## 概述

SQL注入（SQL Injection）是一种代码注入技术，攻击者通过在应用程序的用户输入中插入恶意SQL语句，从而操纵后台数据库。

## 常见SQL注入类型

### 1. 基于错误的SQL注入
攻击者通过触发数据库错误来获取信息。

```sql
' OR 1=1 --
```

### 2. 联合查询注入
使用UNION SELECT语句获取其他表的数据。

```sql
' UNION SELECT username, password FROM users --
```

### 3. 布尔型注入
通过返回真假判断信息。

```sql
' AND 1=1 --
' AND 1=2 --
```

## 防护措施

### 1. 使用参数化查询
永远不要直接拼接用户输入到SQL语句中。

```python
# 错误写法
query = f"SELECT * FROM users WHERE name = '{name}'"

# 正确写法
cursor.execute("SELECT * FROM users WHERE name = %s", (name,))
```

### 2. 使用ORM框架
如SQLAlchemy、Django ORM等自动处理转义。

### 3. 输入验证
白名单验证，过滤特殊字符。

### 4. 最小权限原则
数据库账户只授予必要的权限。

## 相关标签
SQL注入, Web安全, 数据库安全, 防护
