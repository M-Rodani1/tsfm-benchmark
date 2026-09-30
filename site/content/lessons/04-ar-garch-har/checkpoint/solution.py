def my_garch_path(eps, omega, alpha, beta, s0):
    s = np.empty(len(eps))
    s[0] = s0
    for t in range(1, len(eps)):
        s[t] = omega + alpha * eps[t - 1] ** 2 + beta * s[t - 1]
    return s
