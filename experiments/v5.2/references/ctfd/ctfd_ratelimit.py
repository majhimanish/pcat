def ratelimit(method="POST", limit=50, interval=300, key_prefix="rl"):
    def ratelimit_decorator(f):
        @functools.wraps(f)
        def ratelimit_function(*args, **kwargs):
            ip_address = current_user.get_ip()
            key = "{}:{}:{}".format(key_prefix, ip_address, request.endpoint)
            current = cache.get(key)

            if request.method == method:
                if (
                    current and int(current) > limit - 1
                ):  # -1 in order to align expected limit with the real value
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

        return ratelimit_function

    return ratelimit_decorator
