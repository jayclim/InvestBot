"use client";
import { createContext, useContext, useState, useEffect, useRef, useCallback } from "react";
import StockModal from "./StockModal";

const Ctx = createContext(null);

export function ModalProvider({ children, data }) {
  const [node, setNode] = useState(null);
  const dataRef = useRef(data);
  dataRef.current = data;
  const histRef = useRef(null);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") setNode(null); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  // Open the per-stock drill-down. Price history is a separate ~315 KB file fetched once,
  // then cached for the rest of the session.
  const openStock = useCallback(async (symbol) => {
    let h = histRef.current;
    if (!h) {
      try { h = await fetch("/history.json", { cache: "force-cache" }).then((r) => r.json()); }
      catch (_e) { h = {}; }
      histRef.current = h;
    }
    setNode(<StockModal symbol={symbol} data={dataRef.current} history={h} />);
  }, []);

  return (
    <Ctx.Provider value={{ open: setNode, close: () => setNode(null), openStock, node }}>
      {children}
    </Ctx.Provider>
  );
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
    >?</button>
  );
}
