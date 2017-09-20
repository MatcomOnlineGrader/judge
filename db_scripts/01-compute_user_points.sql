DROP FUNCTION IF EXISTS PUBLIC.compute_user_points(INTEGER);

CREATE OR REPLACE FUNCTION PUBLIC.compute_user_points(in_user_id INTEGER)
  RETURNS INTEGER
  LANGUAGE 'plpgsql'
  COST 100.0
  VOLATILE
AS $function$

DECLARE
    user_points INTEGER;
BEGIN
  SELECT COALESCE(SUM(points), 0) INTO user_points FROM (
    SELECT DISTINCT(api_problem.id), api_problem.points
    FROM api_problem JOIN api_submission ON (api_problem.id = api_submission.problem_id)
    WHERE (api_submission.hidden = FALSE) AND
          (api_submission.result_id = 1) AND
          (api_submission.user_id = in_user_id)
  ) AS solved_problems;
  RETURN user_points;
END;

$function$;

ALTER FUNCTION PUBLIC.compute_user_points(INTEGER)
    OWNER TO postgres;
