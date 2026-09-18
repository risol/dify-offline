"""Install configured default plugins for a newly created tenant."""

import logging
from pathlib import Path

from celery import shared_task

from configs import dify_config
from core.helper import marketplace
from core.plugin.entities.plugin_daemon import PluginInstallTaskStatus
from core.plugin.plugin_service import PluginService
from services.model_provider_service import ModelProviderService

logger = logging.getLogger(__name__)


@shared_task(queue="plugin", bind=True, max_retries=60, default_retry_delay=5)
def configure_default_models_task(self, tenant_id: str, plugin_install_task_id: str | None) -> None:
    """Set explicitly configured default models after default plugins finish installing."""
    if not dify_config.NEW_USER_DEFAULT_MODELS:
        return

    plugin_install_failed = False
    if plugin_install_task_id:
        try:
            install_task = PluginService.fetch_install_task(tenant_id, plugin_install_task_id)
        except Exception as exc:
            logger.warning(
                "Failed to fetch default plugin installation task for tenant %s; retrying",
                tenant_id,
            )
            raise self.retry(exc=exc)

        if install_task.status in (PluginInstallTaskStatus.Pending, PluginInstallTaskStatus.Running):
            raise self.retry()

        plugin_install_failed = install_task.status == PluginInstallTaskStatus.Failed
        if plugin_install_failed:
            failed_plugin_ids = [
                plugin.plugin_id for plugin in install_task.plugins if plugin.status == PluginInstallTaskStatus.Failed
            ]
            logger.error(
                "Default plugin installation failed for tenant %s: %s",
                tenant_id,
                ", ".join(failed_plugin_ids),
            )

    model_provider_service = ModelProviderService()
    failed_model_types: list[str] = []
    for model_type, provider, model in dify_config.NEW_USER_DEFAULT_MODEL_LIST:
        try:
            model_provider_service.update_default_model_of_model_type(
                tenant_id=tenant_id,
                model_type=model_type,
                provider=provider,
                model=model,
            )
        except Exception:
            failed_model_types.append(model_type)
            logger.exception(
                "Failed to configure default model for tenant %s: model_type=%s provider=%s model=%s",
                tenant_id,
                model_type,
                provider,
                model,
            )

    if plugin_install_failed or failed_model_types:
        raise RuntimeError(
            f"Failed to initialize defaults for tenant {tenant_id}; "
            f"model types: {', '.join(failed_model_types) or 'none'}"
        )


def _local_package_name(plugin_id: str) -> str:
    return plugin_id.replace("/", "__") + ".difypkg"


def _install_from_offline_packages(tenant_id: str, plugin_ids: list[str]):
    package_dir = Path(dify_config.OFFLINE_PLUGIN_PACKAGE_DIR)
    if not package_dir.is_dir():
        raise RuntimeError(f"Offline plugin package directory does not exist: {package_dir}")

    identifiers: list[str] = []
    missing: list[str] = []
    for plugin_id in plugin_ids:
        package_path = package_dir / _local_package_name(plugin_id)
        if not package_path.is_file():
            missing.append(plugin_id)
            continue

        decoded = PluginService.upload_pkg(tenant_id, package_path.read_bytes())
        identifiers.append(decoded.unique_identifier)

    if missing:
        raise RuntimeError(
            "Missing offline plugin package(s): "
            + ", ".join(missing)
            + f". Expected them under {package_dir}."
        )

    if not identifiers:
        return None

    logger.info("Installing default plugins from offline packages for tenant %s: %s", tenant_id, ", ".join(plugin_ids))
    return PluginService.install_from_local_pkg(tenant_id, identifiers)


@shared_task(queue="plugin")
def install_default_plugins_task(tenant_id: str, plugin_ids: list[str]) -> None:
    """Install configured plugins without public-network access when OFFLINE_MODE is enabled."""
    if not plugin_ids:
        return

    try:
        if dify_config.OFFLINE_MODE:
            response = _install_from_offline_packages(tenant_id, plugin_ids)
        else:
            if not dify_config.MARKETPLACE_ENABLED:
                raise RuntimeError("Marketplace is disabled and OFFLINE_MODE is not enabled")
            manifests = {
                manifest.plugin_id: manifest for manifest in marketplace.batch_fetch_plugin_manifests(plugin_ids)
            }
            plugin_identifiers = [
                manifests[plugin_id].latest_package_identifier for plugin_id in plugin_ids if plugin_id in manifests
            ]
            missing_plugin_ids = [plugin_id for plugin_id in plugin_ids if plugin_id not in manifests]
            if missing_plugin_ids:
                logger.warning("Default plugins not found in marketplace: %s", ", ".join(missing_plugin_ids))
            if not plugin_identifiers:
                return
            response = PluginService.install_from_marketplace_pkg(tenant_id, plugin_identifiers)

        if response is not None and dify_config.NEW_USER_DEFAULT_MODELS:
            configure_default_models_task.delay(
                tenant_id,
                None if response.all_installed else response.task_id,
            )
    except Exception:
        logger.exception("Failed to install default plugins for tenant %s", tenant_id)
        raise
