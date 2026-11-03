# -*- coding: utf-8 -*-
"""Логирование Codegen Studio."""
import logging
import os
from logging.handlers import RotatingFileHandler

_LOGGER = "studio"
_INIT = False


def setup(project_path, level=logging.DEBUG):
    global _INIT
    log = logging.getLogger(_LOGGER)
    if _INIT:
        return log
    log_dir = os.path.join(project_path, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log.setLevel(level)
    log.propagate = False
    for h in list(log.handlers):
        log.removeHandler(h)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    app = RotatingFileHandler(
        os.path.join(log_dir, "studio_app.log"),
        maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    app.setFormatter(fmt); app.setLevel(logging.DEBUG); log.addHandler(app)
    err = RotatingFileHandler(
        os.path.join(log_dir, "studio_errors.log"),
        maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    err.setFormatter(fmt); err.setLevel(logging.WARNING); log.addHandler(err)
    _INIT = True
    log.info("Логирование Studio инициализировано: %s", log_dir)
    return log


def get_logger(name=None):
    log = logging.getLogger(_LOGGER)
    if not log.handlers:
        log.addHandler(logging.NullHandler())
    return logging.getLogger(f"{_LOGGER}.{name}" if name else _LOGGER)


def log_failure(kind, msg):
    """Пишет неудачную операцию в errors.log (уровень ERROR) и в app.log."""
    log = get_logger("errors")
    log.error("[%s] %s", kind, msg)
