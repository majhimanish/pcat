from flask import flash


def info_for(endpoint, message):
    flash(message=message, category=endpoint + ".infos")
