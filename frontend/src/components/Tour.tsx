import React, { useCallback, useEffect, useLayoutEffect, useState } from 'react';
import { X, ArrowRight, ArrowLeft, Loader2 } from 'lucide-react';
import { DEMO_EVENTS } from '../samples/gstSample';

const STORAGE_KEY = 'shreshti_tour_done_v1';

interface TourAction {
  label: string;
  /** Event that makes the page do the step for the visitor. */
  fire: string;
  /** Event that signals the step has finished; the tour moves on when it arrives. */
  doneEvent?: string;
}

interface TourStep {
  /** CSS selector of the element to highlight; centred card when absent or not on the page. */
  target?: string;
  kicker: string;
  title: string;
  body: React.ReactNode;
  action?: TourAction;
  /** Shown instead of the body when the target is not on the page yet. */
  missing?: string;
}

const STEPS: TourStep[] = [
  {
    kicker: 'Welcome',
    title: 'Check an invoice in 60 seconds',
    body: (
      <>
        ShreshtiAI is a digital munim for micro enterprises. It reads an invoice, checks every line against GST and
        MSMED Act rules, and cites the exact rule for each finding. It never guesses: when the rules don&apos;t settle a
        line, it says <b className="tour-review">needs review</b>.
        <br />
        <br />
        This tour does each step for you. It takes about a minute.
      </>
    ),
  },
  {
    target: '#guidelines',
    kicker: 'Step 1 of 5 · Rules',
    title: 'Load the GST rule book',
    body: (
      <>
        Every verdict is grounded in a rule document. Load the sample GST rules: tax type (IGST Act s.8), invoice
        contents (CGST Rules r.46), input tax credit (CGST Act s.16, s.17) and MSME payment terms (MSMED Act s.15).
      </>
    ),
    action: { label: 'Load sample GST rules', fire: DEMO_EVENTS.loadGst, doneEvent: DEMO_EVENTS.gstLoaded },
  },
  {
    target: '#marketing-copy-input',
    kicker: 'Step 2 of 5 · Invoice',
    title: 'Paste an invoice',
    body: (
      <>
        Owners paste invoice text here, or upload a photo with <i>Image OCR Review</i>. Fill in a sample invoice from Sri
        Lakshmi Traders, Birur, a fictional shop. It contains a few deliberate mistakes.
      </>
    ),
    action: { label: 'Fill sample invoice', fire: DEMO_EVENTS.fillInvoice },
  },
  {
    target: '#btn-analyze-compliance',
    kicker: 'Step 3 of 5 · Check',
    title: 'Run the check',
    body: (
      <>
        Each line is matched against the rule text with hybrid search (keywords + meaning). Then it is marked
        <b className="tour-ok"> compliant</b>, <b className="tour-bad">non-compliant</b> or
        <b className="tour-review"> needs review</b>. The free server can take up to a minute to wake the first time.
      </>
    ),
    action: { label: 'Run the check', fire: DEMO_EVENTS.runCheck, doneEvent: DEMO_EVENTS.reviewDone },
  },
  {
    target: '#verdict-board',
    kicker: 'Step 4 of 5 · Verdict',
    title: 'Read the verdict',
    body: (
      <>
        The headline gives the overall verdict. The invoice is marked up on the left: each underline is one finding,
        coloured by verdict and numbered. On the right, each finding gives its reason and the rule file it came from.
      </>
    ),
    missing: 'Run the check in step 3 first; the verdict board appears here with the results.',
  },
  {
    target: "article[id^='claim-verdict-card-']",
    kicker: 'Step 5 of 5 · Evidence',
    title: 'See the exact rule text',
    body: (
      <>
        Every finding quotes the rule it relied on, with retrieval scores, and drafts a correction where it is safe to.
        Nothing is filed or sent without the owner&apos;s approval. Every check is saved in the <i>Audit trail</i> below
        and can be exported as PDF, CSV or JSON.
      </>
    ),
    missing: 'Run the check in step 3 first; the evidence cards appear below the verdict board.',
  },
];

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

