def total_cost(lines):
    # renamed copy of orders.total_price with comments
    s = 0
    for ln in lines:  # every line
        if ln.price > 100:
            s += ln.price * 2
    return s
