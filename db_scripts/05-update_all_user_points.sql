DO
$DO$
  DECLARE
      user_profile RECORD;
  BEGIN
    FOR user_profile IN (SELECT * FROM api_userprofile) LOOP
      UPDATE api_userprofile SET points = (SELECT compute_user_points(user_profile.user_id)) WHERE api_userprofile.user_id = user_profile.user_id;
    END LOOP;
  END
$DO$;