const PAD = 8;

const readTourDone = (): boolean => {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
};

const writeTourDone = () => {
  try {
    window.localStorage.setItem(STORAGE_KEY, '1');
  } catch {
    // Storage can be unavailable (private mode); the tour then simply shows again next time.
  }
};

export const Tour: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [isNarrow, setIsNarrow] = useState(() => typeof window !== 'undefined' && window.innerWidth < 640);

  const step = STEPS[index];
  const last = index === STEPS.length - 1;

  const close = useCallback(() => {
    setOpen(false);
    setBusy(false);
    writeTourDone();
  }, []);

  const start = useCallback(() => {
    setIndex(0);
    setNote(null);
    setBusy(false);
    setOpen(true);
  }, []);

  // First visit: start automatically. Automated browsers (UI tests) are left alone.
  useEffect(() => {
    if (readTourDone() || (typeof navigator !== 'undefined' && navigator.webdriver)) return;
    const t = window.setTimeout(start, 1200);
    return () => window.clearTimeout(t);
  }, [start]);

  // "Take the tour" buttons elsewhere on the page.
  useEffect(() => {
    window.addEventListener(DEMO_EVENTS.startTour, start);
    return () => window.removeEventListener(DEMO_EVENTS.startTour, start);
  }, [start]);

  const measure = useCallback(() => {
    const narrow = window.innerWidth < 640;
    setIsNarrow((prev) => (prev === narrow ? prev : narrow));
    const el = step?.target ? (document.querySelector(step.target) as HTMLElement | null) : null;
    if (!el) {
      setRect((prev) => (prev === null ? prev : null));
      return;
    }
    const r = el.getBoundingClientRect();
    const nextRect = { top: r.top - PAD, left: r.left - PAD, width: r.width + PAD * 2, height: r.height + PAD * 2 };
    // Only update when it moved, so the per-frame loop doesn't re-render needlessly.
    setRect((prev) =>
      prev &&
      Math.abs(prev.top - nextRect.top) < 0.5 &&
      Math.abs(prev.left - nextRect.left) < 0.5 &&
      Math.abs(prev.width - nextRect.width) < 0.5 &&
      Math.abs(prev.height - nextRect.height) < 0.5
        ? prev
        : nextRect
    );
  }, [step]);

  // Bring the target into view whenever the step changes.
  useLayoutEffect(() => {
    if (!open) return;
    setNote(null);
    const el = step?.target ? (document.querySelector(step.target) as HTMLElement | null) : null;
    if (el) {
      el.scrollIntoView?.({ behavior: 'smooth', block: isNarrow ? 'start' : 'center' });
    }
    measure();
    const t = window.setTimeout(measure, 450);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, index]);

  // Keep the highlight on the target while the page scrolls, resizes or re-renders.
  useEffect(() => {
    if (!open) return;
    // Re-measure every frame so the highlight follows smooth scrolling and layout changes.
    let frame = 0;
    const loop = () => {
      measure();
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frame);
  }, [open, measure]);

  const next = useCallback(() => {
    setBusy(false);
    if (last) close();
    else setIndex((i) => i + 1);
  }, [last, close]);

  const back = useCallback(() => {
    setBusy(false);
    setIndex((i) => Math.max(0, i - 1));
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
      else if (e.key === 'ArrowRight' && !busy) next();
      else if (e.key === 'ArrowLeft' && !busy) back();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, busy, next, back, close]);

  const runAction = () => {
    const action = step.action;
    if (!action) return;
    if (!action.doneEvent) {
      window.dispatchEvent(new Event(action.fire));
      window.setTimeout(next, 350);
      return;
    }
    setBusy(true);
    setNote(null);
    const onDone = (e: Event) => {
      window.removeEventListener(action.doneEvent as string, onDone);
      window.clearTimeout(timer);
      const detail = (e as CustomEvent).detail as { ok?: boolean; error?: boolean } | undefined;
      setBusy(false);
      if (detail && (detail.ok === false || detail.error)) {
        setNote('That did not finish: the server may still be waking up. Wait a few seconds and try again.');
        return;
      }
      window.setTimeout(next, 300);
    };
    const timer = window.setTimeout(() => {
      window.removeEventListener(action.doneEvent as string, onDone);
      setBusy(false);
      setNote('This is taking longer than usual (the free server may be waking up). You can wait and press Next.');
    }, 120000);
    window.addEventListener(action.doneEvent, onDone);
    window.dispatchEvent(new Event(action.fire));
  };

  if (!open || !step) return null;

  const targetMissing = !!step.target && !rect;

  // Card placement: below the target if it fits, else above, else pinned to the bottom.
  const cardWidth = Math.min(380, window.innerWidth - 32);
  let cardStyle: React.CSSProperties;
  if (isNarrow || !rect) {
    cardStyle = isNarrow
      ? { left: 16, right: 16, bottom: 16 }
      : { left: '50%', top: '50%', transform: 'translate(-50%, -50%)', width: cardWidth };
  } else {
    const spaceBelow = window.innerHeight - (rect.top + rect.height);
    const left = Math.min(Math.max(16, rect.left), window.innerWidth - cardWidth - 16);
    if (rect.height > window.innerHeight * 0.6) cardStyle = { bottom: 16, left: Math.max(16, rect.left + 24), width: cardWidth };
    else if (spaceBelow > 260) cardStyle = { top: rect.top + rect.height + 14, left, width: cardWidth };
    else if (rect.top > 260) cardStyle = { bottom: window.innerHeight - rect.top + 14, left, width: cardWidth };
    else cardStyle = { bottom: 16, right: 16, width: cardWidth };
  }

  return (
    <div className="tour-root" aria-live="polite">
      {rect ? (
        <div
          className="tour-spotlight"
          style={{ top: rect.top, left: rect.left, width: rect.width, height: rect.height }}
          aria-hidden="true"
        />
      ) : (
        <div className="tour-scrim" aria-hidden="true" onClick={close} />
      )}

      <div className="tour-card" role="dialog" aria-modal="false" aria-labelledby="tour-title" style={cardStyle}>
        <div className="tour-head">
          <span className="tour-kicker">{step.kicker}</span>
          <button type="button" className="tour-x" onClick={close} aria-label="Close tour">
            <X size={14} />
          </button>
        </div>
        <h2 id="tour-title" className="tour-title">
          {step.title}
        </h2>
        <div className="tour-body">{targetMissing && step.missing ? step.missing : step.body}</div>
        {note && <div className="tour-note">{note}</div>}

        <div className="tour-dots" aria-hidden="true">
          {STEPS.map((_, i) => (
            <span key={i} className={i === index ? 'on' : i < index ? 'done' : ''} />
          ))}
        </div>

        <div className="tour-actions">
          {index === 0 ? (
            <button type="button" className="btn btn-secondary tour-btn" onClick={close}>
              Skip
            </button>
          ) : (
            <button type="button" className="btn btn-secondary tour-btn" onClick={back} disabled={busy}>
              <ArrowLeft size={13} /> Back
            </button>
          )}
          <span style={{ flex: 1 }} />
          {step.action && !targetMissing ? (
            <>
              <button type="button" className="tour-link" onClick={next} disabled={busy}>
                Next
              </button>
              <button type="button" className="btn btn-primary tour-btn" onClick={runAction} disabled={busy}>
                {busy ? <Loader2 size={13} className="spinning" /> : null}
                {busy ? 'Working…' : step.action.label}
              </button>
            </>
          ) : (
            <button type="button" className="btn btn-primary tour-btn" onClick={next}>
              {index === 0 ? 'Start the tour' : last ? 'Finish' : 'Next'}
              {!last && <ArrowRight size={13} />}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
