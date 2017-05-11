CREATE OR REPLACE FUNCTION public.computeproblempoints(
	problemid integer)
    RETURNS integer
    LANGUAGE 'plpgsql'
    COST 100.0
    VOLATILE 
AS $function$

DECLARE
    solved int;
BEGIN
  SELECT Count(DISTINCT api_submission.user_id) INTO solved FROM api_submission WHERE api_submission.problem_id = problemId AND api_submission.hidden = False AND api_submission.result_id=1;
  return 108 / (12 + solved) + 1;
END;

$function$;

ALTER FUNCTION public.computeproblempoints(integer)
    OWNER TO postgres;
