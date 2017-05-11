DO
$do$
declare
    problem record;
BEGIN 
FOR problem IN (SELECT * FROM   api_problem) LOOP
	update api_problem set points = (select computeproblempoints(problem.id)) where api_problem.id = problem.id;
END LOOP;
END
$do$;