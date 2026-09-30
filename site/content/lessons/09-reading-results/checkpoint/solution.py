def verdict(mean_diff, p_holm, alpha=0.05):
    if p_holm <= alpha:
        return "model better" if mean_diff < 0 else "model worse"
    return "no detectable difference"
