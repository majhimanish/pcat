import math
from CTFd.models import Solves
from CTFd.utils.modes import get_model


def get_solve_count(challenge):
    Model = get_model()

    solve_count = (
        Solves.query.join(Model, Solves.account_id == Model.id)
        .filter(
            Solves.challenge_id == challenge.id,
            Model.hidden == False,
            Model.banned == False,
        )
        .count()
    )
    return solve_count


def linear(challenge):
    solve_count = get_solve_count(challenge)

    # If the solve count is 0 we shouldn't manipulate the solve count to
    # let the math update back to normal
    if solve_count != 0:
        # We subtract -1 to allow the first solver to get max point value
        solve_count -= 1

    value = challenge.initial - (challenge.decay * solve_count)

    value = math.ceil(value)

    if value < challenge.minimum:
        value = challenge.minimum

    return value
