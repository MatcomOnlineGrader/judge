DO
$do$
DECLARE
    problem record;
BEGIN 
  FOR problem IN (SELECT * FROM api_problem) LOOP
    update api_problem SET points = (SELECT computeproblempoints(problem.id)) WHERE api_problem.id = problem.id;
  END LOOP;
END
$do$;
