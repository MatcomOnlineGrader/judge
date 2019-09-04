import Button from "./ui/button";
import * as React from "react";

const messages = {
  subjectPlaceholder: "Brief description",
  descriptionPlaceholder:
    "Send us the error you found and how to reproduce it step by step. " +
    "You can also send suggestions or anything else you want to share with us. " +
    "Attach a screenshot to help us understand your request."
};

export class ReporterModal extends React.Component<{}, {}> {
  topUrl(): string {
    return window.location.href;
  }

  render() {
    const csrftoken = (window as any)["CurrentUser"].csrftoken;
    return (
      <div
        className="modal fade"
        id="reporter"
        tabIndex={-1}
        role="dialog"
        aria-labelledby="reporterModalLabel"
      >
        <div className="modal-dialog" role="document">
          <div className="modal-content">
            <div className="modal-header">
              <Button
                className="close"
                data={{ dismiss: "modal" }}
                ariaLabel="Close"
              >
                <span aria-hidden="true">&times;</span>
              </Button>
              <h4 className="modal-title" id="reporterModalLabel">
                Contact us (<small>bug, suggestions, etc</small>)
              </h4>
            </div>
            <div className="modal-body">
              <form
                action="/feedback/create/"
                method="post"
                encType="multipart/form-data"
              >
                <input
                  type="hidden"
                  name="csrfmiddlewaretoken"
                  value={csrftoken}
                />
                <input name="next" value={this.topUrl()} hidden />
                <div className="form-group">
                  <label>Subject</label>
                  <input
                    name="subject"
                    className="form-control"
                    placeholder={messages.subjectPlaceholder}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Description</label>
                  <textarea
                    name="description"
                    className="form-control"
                    rows={5}
                    placeholder={messages.descriptionPlaceholder}
                  />
                </div>
                <div className="form-group">
                  <label>Screenshot</label>
                  <input
                    type="file"
                    name="screenshot"
                    className="btn btn-default"
                    style={{ width: "100%" }}
                    accept="image/*"
                  />
                </div>
                <div className="text-center">
                  <Button data={{ dismiss: "modal" }}>Cancel</Button>
                  <span>&nbsp;</span>
                  <Button
                    primary
                    // onClick={this.handleSubmitClick}
                    type="submit"
                  >
                    <i className="glyphicon glyphicon-send" /> Send
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
