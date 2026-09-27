def my_lognormal_mean(median, q10, q90):
    s = (q90 - q10) / (2 * 1.2815515655446004)
    return np.exp(median + s**2 / 2)
