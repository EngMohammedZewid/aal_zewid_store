import { ReactNode } from "react";

export function Modal({ title, children, onClose, className = "" }: { title: string; children: ReactNode; onClose: () => void; className?: string }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className={`modal ${className}`.trim()} onClick={(event) => event.stopPropagation()}>
        <div className="page-head">
          <h2 style={{ margin: 0 }}>{title}</h2>
          <button className="btn btn-muted" onClick={onClose}>إغلاق</button>
        </div>
        {children}
      </div>
    </div>
  );
}
