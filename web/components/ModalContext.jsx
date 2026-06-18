"use client";
import { createContext, useContext, useState, useEffect } from "react";

const Ctx = createContext(null);

export function ModalProvider({ children }) {
  const [node, setNode] = useState(null);
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") setNode(null); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);
  return <Ctx.Provider value={{ open: setNode, close: () => setNode(null), node }}>{children}</Ctx.Provider>;
}

export const useModal = () => useContext(Ctx);

export function Modal() {
  const { node, close } = useModal();
  if (!node) return null;
  return (
    <div className="modal" onClick={(e) => { if (e.target.classList.contains("modal") || e.target.classList.contains("modal-bg")) close(); }}>
      <div className="modal-bg" />
      <div className="modal-card" role="dialog" aria-modal="true">
        <button className="modal-x" onClick={close} aria-label="Close">✕</button>
        <div>{node}</div>
      </div>
    </div>
  );
}

export function InfoButton({ title, children }) {
  const { open } = useModal();
  return (
    <button
      className="i"
      aria-label={`About ${title}`}
      onClick={() => open(<><div className="modal-eyebrow">Where this comes from</div><h3>{title}</h3><p>{children}</p></>)}
    />
  );
}
