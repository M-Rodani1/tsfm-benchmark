def my_sentence(r):
    if r.reject_holm:
        verdict = "model better" if r.mean_diff < 0 else "model worse"
    else:
        verdict = "no detectable difference"
    return (f"{r.model} vs {r.reference} ({r.target}, h={r.horizon}): relative loss "
            f"{ci(r.rel_loss, r.rel_loss_lo, r.rel_loss_hi)}, Holm p = {fp(r.p_holm)}: {verdict}.")
