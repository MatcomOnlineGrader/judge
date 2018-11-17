import * as React from "react";
import * as ReactDOM from "react-dom";

import { ReporterButton } from "./components/reporter_button";

const CurrentUser = (window as any)["CurrentUser"];

if (CurrentUser && CurrentUser.authenticated) {
  ReactDOM.render(<ReporterButton />, document.getElementById("report-issues"));
}
