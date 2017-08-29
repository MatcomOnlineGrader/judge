CREATE OR REPLACE FUNCTION public.updatesubmission()
    RETURNS trigger
    LANGUAGE 'plpgsql'
    COST 100.0
    VOLATILE NOT LEAKPROOF 
AS $BODY$
DECLARE
  row record;
  old_value INTEGER ;
  new_value INTEGER ;
BEGIN
  IF NEW.result_id IS DISTINCT FROM OLD.result_id THEN
    SELECT points INTO old_value FROM api_problem WHERE NEW.problem_id = id;
    SELECT ComputeProblemPoints(NEW.problem_id) INTO new_value FROM api_problem WHERE NEW.problem_id = id;

    FOR row IN (SELECT DISTINCT (user_id) FROM api_submission WHERE (hidden = FALSE) AND (problem_id = NEW.problem_id) AND (result_id = 1)) LOOP
      UPDATE api_userprofile SET points = (api_userprofile.points - old_value + new_value) WHERE user_id = row.user_id;
    END LOOP;

    UPDATE api_problem SET points = new_value WHERE api_problem.id = NEW.problem_id;
  END IF;
  RETURN NEW;
END;

$BODY$;

ALTER FUNCTION public.updatesubmission()
    OWNER TO postgres;
