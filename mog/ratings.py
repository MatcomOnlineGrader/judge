"""
This file contains the functions for computing the new rating of the users after a rated-contest
The formulas are taken from https://codeforces.com/blog/entry/20762
"""

from math import sqrt

from judge import settings
from api.models import RatingChange
from api.lib.queries import calculate_standing


def win_probability(rating1, rating2):
    """
    Computes the probability that a user with rating1 will have better performance
    than a user with rating2
    """
    return 1 / (1 + 10 ** ((rating2 - rating1) / 400.0))


def get_seed(other_ratings, actual_rating):
    """
    Computes the seed (expected rank) of a user with rating: actual_rating
    """
    # the best possible expected rank is 1
    # if the ranks of the other users are very low compared to actual rank
    # result will be close to 1 at the end because the winning probabilities
    # of th other users are close to 0
    result = 1.0
    for rating in other_ratings:
        # if rating of other user is >> actual_rating the probability will be >> 0.5
        # this will increase the expected rank by almost 1
        result += win_probability(rating, actual_rating)

    return result


def get_rating_for_rank(other_ratings, rank):
    """
    Computes a rating such that computing the seed (expected rank) yields the actual
    rank of the user
    """
    left = 1
    right = settings.MAX_RATING

    while right - left > 1:
        mid = (left + right) // 2
        if get_seed(other_ratings, mid) < rank:
            right = mid
        else:
            left = mid
    return left


def reassign_ranks(ranks):
    """
    When some users are tied with other users, assigns the average of the
    positions covered by the tied users
    """
    cur = 0
    num_coders = len(ranks)
    new_ranks = []

    while cur < num_coders:
        cnt = 0
        while cur + cnt < num_coders and ranks[cur + cnt] == ranks[cur]:
            cnt += 1
        rank = ranks[cur] + cnt - 1
        new_ranks += [rank] * cnt
        cur += cnt

    return new_ranks


def check_rating_deltas(ranks, ratings, deltas):
    """
    Checks (independently of the rating method used) if the rating deltas are consistent, which means that the
    following conditions must me satisfied:

    a) if the participant j had worse rating than the participant i before the contest and finished the contest
    on a worse place, then the new rating of j can’t be greater than the new rating of i

    b) if i finished the contest better than j but i had worse rating before the contest then i should have equal
    or greater rating change than j.

    c) a user whose rank in the contest is the last place cannot increase rating

    d) the new rating should be between 1 and MAX_RATING-1

    :param ranks: Ranks of the users in the contest (must be non-decreasing)
    :param ratings: Current ratings of the users (order must match the corresponding ranks)
    :param deltas: Computed deltas (rating-changes)
    :return: True if the deltas are consistent, False in other case
    """
    for i in range(len(ranks)):
        for j in range(i + 1, len(ranks)):
            # Check condition a)
            if ratings[i] >= ratings[j]:
                if ratings[i] + deltas[i] < ratings[j] + deltas[j]:
                    return False

            # Check condition b)
            if ratings[i] <= ratings[j]:
                if deltas[i] < deltas[j]:
                    return False

        # Check condition c)
        # after calling reassign_ranks the users tied in the last place have rank=len(ranks)
        if ranks[i] == len(ranks) and deltas[i] > 0:
            return False

        # Check condition d)
        if ratings[i] + deltas[i] < 1 or ratings[i] + deltas[i] >= settings.MAX_RATING:
            return False

    return True


def get_rating_deltas(ranks, ratings):
    """
    Gets the deltas for updating the ratings of the users after a contests
    :param ranks: Ranks of the users in the contest (must be non-decreasing)
    :param ratings: Current ratings of the users (order must match the corresponding ranks)
    :return: Rating-changes of the users (given in the same order as the input)
    """
    num_coders = len(ranks)

    # 1) Reassign ranks
    ranks = reassign_ranks(ranks)

    # 2) Compute seeds
    seeds = []
    for i in range(num_coders):
        other_ratings = ratings[:i] + ratings[i + 1 :]
        seeds.append(get_seed(other_ratings, ratings[i]))

    # 3) Compute deltas
    deltas = []
    for i in range(num_coders):
        other_ratings = ratings[:i] + ratings[i + 1 :]
        # take geometric mean of expected and actual ranks
        # this is similar to (a+b)/2 but when there is a big difference between a and b
        # it is closer to a (this protects users with high ratings from loosing too much rating)
        mean_rank = sqrt(seeds[i] * ranks[i])
        # compute the rating that correspond to mean_rank
        performed_rating = get_rating_for_rank(other_ratings, mean_rank)
        # we want the rating of the user to be closer to the performed rating
        # the new rating will be the midpoint between the actual ranking and the performed rating
        deltas.append((performed_rating - ratings[i]) // 2)

    return deltas, seeds


def set_ratings(contest):
    """
    Rates a contest. If everything goes well, adds to the database the RatingChanges that correspond to the
    new rating results
    :param contest: Contest to be rated
    :return: True if the rating was applied. False if after computing the new rating some of the checks failed
    """
    # remove previous rating changes
    contest.rating_changes.all().delete()

    _, instance_results = calculate_standing(contest)

    # only instances with some submissions (other than Compilation Error or Internal Error)
    instance_results = [
        result for result in instance_results if result.submissions_count > 0
    ]

    ratings, ranks = [], []
    for ir in instance_results:
        profile = ir.instance.user.profile
        if profile.has_rating:
            ratings.append(profile.rating)
        else:
            ratings.append(settings.BASE_RATING)
        ranks.append(ir.rank)

    deltas, seeds = get_rating_deltas(ranks, ratings)

    # if some of the necessary conditions for the new ratings are not satisfied do not apply the
    # rating and return False
    if not check_rating_deltas(ranks, ratings, deltas):
        return False

    # make the rating persistent
    for i, result in enumerate(instance_results):
        RatingChange.objects.create(
            profile=result.instance.user.profile,
            contest=contest,
            rating=deltas[i],
            rank=result.rank,
            seed=seeds[i],
        )

    contest.rated = True
    contest.save()

    return True
