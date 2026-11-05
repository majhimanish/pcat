def throttle(method="POST", limit=10, interval=60, key_prefix="th"):
    def throttle_decorator(f):
        @functools.wraps(f)
        def throttle_function(*args, **kwargs):
            key = "{}:{}:{}".format(key_prefix, request.remote_addr, request.endpoint)
            current = cache.get(key)

            if request.method == method:
                if current and int(current) > limit - 1:
                    resp = jsonify(
                        {
                            "code": 429,
                            "message": "Too many requests. Limit is %s requests in %s seconds"
                            % (limit, interval),
                        }
                    )
                    resp.status_code = 429
                    return resp
                else:
                    if current is None:
                        cache.set(key, 1, timeout=interval)
                    else:
                        cache.set(key, int(current) + 1, timeout=interval)
            return f(*args, **kwargs)

        return throttle_function

    return throttle_decorator
