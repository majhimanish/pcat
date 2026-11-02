def helper_total(items):
    total = 0
    for item in items:
        if item.price > 100:
            total += item.price * 2
    return total
