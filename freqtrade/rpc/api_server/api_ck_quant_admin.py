"""Authenticated CK Quant configuration and strategy management endpoints."""

import ast
import hashlib
import json
import logging
import os
import tempfile
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import rapidjson
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from freqtrade.configuration import validate_config_consistency
from freqtrade.configuration.load_config import CONFIG_PARSE_MODE
from freqtrade.constants import Config
from freqtrade.exceptions import ConfigurationError
from freqtrade.misc import deep_merge_dicts
from freqtrade.rpc.api_server.deps import get_config, get_rpc_optional
from freqtrade.rpc.rpc import RPC


logger = logging.getLogger(__name__)
router = APIRouter()

REDACTED = "__CKQ_REDACTED__"
SENSITIVE_PATHS = {
    "exchange.key",
    "exchange.api_key",
    "exchange.apiKey",
    "exchange.secret",
    "exchange.password",
    "exchange.uid",
    "exchange.account_id",
    "exchange.accountId",
    "exchange.wallet_address",
    "exchange.walletAddress",
    "exchange.private_key",
    "exchange.privateKey",
    "telegram.token",
    "telegram.chat_id",
    "discord.webhook_url",
    "api_server.password",
    "api_server.jwt_secret_key",
    "api_server.ws_token",
    "webhook.url",
}


class AdminCapabilities(BaseModel):
    enabled: bool
    config_edit: bool
    strategy_edit: bool
    apply_reload: bool
    audit_log: bool = True
    automatic_backups: bool = True


class EditableDocument(BaseModel):
    kind: Literal["config", "strategy"]
    name: str
    source: str
    revision: str
    redacted: bool = False
    updated_at: datetime


class SaveDocumentRequest(BaseModel):
    source: str = Field(min_length=1, max_length=2_000_000)
    revision: str = Field(min_length=64, max_length=64)
    apply: bool = True


class ValidationRequest(BaseModel):
    source: str = Field(min_length=1, max_length=2_000_000)


class ValidationResult(BaseModel):
    valid: bool
    message: str


class SaveDocumentResult(BaseModel):
    status: str
    revision: str
    backup_id: str
    reload_requested: bool


class BackupInfo(BaseModel):
    backup_id: str
    kind: Literal["config", "strategy"]
    created_at: datetime
    size: int


class RestoreBackupRequest(BaseModel):
    backup_id: str = Field(min_length=1, max_length=512, pattern=r"^[A-Za-z0-9_.-]+$")
    revision: str = Field(min_length=64, max_length=64)
    apply: bool = True


def _settings(config: Config) -> dict[str, Any]:
    return config.get("ck_quant_admin", {})


