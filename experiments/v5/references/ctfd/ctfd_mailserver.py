def mailserver():
    if app.config.get("MAIL_SERVER") and app.config.get("MAIL_PORT"):
        return True
    if get_config("mail_server") and get_config("mail_port"):
        return True
    return False
