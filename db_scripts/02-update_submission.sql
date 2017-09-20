DROP FUNCTION IF EXISTS PUBLIC.update_submission(INTEGER);

CREATE OR REPLACE FUNCTION PUBLIC.update_submission()
  RETURNS TRIGGER
  LANGUAGE 'plpgsql'
  COST 100.0
  VOLATILE NOT LEAKPROOF
AS $BODY$

DECLARE
  row RECORD;
  user_points INTEGER;
BEGIN
  -- update problem points
  UPDATE api_problem SET points = (SELECT compute_problem_points(api_problem.id)) WHERE api_problem.id = NEW.problem_id;
  -- update user points
  FOR row IN (SELECT DISTINCT (user_id) FROM api_submission WHERE (hidden = FALSE) AND (problem_id = NEW.problem_id)) LOOP
    UPDATE api_userprofile SET points = (SELECT compute_user_points(row.user_id)) WHERE api_userprofile.user_id = row.user_id;
  END LOOP;
  RETURN NEW;
END;

$BODY$;

ALTER FUNCTION public.update_submission()
    OWNER TO postgres;
