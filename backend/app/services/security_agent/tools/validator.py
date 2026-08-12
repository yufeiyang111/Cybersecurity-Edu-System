# -*- coding: utf-8 -*-
"""工具输入校验器（T05，spec §10.2）：JSON Schema 子集的本地确定性实现。

支持 type / properties / required / additionalProperties / items /
minimum / maximum / minLength / maxLength / enum / minItems / maxItems，
不新增依赖；路径字段做穿越检查。非法输入在 Handler 前拒绝。
"""
from __future__ import annotations

import re
from typing import Any

_INTEGER_TYPES = (int,)
_NUMBER_TYPES = (int, float)
_STRING_TYPES = (str,)
_BOOLEAN_TYPES = (bool,)

_MAX_DEPTH = 8
_MAX_STRING_LENGTH = 10000

# 路径穿越/绝对路径特征：../、..\、盘符、/ 开头、\ 开头
_PATH_TRAVERSAL = re.compile(r"(?:^|[\\/])\.\.[\\/]|^[A-Za-z]:[\\/]|^[\\/]")
_PATH_LIKE_FIELDS = ("file_path", "path", "directory", "artifact_path")


class InputValidationError(ValueError):
    """工具输入未通过 schema 校验。"""


def validate_input(schema: dict, data: dict, *, depth: int = 0) -> None:
    """校验 data 符合 schema；非法抛 InputValidationError。"""
    if depth > _MAX_DEPTH:
        raise InputValidationError("输入嵌套深度超过上限")
    if not isinstance(data, dict):
        raise InputValidationError("输入必须是对象")
    _validate_object(schema, data, depth=depth)
    _check_path_fields(schema, data)


def _validate_object(schema: dict, data: dict, *, depth: int) -> None:
    if not isinstance(schema, dict) or schema.get("type") != "object":
        return
    properties = schema.get("properties")
    properties = properties if isinstance(properties, dict) else {}
    required = schema.get("required") or []
    required = required if isinstance(required, list) else []

    for name in required:
        if name not in data:
            raise InputValidationError(f"缺少必填字段：{name}")

    if schema.get("additionalProperties") is False:
        unknown = set(data) - set(properties)
        if unknown:
            raise InputValidationError(
                f"包含未知字段：{', '.join(sorted(unknown))}"
            )

    for name, value in data.items():
        prop_schema = properties.get(name)
        if prop_schema is None:
            if schema.get("additionalProperties") is False:
                raise InputValidationError(f"包含未知字段：{name}")
            continue
        _validate_value(prop_schema, value, name, depth=depth + 1)


def _validate_value(schema: dict, value: Any, name: str, *, depth: int) -> None:
    if depth > _MAX_DEPTH:
        raise InputValidationError(f"字段 {name} 嵌套深度超过上限")
    if not isinstance(schema, dict):
        return
    value_type = schema.get("type")

    if value_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise InputValidationError(f"{name} 必须是整数")
        _check_bounds(schema, value, name)
    elif value_type == "number":
        if not isinstance(value, _NUMBER_TYPES) or isinstance(value, bool):
            raise InputValidationError(f"{name} 必须是数字")
        _check_bounds(schema, value, name)
    elif value_type == "string":
        if not isinstance(value, str):
            raise InputValidationError(f"{name} 必须是字符串")
        if len(value) > _MAX_STRING_LENGTH:
            raise InputValidationError(f"{name} 超过最大长度 {_MAX_STRING_LENGTH}")
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise InputValidationError(
                f"{name} 长度不能小于 {schema['minLength']}"
            )
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise InputValidationError(
                f"{name} 长度不能超过 {schema['maxLength']}"
            )
        if "enum" in schema and value not in schema["enum"]:
            raise InputValidationError(f"{name} 不在允许取值范围内")
    elif value_type == "boolean":
        if not isinstance(value, bool):
            raise InputValidationError(f"{name} 必须是布尔值")
    elif value_type == "array":
        if not isinstance(value, list):
            raise InputValidationError(f"{name} 必须是数组")
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise InputValidationError(f"{name} 至少需要 {schema['minItems']} 项")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise InputValidationError(f"{name} 最多允许 {schema['maxItems']} 项")
        items_schema = schema.get("items")
        if isinstance(items_schema, dict):
            for index, item in enumerate(value):
                _validate_value(
                    items_schema, item, f"{name}[{index}]", depth=depth + 1
                )
    elif value_type == "object":
        if not isinstance(value, dict):
            raise InputValidationError(f"{name} 必须是对象")
        _validate_object(schema, value, depth=depth)
    else:
        # 未声明 type：仅当提供 enum 时校验
        if "enum" in schema and value not in schema["enum"]:
            raise InputValidationError(f"{name} 不在允许取值范围内")


def _check_bounds(schema: dict, value: Any, name: str) -> None:
    if "minimum" in schema and value < schema["minimum"]:
        raise InputValidationError(f"{name} 不能小于 {schema['minimum']}")
    if "maximum" in schema and value > schema["maximum"]:
        raise InputValidationError(f"{name} 不能大于 {schema['maximum']}")


def _check_path_fields(schema: dict, data: dict) -> None:
    properties = schema.get("properties")
    properties = properties if isinstance(properties, dict) else {}
    for name, value in data.items():
        prop_schema = properties.get(name)
        if not isinstance(prop_schema, dict):
            continue
        if prop_schema.get("type") == "string" and name in _PATH_LIKE_FIELDS:
            if isinstance(value, str) and _PATH_TRAVERSAL.search(value):
                raise InputValidationError(f"{name} 包含路径穿越或绝对路径")
        if prop_schema.get("type") == "array":
            items_schema = prop_schema.get("items")
            if (
                isinstance(items_schema, dict)
                and name in _PATH_LIKE_FIELDS
                and isinstance(value, list)
            ):
                for item in value:
                    if (
                        isinstance(item, str)
                        and _PATH_TRAVERSAL.search(item)
                    ):
                        raise InputValidationError(
                            f"{name} 包含路径穿越或绝对路径"
                        )
