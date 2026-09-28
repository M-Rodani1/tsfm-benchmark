def my_delta(m_seen, ref_seen, m_clean, ref_clean):
    r_seen = np.sum(m_seen) / np.sum(ref_seen)
    r_clean = np.sum(m_clean) / np.sum(ref_clean)
    return np.log(r_clean) - np.log(r_seen)
