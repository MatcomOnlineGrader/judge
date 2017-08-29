CREATE OR REPLACE FUNCTION public.updatesubmission()
    RETURNS trigger
    LANGUAGE 'plpgsql'
    COST 100.0
    VOLATILE NOT LEAKPROOF 
AS $BODY$

BEGIN
  IF NEW.result_id IS DISTINCT FROM OLD.result_id THEN
    UPDATE api_problem SET points = (SELECT ComputeProblemPoints(NEW.problem_id)) WHERE api_problem.id = NEW.problem_id;
  END IF;
  RETURN NEW;
END;

$BODY$;

ALTER FUNCTION public.updatesubmission()
    OWNER TO postgres;
