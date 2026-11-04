def get_ip(req=None):
    """Returns the IP address of the currently in scope request. The approach is to define a list of trusted proxies
    (in this case the local network), and only trust the most recently defined untrusted IP address.
    Taken from http://stackoverflow.com/a/22936947/4285524 but the generator there makes no sense.
    The trusted_proxies regexes is taken from Ruby on Rails.

    This has issues if the clients are also on the local network so you can remove proxies from config.py.

    CTFd does not use IP address for anything besides cursory tracking of teams and it is ill-advised to do much
    more than that if you do not know what you're doing.
    """
    if req is None:
        req = request
    trusted_proxies = app.config["TRUSTED_PROXIES"]
    combined = "(" + ")|(".join(trusted_proxies) + ")"
    route = req.access_route + [req.remote_addr]
    for addr in reversed(route):
        if not re.match(combined, addr):  # IP is not trusted but we trust the proxies
            remote_addr = addr
            break
    else:
        remote_addr = req.remote_addr
    return remote_addr
