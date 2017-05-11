-- FUNCTION: public.computeproblempoints(integer)

-- DROP FUNCTION public.computeproblempoints(integer);

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

select Count( distinct api_submission.user_id) into solved from api_submission where api_submission.problem_id = problemId and api_submission.hidden = false and api_submission.result_id=1;
return 108 / (12 + solved) + 1;
END;

$function$;

ALTER FUNCTION public.computeproblempoints(integer)
    OWNER TO postgres;


