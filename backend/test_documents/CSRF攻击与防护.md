# CSRF攻击与防护

## 概念

跨站请求伪造（Cross-Site Request Forgery，CSRF）是一种攻击，迫使已登录用户执行非本意的操作。

## 攻击原理

1. 用户登录网站A
2. 攻击者诱导用户访问恶意网站B
3. 恶意网站B向网站A发起请求，使用用户的Cookie

## 防护措施

### 1. CSRF Token
在表单中添加随机token。

### 2. SameSite Cookie
设置Cookie的SameSite属性。

### 3. 验证Referer
检查请求来源。

### 4. 双重提交
将token放在Cookie和参数中。

## 相关标签
CSRF, Web安全, 会话安全
