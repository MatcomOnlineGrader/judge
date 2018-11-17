import * as React from "react";
import { ReporterModal } from "./reporter_modal";

export class ReporterButton extends React.Component<{}, {}> {
  render() {
    return (
      <div>
        <ReporterModal />
        <a
          className="reporter-button"
          href="#"
          data-toggle="tooltip"
          data-placement="top"
          title="Report"
        >
          <a href="#" data-toggle="modal" data-target="#reporter">
            <span className="glyphicon glyphicon-exclamation-sign" />
          </a>
        </a>
      </div>
    );
  }
}
