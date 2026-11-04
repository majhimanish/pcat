@cache.memoize(timeout=300)
def get_team_score(team_id):
    team = Teams.query.filter_by(id=team_id).first()
    if team:
        return team.score
    return None
