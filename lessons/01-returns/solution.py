def my_h_step_return(prices: np.ndarray, i: int, h: int) -> float:
    return 100 * np.log(prices[i + h] / prices[i])
