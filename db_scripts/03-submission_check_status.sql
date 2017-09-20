DROP TRIGGER IF EXISTS check_update ON PUBLIC.api_submission;

CREATE TRIGGER check_update
  AFTER UPDATE OF result_id
  ON PUBLIC.api_submission
  FOR EACH ROW
  WHEN ((OLD.result_id IS DISTINCT FROM NEW.result_id))
  EXECUTE PROCEDURE PUBLIC.update_submission();
