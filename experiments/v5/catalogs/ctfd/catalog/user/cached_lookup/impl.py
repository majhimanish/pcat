from CTFd.cache import cache
from CTFd.models import Teams


@cache.memoize(timeout=300)
def get_team_place(team_id):
    team = Teams.query.filter_by(id=team_id).first()
    if team:
        return team.place
    return None
