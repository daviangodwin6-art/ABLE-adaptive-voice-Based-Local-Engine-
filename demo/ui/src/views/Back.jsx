export default function Back({ onClick, children = "← Back to ABLE" }) {
  return <button className="btn-back" onClick={onClick}>{children}</button>;
}
