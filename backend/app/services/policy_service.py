"""
政策文档领域服务

负责政策文档（用户协议 / 隐私政策）的默认内容、幂等种子、读取与更新。
路由层保持薄层，校验在路由层完成，持久化逻辑收敛到本模块。
"""
from __future__ import annotations

from typing import Optional

from app import db
from app.models.policy import PolicyDocument

TERMS_SLUG = "terms"
PRIVACY_SLUG = "privacy"

DEFAULT_POLICIES: dict[str, dict[str, str]] = {
    TERMS_SLUG: {
        "title": "用户协议",
        "content": """# 用户协议

欢迎使用 **CyberGuard**（以下简称"本平台"）。在使用本平台前，请您仔细阅读并充分理解本协议的全部内容。您注册、登录或使用本平台，即视为您已阅读并同意本协议。

## 一、服务说明

1. 本平台为企业级安全运营与 DevSecOps 工作台，提供安全知识问答、扫描分析、依赖审计、修复建议等服务。
2. 本平台可能根据业务需要调整、升级或中止部分功能，并会以合理方式提前告知。

## 二、账号管理

1. 您应使用真实、合法、有效的个人信息完成注册，并对账号下的一切操作行为负责。
2. 您应妥善保管账号与密码，因保管不善造成的损失由您自行承担。
3. 如发现账号被他人盗用或存在安全风险，请立即告知本平台。

## 三、用户行为规范

您承诺不利用本平台从事以下行为：

1. 违反法律法规或公序良俗；
2. 干扰、破坏或攻击本平台及相关系统；
3. 上传、发布或传播虚假、侵权、恶意内容；
4. 未经授权访问他人账号或数据；
5. 其他危害平台安全或他人权益的行为。

## 四、知识产权

1. 本平台的界面设计、软件程序、商标等归本平台或其权利人所有。
2. 您在本平台发布的内容，相关权利仍归您所有，但您授予本平台在提供服务的范围内使用该内容的许可。

## 五、免责声明

1. 本平台提供的信息与分析结果仅供参考，不构成任何形式的专业建议或承诺。
2. 因不可抗力、第三方原因或您自身操作导致的服务中断或损失，本平台在法律允许的范围内不承担相关责任。

## 六、协议变更

本平台有权根据运营需要修订本协议。修订后的协议将通过平台公示，修订生效后您继续使用本平台即视为接受修订内容。

## 七、法律适用与争议解决

本协议适用中华人民共和国法律。因本协议引起的争议，双方应友好协商解决；协商不成的，任何一方可向本平台运营方所在地有管辖权的人民法院提起诉讼。
""",
    },
    PRIVACY_SLUG: {
        "title": "隐私政策",
        "content": """# 隐私政策

本隐私政策（以下简称"本政策"）说明 **CyberGuard**（以下简称"本平台"）如何收集、使用、存储与保护您的个人信息。我们深知个人信息对您的重要性，并将严格遵循相关法律法规的要求保护您的隐私。

## 一、我们收集的信息

1. **注册信息**：您在注册时提供的用户名、邮箱、昵称等账号信息。
2. **使用信息**：您在本平台的知识问答记录、收藏内容、浏览与操作行为。
3. **安全扫描信息**：您在安全运营场景下授权上传的代码快照、依赖清单等（仅用于分析目的）。
4. **设备与日志信息**：访问时间、IP 地址、浏览器类型等基础访问日志。

## 二、信息的使用

我们仅在以下目的范围内使用您的信息：

1. 提供、维护与改进本平台的功能与服务；
2. 处理您的问答请求并返回结果；
3. 开展安全审计与异常检测，保障平台与账号安全；
4. 在法律要求的范围内履行合规义务。

## 三、信息的存储与保护

1. 您的信息存储于我们采用合理安全措施保护的服务器中。
2. 我们使用加密、访问控制、日志审计等手段保护您的数据。
3. 我们将仅在本政策所述目的的存续期内保留您的个人信息，超期后将进行删除或匿名化处理。

## 四、信息的共享与披露

我们不会向无关第三方出售您的个人信息。仅在以下情形下可能共享：

1. 获得您的明确同意；
2. 法律法规、司法或行政主管机关的要求；
3. 为保障本平台或其他用户的合法权益所必需。

## 五、您的权利

您有权访问、更正、删除您的个人信息，并有权注销账号。您可通过平台个人中心或联系我们行使上述权利。

## 六、未成年人保护

本平台主要面向企业用户。若您为未成年人，请在监护人指导下使用本平台。

## 七、政策更新

本政策可能适时更新。重大变更将通过平台显著位置公示，您继续使用本平台即视为接受更新后的政策。

## 八、联系我们

如您对本政策有任何疑问、意见或建议，欢迎通过平台公示的联系方式与我们联系。
""",
    },
}


def ensure_policy_documents() -> None:
    """惰性创建默认政策文档，幂等；已有文档时不重复写入。"""
    if PolicyDocument.query.count() > 0:
        return
    for slug, data in DEFAULT_POLICIES.items():
        db.session.add(
            PolicyDocument(
                slug=slug,
                title=data["title"],
                content=data["content"],
                version=1,
                updated_by="system",
            )
        )
    db.session.commit()


def list_policies() -> list[PolicyDocument]:
    ensure_policy_documents()
    return PolicyDocument.query.order_by(PolicyDocument.id.asc()).all()


def get_policy(slug: str) -> Optional[PolicyDocument]:
    ensure_policy_documents()
    return PolicyDocument.query.filter_by(slug=slug).first()


def update_policy(slug: str, title: str, content: str, updated_by: str) -> PolicyDocument:
    """更新政策文档，版本自增并记录更新人；文档不存在时按 slug 创建。"""
    policy = PolicyDocument.query.filter_by(slug=slug).first()
    if policy is None:
        policy = PolicyDocument(slug=slug, title=title, content=content, version=1)
        db.session.add(policy)
    else:
        policy.title = title
        policy.content = content
        policy.version = (policy.version or 1) + 1
    policy.updated_by = updated_by
    db.session.commit()
    return policy
