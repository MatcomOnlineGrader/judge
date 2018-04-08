-- TRIGGER executed when a submission change its result,
-- status, or hidden field. This is because only
-- "accepted-normal-visible" submissions are considered to
-- calculate problem points.
DROP TRIGGER IF EXISTS check_update ON PUBLIC.api_submission;

CREATE TRIGGER check_update
  AFTER UPDATE OF result_id, status, hidden
  ON PUBLIC.api_submission
  FOR EACH ROW
  WHEN ((OLD.result_id IS DISTINCT FROM NEW.result_id) OR
        (OLD.status IS DISTINCT FROM NEW.status) OR
        (OLD.hidden IS DISTINCT FROM NEW.hidden))
  EXECUTE PROCEDURE PUBLIC.update_submission();
