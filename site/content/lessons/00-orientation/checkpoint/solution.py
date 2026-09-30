def n_primary_tests(cfg):
    return len(cfg.models.tsfms) * len(cfg.targets.kinds) * len(cfg.targets.horizons)
