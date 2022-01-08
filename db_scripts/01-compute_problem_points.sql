DROP FUNCTION IF EXISTS PUBLIC.compute_problem_points(INTEGER);

CREATE OR REPLACE FUNCTION PUBLIC.compute_problem_points(in_problem_id INTEGER)
  RETURNS INTEGER
  LANGUAGE 'plpgsql'
  COST 100.0
  VOLATILE
AS $function$

DECLARE
    solved INTEGER;
BEGIN
  -- select the number of users that have at least one
  -- accepted, normal & visible submission and call this
  -- number @solved.
  -- @points = 108 / (12 + @solved) + 1
  SELECT COUNT(DISTINCT api_submission.user_id)
  INTO solved
  FROM api_submission
  WHERE (api_submission.problem_id = in_problem_id) AND
        (api_submission.result_id = 1) AND
        (api_submission.status = 'normal') AND
        (api_submission.hidden = FALSE);
  RETURN 108 / (12 + solved) + 1;
END;

$function$;

ALTER FUNCTION PUBLIC.compute_problem_points(INTEGER)
    OWNER TO ${USERNAME};