def _require_enabled(config: Config = Depends(get_config)) -> Config:
    if not _settings(config).get("enabled", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return config


def _require_permission(config: Config, permission: str) -> None:
    if not _settings(config).get(permission, False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission disabled")


def _user_data_dir(config: Config) -> Path:
    return Path(config["user_data_dir"]).resolve()


def _ensure_managed_file(path: Path, config: Config, subdirectory: str | None = None) -> Path:
    resolved = path.resolve()
    root = _user_data_dir(config)
    if subdirectory:
        root = (root / subdirectory).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file() or resolved.is_symlink():
        raise HTTPException(
            status_code=403, detail="File is outside the managed user-data directory"
        )
    return resolved


def _config_path(config: Config) -> Path:
    files = config.get("config_files", [])
    if not files:
        raise HTTPException(status_code=409, detail="No editable configuration file is active")
    return _ensure_managed_file(Path(files[0]), config)


def _strategy_path(config: Config, rpc: RPC | None) -> Path:
    if not rpc:
        raise HTTPException(status_code=409, detail="Strategy editing requires trading mode")
    path = getattr(rpc._freqtrade.strategy, "__file__", None)
    if not path:
        raise HTTPException(
            status_code=409, detail="The active strategy has no editable source file"
        )
    return _ensure_managed_file(Path(path), config, "strategies")


def _revision(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_config(source: str) -> dict[str, Any]:
    try:
        value = rapidjson.loads(source, parse_mode=CONFIG_PARSE_MODE)
    except rapidjson.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid JSON configuration: {exc}") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=422, detail="The configuration root must be an object")
    return value


def _path_value(value: dict[str, Any], dotted_path: str) -> Any:
    current: Any = value
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_path_value(value: dict[str, Any], dotted_path: str, replacement: Any) -> None:
    parts = dotted_path.split(".")
    current: Any = value
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if isinstance(current, dict) and parts[-1] in current:
        current[parts[-1]] = replacement


def _redact_config(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    for dotted_path in SENSITIVE_PATHS:
        if _path_value(result, dotted_path) is not None:
            _set_path_value(result, dotted_path, REDACTED)
    return result


def _restore_secrets(candidate: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    for dotted_path in SENSITIVE_PATHS:
        if _path_value(candidate, dotted_path) == REDACTED:
            original = _path_value(current, dotted_path)
            if original is not None:
                _set_path_value(candidate, dotted_path, original)
    return candidate


def _serialize_config(value: dict[str, Any]) -> str:
    return rapidjson.dumps(value, indent=4, ensure_ascii=False) + "\n"


def _validate_config(source: str, config: Config) -> str:
    candidate = _parse_config(source)
    current = _parse_config(_read(_config_path(config)))
    candidate = _restore_secrets(candidate, current)
    merged = deep_merge_dicts(candidate, deepcopy(config))
    try:
        validate_config_consistency(merged)
    except ConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _serialize_config(candidate)


def _validate_strategy(source: str, config: Config, rpc: RPC | None) -> str:
    path = _strategy_path(config, rpc)
    strategy_name = rpc._freqtrade.strategy.get_strategy_name() if rpc else path.stem
    try:
        tree = ast.parse(source, filename=path.name)
        compile(tree, path.name, "exec")
    except (SyntaxError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid Python strategy: {exc}") from exc
    classes = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    if strategy_name not in classes:
        raise HTTPException(
            status_code=422,
            detail=f"The active strategy class '{strategy_name}' must remain in the source",
        )
    return source if source.endswith("\n") else source + "\n"


def _backup_root(config: Config) -> Path:
    path = _user_data_dir(config) / "backups" / "ck_quant_admin"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _backup(path: Path, kind: str, config: Config) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    backup_id = f"{timestamp}-{kind}-{path.name}"
    backup_path = _backup_root(config) / backup_id
    backup_path.write_bytes(path.read_bytes())
    return backup_id


def _backup_path(config: Config, backup_id: str) -> Path:
    path = (_backup_root(config) / backup_id).resolve()
    if path.parent != _backup_root(config).resolve() or not path.is_file() or path.is_symlink():
        raise HTTPException(status_code=404, detail="Backup not found")
    return path


def _atomic_write(path: Path, source: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(source)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.chmod(path.stat().st_mode)
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _audit(config: Config, action: str, target: Path, details: dict[str, Any]) -> None:
    log_path = _user_data_dir(config) / "logs" / "ck_quant_admin_audit.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "action": action,
        "target": str(target.relative_to(_user_data_dir(config))),
        **details,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def _save(
    *,
    kind: Literal["config", "strategy"],
    path: Path,
    source: str,
    expected_revision: str,
    apply: bool,
    config: Config,
    rpc: RPC | None,
) -> SaveDocumentResult:
    if apply and not rpc:
        raise HTTPException(status_code=409, detail="Applying changes requires trading mode")
    current = _read(path)
    if _revision(current) != expected_revision:
        raise HTTPException(status_code=409, detail="The file changed after it was opened")
    validated = (
        _validate_config(source, config)
        if kind == "config"
        else _validate_strategy(source, config, rpc)
    )
    backup_id = _backup(path, kind, config)
    _atomic_write(path, validated)
    new_revision = _revision(validated)
    _audit(
        config,
        f"save_{kind}",
        path,
        {"backup_id": backup_id, "old_revision": expected_revision, "new_revision": new_revision},
    )
    reload_requested = False
    if apply and rpc:
        try:
            rpc._rpc_reload_config()
            reload_requested = True
        except Exception:
            logger.exception("Reload failed after saving %s; restoring backup %s", kind, backup_id)
            _atomic_write(path, _read(_backup_path(config, backup_id)))
            _audit(config, f"automatic_rollback_{kind}", path, {"backup_id": backup_id})
            try:
                rpc._rpc_reload_config()
            except Exception:
                logger.exception("Reload also failed after automatic rollback")
            raise HTTPException(
                status_code=409,
                detail="Reload failed; the previous file was restored automatically",
            )
    return SaveDocumentResult(
        status="saved",
        revision=new_revision,
        backup_id=backup_id,
        reload_requested=reload_requested,
    )


@router.get("/admin/capabilities", response_model=AdminCapabilities, tags=["CK Quant Admin"])
def capabilities(config: Config = Depends(_require_enabled)):
    settings = _settings(config)
    return {
        "enabled": True,
        "config_edit": settings.get("config_edit", False),
        "strategy_edit": settings.get("strategy_edit", False),
        "apply_reload": True,
    }


@router.get("/admin/config", response_model=EditableDocument, tags=["CK Quant Admin"])
def get_admin_config(config: Config = Depends(_require_enabled)):
    _require_permission(config, "config_edit")
    path = _config_path(config)
    source = _read(path)
    redacted_source = _serialize_config(_redact_config(_parse_config(source)))
    return EditableDocument(
        kind="config",
        name=path.name,
        source=redacted_source,
        revision=_revision(source),
        redacted=True,
        updated_at=datetime.fromtimestamp(path.stat().st_mtime, UTC),
    )


@router.post("/admin/config/validate", response_model=ValidationResult, tags=["CK Quant Admin"])
def validate_admin_config(payload: ValidationRequest, config: Config = Depends(_require_enabled)):
    _require_permission(config, "config_edit")
    _validate_config(payload.source, config)
    return {"valid": True, "message": "Configuration is valid"}


@router.put("/admin/config", response_model=SaveDocumentResult, tags=["CK Quant Admin"])
def save_admin_config(
    payload: SaveDocumentRequest,
    config: Config = Depends(_require_enabled),
    rpc: RPC | None = Depends(get_rpc_optional),
):
    _require_permission(config, "config_edit")
    return _save(
        kind="config",
        path=_config_path(config),
        source=payload.source,
        expected_revision=payload.revision,
        apply=payload.apply,
        config=config,
        rpc=rpc,
    )


@router.get("/admin/strategy", response_model=EditableDocument, tags=["CK Quant Admin"])
def get_admin_strategy(
    config: Config = Depends(_require_enabled),
    rpc: RPC | None = Depends(get_rpc_optional),
):
    _require_permission(config, "strategy_edit")
    path = _strategy_path(config, rpc)
    source = _read(path)
    return EditableDocument(
        kind="strategy",
        name=path.name,
        source=source,
        revision=_revision(source),
        updated_at=datetime.fromtimestamp(path.stat().st_mtime, UTC),
    )


@router.post("/admin/strategy/validate", response_model=ValidationResult, tags=["CK Quant Admin"])
def validate_admin_strategy(
    payload: ValidationRequest,
    config: Config = Depends(_require_enabled),
    rpc: RPC | None = Depends(get_rpc_optional),
):
    _require_permission(config, "strategy_edit")
    _validate_strategy(payload.source, config, rpc)
    return {"valid": True, "message": "Strategy source is valid"}


@router.put("/admin/strategy", response_model=SaveDocumentResult, tags=["CK Quant Admin"])
def save_admin_strategy(
    payload: SaveDocumentRequest,
    config: Config = Depends(_require_enabled),
    rpc: RPC | None = Depends(get_rpc_optional),
):
    _require_permission(config, "strategy_edit")
    return _save(
        kind="strategy",
        path=_strategy_path(config, rpc),
        source=payload.source,
        expected_revision=payload.revision,
        apply=payload.apply,
        config=config,
        rpc=rpc,
    )


@router.get("/admin/backups", response_model=list[BackupInfo], tags=["CK Quant Admin"])
def list_admin_backups(config: Config = Depends(_require_enabled)):
    backups: list[BackupInfo] = []
    for path in sorted(
        _backup_root(config).iterdir(), key=lambda item: item.stat().st_mtime, reverse=True
    ):
        if not path.is_file() or path.is_symlink():
            continue
        kind: Literal["config", "strategy"] | None = None
        if "-config-" in path.name:
            kind = "config"
        elif "-strategy-" in path.name:
            kind = "strategy"
        if kind:
            backups.append(
                BackupInfo(
                    backup_id=path.name,
                    kind=kind,
                    created_at=datetime.fromtimestamp(path.stat().st_mtime, UTC),
                    size=path.stat().st_size,
                )
            )
    return backups[:50]


@router.post("/admin/{kind}/restore", response_model=SaveDocumentResult, tags=["CK Quant Admin"])
def restore_admin_backup(
    kind: Literal["config", "strategy"],
    payload: RestoreBackupRequest,
    config: Config = Depends(_require_enabled),
    rpc: RPC | None = Depends(get_rpc_optional),
):
    _require_permission(config, f"{kind}_edit")
    marker = f"-{kind}-"
    if marker not in payload.backup_id:
        raise HTTPException(status_code=422, detail="Backup type does not match the target")
    backup_source = _read(_backup_path(config, payload.backup_id))
    path = _config_path(config) if kind == "config" else _strategy_path(config, rpc)
    result = _save(
        kind=kind,
        path=path,
        source=backup_source,
        expected_revision=payload.revision,
        apply=payload.apply,
        config=config,
        rpc=rpc,
    )
    _audit(
        config,
        f"restore_{kind}",
        path,
        {"source_backup_id": payload.backup_id, "safety_backup_id": result.backup_id},
    )
    return result
