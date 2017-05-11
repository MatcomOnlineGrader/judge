-- Trigger: check_update

-- DROP TRIGGER check_update ON public.api_submission;

CREATE TRIGGER check_update
    BEFORE UPDATE OF result_id
    ON public.api_submission
    FOR EACH ROW
    WHEN ((old.result_id IS DISTINCT FROM new.result_id))
    EXECUTE PROCEDURE public.updatesubmission();