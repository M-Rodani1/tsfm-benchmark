def my_label_mask(n: int, origin_pos: int, h: int) -> np.ndarray:
    return np.arange(n) + h <= origin_pos
