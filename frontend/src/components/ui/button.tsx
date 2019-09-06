import * as React from "react";

interface ButtonProps {
  ariaLabel?: string;
  onClick?: (e: any) => void;
  primary?: boolean;
  type?: "button" | "submit";
  data?: { [key: string]: any };
  className?: string;
}

class Button extends React.Component<ButtonProps, {}> {
  render() {
    let cls = "btn";
    if (!!this.props.primary) {
      cls += " btn-primary";
    } else {
      cls += " btn-default";
    }
    const data: { [key: string]: any } = {};
    if (this.props.data) {
      for (const name in this.props.data) {
        data[`data-${name}`] = this.props.data[name];
      }
    }
    return (
      <button
        aria-label={this.props.ariaLabel}
        type={this.props.type || "button"}
        className={this.props.className || cls}
        onClick={this.props.onClick}
        {...data}
      >
        {this.props.children}
      </button>
    );
  }
}

export default Button;
