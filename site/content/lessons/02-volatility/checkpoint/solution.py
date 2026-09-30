def my_garman_klass(o, h, l, c):
    return 1e4 * (0.5 * np.log(h / l) ** 2 - (2 * np.log(2) - 1) * np.log(c / o) ** 2)
