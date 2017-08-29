DO
$DO$
DECLARE
    user_profile RECORD;
    user_points INTEGER;
BEGIN
  FOR user_profile IN (SELECT * FROM api_userprofile) LOOP
    SELECT coalesce(SUM(points), 0) INTO user_points FROM (
      SELECT DISTINCT(api_problem.id), api_problem.points
      FROM api_problem JOIN api_submission ON (api_problem.id = api_submission.problem_id)
      WHERE (api_submission.hidden = FALSE) AND
            (api_submission.result_id = 1) AND
            (api_submission.user_id = user_profile.user_id)
    ) AS solved_problems;
    UPDATE api_userprofile SET points = user_points WHERE user_id = user_profile.user_id;
  END LOOP;
END
$DO$;
