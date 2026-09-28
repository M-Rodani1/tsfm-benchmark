def my_qlike(y, f):
    ratio = np.asarray(y) / np.asarray(f)
    return ratio - np.log(ratio) - 1
