"""项目级扫描排除规则应用服务：校验、持久化、审计。

路由只负责授权与 HTTP 映射；本模块保证规则以 gitignore 语义被校验并有序存储。
"""
from __future__ import annotations

from typing import Iterable, Sequence

from app import db
from app.models.security import AuditEvent, ProjectExclusionRule, SecurityProject
from app.services.scan_exclusion import compile_patterns, GitignoreMatcher


class ExclusionRuleError(ValueError):
    """规则不合法（空、注释或无法编译）。"""


def patterns_for_project(project_id: int) -> list[str]:
    """按 position 顺序返回项目的有效规则行，供扫描链路使用。"""
    rows = (
        ProjectExclusionRule.query.filter_by(project_id=project_id)
        .order_by(ProjectExclusionRule.position.asc(), ProjectExclusionRule.id.asc())
        .all()
    )
    return [row.pattern for row in rows]


def matcher_for_project(project_id: int) -> GitignoreMatcher | None:
    """构建项目排除匹配器；无规则时返回 None。"""
    patterns = patterns_for_project(project_id)
    if not patterns:
        return None
    return GitignoreMatcher.from_patterns(patterns)


def list_exclusion_rules(project_id: int) -> list[ProjectExclusionRule]:
    return (
        ProjectExclusionRule.query.filter_by(project_id=project_id)
        .order_by(ProjectExclusionRule.position.asc(), ProjectExclusionRule.id.asc())
        .all()
    )


def _write_audit(project: SecurityProject, actor_id: int, action: str, rule_id: int) -> None:
    db.session.add(
        AuditEvent(
            workspace_id=project.workspace_id,
            actor_id=actor_id,
            action=action,
            target_type="exclusion_rule",
            target_id=rule_id,
            metadata_json={},
        )
    )


def add_exclusion_rule(
    project: SecurityProject,
    actor_id: int,
    pattern: str,
) -> ProjectExclusionRule:
    """追加一条有效规则；无效规则直接报错。"""
    valid = compile_patterns([pattern])
    if not valid:
        raise ExclusionRuleError("规则为空或不是有效的匹配模式")
    next_position = _next_position(project.id)
    rule = ProjectExclusionRule(
        project_id=project.id,
        pattern=valid[0],
        position=next_position,
        created_by=actor_id,
    )
    db.session.add(rule)
    db.session.flush()
    _write_audit(project, actor_id, "scan.exclusion.added", rule.id)
    db.session.commit()
    return rule


def delete_exclusion_rule(rule: ProjectExclusionRule, actor_id: int) -> None:
    """删除单条规则并记录审计。"""
    project = db.session.get(SecurityProject, rule.project_id)
    rule_id = rule.id
    db.session.delete(rule)
    if project is not None:
        _write_audit(project, actor_id, "scan.exclusion.removed", rule_id)
    db.session.commit()


def replace_exclusion_rules(
    project: SecurityProject,
    actor_id: int,
    patterns: Sequence[str],
) -> list[ProjectExclusionRule]:
    """整体替换规则（gitignore 文件式编辑），空列表即清空。"""
    valid = compile_patterns(patterns)
    ProjectExclusionRule.query.filter_by(project_id=project.id).delete()
    rows = [
        ProjectExclusionRule(
            project_id=project.id,
            pattern=pattern,
            position=position,
            created_by=actor_id,
        )
        for position, pattern in enumerate(valid)
    ]
    db.session.add_all(rows)
    db.session.flush()
    _write_audit(project, actor_id, "scan.exclusion.replaced", 0)
    db.session.commit()
    return rows


def _next_position(project_id: int) -> int:
    current = (
        db.session.query(db.func.max(ProjectExclusionRule.position))
        .filter_by(project_id=project_id)
        .scalar()
    )
    return (current + 1) if current is not None else 0
