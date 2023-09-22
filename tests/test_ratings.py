from django.test import TestCase

from mog.ratings import (
    reassign_ranks,
    win_probability,
    get_seed,
    get_rating_for_rank,
    get_rating_deltas,
    check_rating_deltas,
)


class RatingsTestCase(TestCase):
    def setUp(self):
        super(RatingsTestCase, self).setUp()

    def test_reassign_ranks(self):
        ranks = [1, 1, 3, 3, 3, 6, 6, 6, 6, 10, 10, 10, 10, 10, 10]
        correct_ranks = [2, 2, 5, 5, 5, 9, 9, 9, 9, 15, 15, 15, 15, 15, 15]
        new_ranks = reassign_ranks(ranks)
        for i in range(len(ranks)):
            self.assertTrue(new_ranks[i] == correct_ranks[i])

    def test_win_probability(self):
        rating1 = 2000
        rating2 = 1500

        self.assertTrue(0 <= win_probability(rating1, rating2) <= 1)
        self.assertTrue(win_probability(rating1, rating2) > 0.5)
        self.assertTrue(win_probability(rating2, rating1) < 0.5)

    def test_win_close_probability(self):
        rating1 = 1502
        rating2 = 1500

        self.assertTrue(0 <= win_probability(rating1, rating2) <= 1)
        self.assertTrue(0.55 > win_probability(rating1, rating2) > 0.5)
        self.assertTrue(0.45 < win_probability(rating2, rating1) < 0.5)

    def test_seed(self):
        ratings = [2000, 1900, 1500, 1000]
        seeds = []
        for i in range(len(ratings)):
            other_ratings = ratings[:i] + ratings[i + 1 :]
            seeds.append(get_seed(other_ratings, ratings[i]))

        for i in range(len(ratings)):
            self.assertTrue(1 <= seeds[i] <= len(ratings))
            if i > 0:
                self.assertTrue(seeds[i - 1] < seeds[i])

    def test_rating_for_rank(self):
        ratings = [1500, 1900, 2000, 1850, 1200, 1350, 1000]
        for i in range(len(ratings)):
            rank = i + 1
            other_ratings = ratings[:i] + ratings[i + 1 :]
            performed_rating = get_rating_for_rank(other_ratings, rank=rank)
            seed = get_seed(other_ratings, performed_rating)
            self.assertTrue(rank - 1e-2 <= seed <= rank + 1e-2)

    def test_rating_deltas(self):
        ratings = [1550, 1500, 1900, 2000, 1850, 1200, 1350, 1000]
        ranks = list(range(1, len(ratings) + 1))
        deltas, _ = get_rating_deltas(ranks, ratings)
        self.assertTrue(check_rating_deltas(ranks, ratings, deltas))

    def test_high_rating(self):
        ratings = [7999, 7998, 7999, 2000, 1850, 1200, 1350, 1000]
        ranks = list(range(1, len(ratings) + 1))
        deltas, _ = get_rating_deltas(ranks, ratings)
        self.assertTrue(deltas[0] == 0)
        self.assertTrue(check_rating_deltas(ranks, ratings, deltas))

    def test_low_rating(self):
        ratings = [7999, 1500, 1900, 2000, 1850, 1200, 1350, 1]
        ranks = list(range(1, len(ratings) + 1))
        deltas, _ = get_rating_deltas(ranks, ratings)
        self.assertTrue(deltas[-1] == 0)
        self.assertTrue(check_rating_deltas(ranks, ratings, deltas))
