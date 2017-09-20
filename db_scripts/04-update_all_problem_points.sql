DO
$DO$
  DECLARE
      problem RECORD;
  BEGIN
    FOR problem IN (SELECT * FROM api_problem) LOOP
      UPDATE api_problem SET points = (SELECT compute_problem_points(problem.id)) WHERE api_problem.id = problem.id;
    END LOOP;
  END
$DO$;
