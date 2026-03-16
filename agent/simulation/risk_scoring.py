def compute_risk(impact):

    size = len(impact)

    if size == 0:
        return 1

    if size < 2:
        return 4

    if size < 4:
        return 7

    return 9